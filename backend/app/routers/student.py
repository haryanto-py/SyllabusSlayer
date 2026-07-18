"""Student-facing routes (RBAC: student): play a campaign with server-authoritative scoring.

  POST /student/play/{campaign_id}/start  -> PlaySession + the REDACTED game (no answers)
  POST /student/play/{session_id}/answer  -> score one answer, persist attempt, return state
  POST /student/play/{session_id}/finish  -> finalize the session

Join-by-class-code arrives in M3; for now a student plays a campaign by id.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.security import CurrentUser, require_student
from app.models.tables import (
    Assignment,
    Campaign,
    Class,
    Enrollment,
    PlaySession,
    QuestionAttempt,
    SessionStatus,
    StudentProgress,
    User,
)
from app.schemas.game import CombatConfig
from app.services import analytics, meta, relics, runmap, scoring
from app.services.users import get_or_create_user

router = APIRouter(prefix="/student", tags=["student"], dependencies=[Depends(require_student)])


def _load_session(session: Session, session_id: str, user: User) -> PlaySession:
    ps = session.get(PlaySession, session_id)
    if not ps or ps.student_id != user.id:
        raise HTTPException(404, "play session not found")
    return ps


def _cfg(campaign: Campaign) -> CombatConfig:
    return CombatConfig.model_validate(campaign.combat_config or {})


def _load_progress(session: Session, student_id: str, campaign_id: str) -> StudentProgress | None:
    return session.exec(
        select(StudentProgress).where(
            StudentProgress.student_id == student_id,
            StudentProgress.campaign_id == campaign_id,
        )
    ).first()


def _unlocked_set(progress: StudentProgress | None) -> set[str]:
    """Relic ids the caller may be offered/granted (defaults to the starter pool)."""
    if progress and progress.unlocked_relics:
        return set(progress.unlocked_relics)
    return set(meta.STARTER_RELICS)


def _bank_progress(session: Session, ps: PlaySession, campaign: Campaign | None) -> dict:
    """The SINGLE writer of StudentProgress. Called on BOTH defeat and victory so demonstrated
    learning banks identically win-or-lose. Recomputes cumulative per-topic mastery from ALL of
    this student's attempts on the campaign, mints Insight from the fresh-mastery delta, unlocks
    relics, and rolls up best_score/total_xp. Pure balance math lives in services/meta.py.
    Returns a summary dict for the run-end response.
    """
    cfg = _cfg(campaign) if campaign else CombatConfig()
    game = campaign.game_json if campaign else None

    sess_ids = [
        s.id
        for s in session.exec(
            select(PlaySession).where(
                PlaySession.student_id == ps.student_id,
                PlaySession.campaign_id == ps.campaign_id,
            )
        ).all()
    ]
    attempts: list = (
        session.exec(
            select(QuestionAttempt).where(QuestionAttempt.session_id.in_(sess_ids))
        ).all()
        if sess_ids
        else []
    )
    topics: list[dict] = []
    if game:
        qindex = analytics.build_question_index(game)
        topics, _ = analytics.aggregate(attempts, qindex)

    progress = _load_progress(session, ps.student_id, ps.campaign_id)
    if progress is None:
        progress = StudentProgress(student_id=ps.student_id, campaign_id=ps.campaign_id)
        session.add(progress)

    prior_mastery = progress.mastery_by_topic or {}
    insight_earned = meta.award_insight(topics, prior_mastery)
    merged = meta.merge_mastery(prior_mastery, topics)
    newly = meta.newly_unlocked_relics(merged, progress.unlocked_relics)

    prior_best = progress.best_score or 0
    is_new_best = (ps.final_score or 0) > prior_best  # strict improvement, computed before max()

    progress.mastery_by_topic = merged
    flag_modified(progress, "mastery_by_topic")  # SQLAlchemy misses in-place JSON edits
    progress.unlocked_relics = sorted(set(progress.unlocked_relics or []) | set(newly))
    flag_modified(progress, "unlocked_relics")
    progress.meta_currency = (progress.meta_currency or 0) + insight_earned
    progress.best_score = max(prior_best, ps.final_score or 0)
    progress.total_xp = (progress.total_xp or 0) + (ps.final_xp or 0)  # cumulative across runs
    progress.level = scoring.level_for_xp(progress.total_xp, cfg)
    progress.updated_at = datetime.now(UTC)
    session.add(progress)

    return {
        "insightEarned": insight_earned,
        "insightTotal": progress.meta_currency,
        "newlyUnlocked": [relics.relic_public(r) for r in newly if r in relics.RELICS],
        "masteryByTopic": merged,
        "bestScore": progress.best_score,
        "isNewBest": is_new_best,
        "level": progress.level,
    }


@router.get("/me")
def whoami(user: CurrentUser = Depends(require_student)) -> dict:
    return {"role": user.role, "sub": user.sub, "email": user.email}


@router.post("/play/{campaign_id}/start")
def start_play(
    campaign_id: str,
    assignment_id: str | None = None,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> dict:
    user = get_or_create_user(session, current)
    campaign = session.get(Campaign, campaign_id)
    if not campaign or not campaign.game_json:
        raise HTTPException(404, "campaign not found")
    cfg = _cfg(campaign)
    progress = _load_progress(session, user.id, campaign_id)
    bonus_hp = meta.start_bonus_max_hp(progress.mastery_by_topic if progress else None)
    ps = PlaySession(
        campaign_id=campaign_id,
        assignment_id=assignment_id,
        student_id=user.id,
        status=SessionStatus.in_progress,
        hp_remaining=cfg.playerStartingHp + bonus_hp,  # meta bonus routes through HP only
        bonus_max_hp=bonus_hp,
        final_score=0,
        final_xp=0,
    )
    session.add(ps)
    session.commit()
    session.refresh(ps)
    game = scoring.redact_game(campaign.game_json)
    for act in game.get("acts", []):
        if not act.get("map"):  # campaigns generated before M5.1 have no run map
            act["map"] = runmap.build_act_map(
                act.get("encounters", []), seed=f"{campaign.id}:{act.get('actId', '')}"
            )
    return {
        "session_id": ps.id,
        "combatConfig": cfg.model_dump(mode="json"),
        "game": game,
        "hp": ps.hp_remaining,
        "maxHp": cfg.playerStartingHp + bonus_hp,
        "startBonusMaxHp": bonus_hp,
    }


class AnswerIn(BaseModel):
    encounter_id: str
    question_id: str
    answer: Any
    time_ms: int | None = None


@router.post("/play/{session_id}/answer")
def submit_answer(
    session_id: str,
    body: AnswerIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> dict:
    user = get_or_create_user(session, current)
    ps = _load_session(session, session_id, user)
    if ps.status != SessionStatus.in_progress:
        raise HTTPException(409, "play session is not in progress")
    campaign = session.get(Campaign, ps.campaign_id)
    if not campaign or not campaign.game_json:
        raise HTTPException(404, "campaign not found")
    cfg = _cfg(campaign)

    question = scoring.find_question(campaign.game_json, body.encounter_id, body.question_id)
    if question is None:
        raise HTTPException(404, "question not found in campaign")

    prior = session.exec(
        select(QuestionAttempt)
        .where(QuestionAttempt.session_id == ps.id)
        .order_by(QuestionAttempt.attempted_at)
    ).all()
    prev_streak = scoring.trailing_streak([a.is_correct for a in prior])
    effects = relics.aggregate_effects(ps.relics)
    wrong_here = sum(1 for a in prior if a.encounter_id == body.encounter_id and not a.is_correct)
    result = scoring.score_answer(question, body.answer, prev_streak, cfg, effects, wrong_here)

    session.add(
        QuestionAttempt(
            session_id=ps.id,
            question_id=body.question_id,
            encounter_id=body.encounter_id,
            is_correct=result["is_correct"],
            selected_answer={"answer": body.answer},
            time_ms=body.time_ms,
            damage_dealt=result["damage"],
            streak_at_time=result["new_streak"],
        )
    )
    start_hp = ps.hp_remaining if ps.hp_remaining is not None else cfg.playerStartingHp
    ps.final_score = (ps.final_score or 0) + result["damage"]
    ps.final_xp = (ps.final_xp or 0) + result["xp_gain"]
    ps.hp_remaining = max(0, start_hp - result["hp_cost"])
    session.add(ps)
    session.commit()

    # Permadeath (server-authoritative): HP 0 ends the run. Bank progress FIRST so this-run
    # learning is never lost on a loss, THEN flip status — the in_progress guard above now 409s
    # any further /answer. The just-committed attempt is included in the banked mastery.
    outcome = "in_progress"
    death: dict = {}
    if ps.hp_remaining <= 0:
        # Bank BEFORE the status flip; capture the summary so the death screen can show the
        # Insight/relics actually earned this run (award_insight is delta-vs-peak, so these
        # values are only computable here — finish_play on a defeated run can't recover them).
        death = _bank_progress(session, ps, campaign)
        ps.status = SessionStatus.defeated
        ps.completed_at = datetime.now(UTC)
        session.add(ps)
        session.commit()
        outcome = "defeated"

    return {
        "isCorrect": result["is_correct"],
        "correctAnswer": result["correct"],
        "explanation": question.get("explanation"),
        "sourceQuote": question.get("sourceQuote"),
        "sourcePage": question.get("sourcePage"),
        "damage": result["damage"],
        "streak": result["new_streak"],
        "hp": ps.hp_remaining,
        "maxHp": cfg.playerStartingHp + (ps.bonus_max_hp or 0),
        "score": ps.final_score,
        "xp": ps.final_xp,
        "level": death.get("level", scoring.level_for_xp(ps.final_xp or 0, cfg)),
        "playerDown": ps.hp_remaining <= 0,
        "outcome": outcome,
        # meta banked on the killing blow (empty defaults while the run is still alive)
        "insightEarned": death.get("insightEarned", 0),
        "insightTotal": death.get("insightTotal"),
        "newlyUnlocked": death.get("newlyUnlocked", []),
        "masteryByTopic": death.get("masteryByTopic", {}),
        "bestScore": death.get("bestScore"),
        "isNewBest": death.get("isNewBest", False),
    }


@router.post("/play/{session_id}/finish")
def finish_play(
    session_id: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> dict:
    user = get_or_create_user(session, current)
    ps = _load_session(session, session_id, user)
    campaign = session.get(Campaign, ps.campaign_id)
    cfg = _cfg(campaign) if campaign else CombatConfig()
    if ps.status == SessionStatus.in_progress:
        # Victory / voluntary finish: bank once, then complete. A run already ended by
        # permadeath (submit_answer) skips this guard, so meta is never double-awarded.
        summary = _bank_progress(session, ps, campaign)
        ps.status = SessionStatus.completed
        ps.completed_at = datetime.now(UTC)
        session.add(ps)
        session.commit()
    else:
        progress = _load_progress(session, ps.student_id, ps.campaign_id)
        summary = {
            "insightEarned": 0,  # already banked at the terminal transition
            "insightTotal": (progress.meta_currency if progress else 0) or 0,
            "newlyUnlocked": [],
            "masteryByTopic": (progress.mastery_by_topic if progress else {}) or {},
            "bestScore": (progress.best_score if progress else ps.final_score) or 0,
            "isNewBest": False,  # no new terminal transition this call
            "level": progress.level if progress else scoring.level_for_xp(ps.final_xp or 0, cfg),
        }
    outcome = "defeated" if ps.status == SessionStatus.defeated else "completed"
    return {
        "status": ps.status.value,
        "outcome": outcome,
        "score": ps.final_score or 0,
        "xp": ps.final_xp or 0,
        "hp": ps.hp_remaining,
        "level": summary["level"],
        "insightEarned": summary["insightEarned"],
        "insightTotal": summary["insightTotal"],
        "newlyUnlocked": summary["newlyUnlocked"],
        "masteryByTopic": summary["masteryByTopic"],
        "bestScore": summary["bestScore"],
        "isNewBest": summary.get("isNewBest", False),
    }


# --------------------------------------------------------------------------- #
# Rest sites + relic rewards (M5.2)
# --------------------------------------------------------------------------- #
def _max_hp(ps: PlaySession, cfg: CombatConfig) -> int:
    return cfg.playerStartingHp + (ps.bonus_max_hp or 0)


@router.post("/play/{session_id}/rest")
def rest(
    session_id: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> dict:
    user = get_or_create_user(session, current)
    ps = _load_session(session, session_id, user)
    campaign = session.get(Campaign, ps.campaign_id)
    cfg = _cfg(campaign) if campaign else CombatConfig()
    max_hp = _max_hp(ps, cfg)
    heal = (max_hp * runmap.REST_HEAL_PCT + 99) // 100  # ceil
    current_hp = ps.hp_remaining if ps.hp_remaining is not None else max_hp
    ps.hp_remaining = min(max_hp, current_hp + heal)
    session.add(ps)
    session.commit()
    return {"hp": ps.hp_remaining, "maxHp": max_hp, "healed": heal}


@router.get("/play/{session_id}/reward-options")
def reward_options(
    session_id: str,
    node_id: str = "",
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> dict:
    user = get_or_create_user(session, current)
    ps = _load_session(session, session_id, user)
    progress = _load_progress(session, ps.student_id, ps.campaign_id)
    allowed = _unlocked_set(progress)  # only meta-unlocked relics are ever offered
    return {
        "options": relics.reward_options(ps.relics, seed=f"{ps.id}:{node_id}", allowed=allowed)
    }


class RewardIn(BaseModel):
    relic_id: str


@router.post("/play/{session_id}/reward")
def take_reward(
    session_id: str,
    body: RewardIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> dict:
    user = get_or_create_user(session, current)
    ps = _load_session(session, session_id, user)
    campaign = session.get(Campaign, ps.campaign_id)
    cfg = _cfg(campaign) if campaign else CombatConfig()
    if body.relic_id not in relics.RELICS:
        raise HTTPException(404, "unknown relic")
    progress = _load_progress(session, ps.student_id, ps.campaign_id)
    if body.relic_id not in _unlocked_set(progress):  # server rejects a locked relic
        raise HTTPException(403, "relic not unlocked")
    owned = list(ps.relics or [])
    if body.relic_id not in owned:
        owned.append(body.relic_id)
        effect = relics.RELICS[body.relic_id]["effect"]
        if effect["type"] == "max_hp":
            ps.bonus_max_hp = (ps.bonus_max_hp or 0) + effect["magnitude"]
            ps.hp_remaining = (ps.hp_remaining or cfg.playerStartingHp) + effect["magnitude"]
        ps.relics = owned
        session.add(ps)
        session.commit()
    return {
        "relics": [relics.relic_public(r) for r in (ps.relics or [])],
        "hp": ps.hp_remaining,
        "maxHp": _max_hp(ps, cfg),
    }


@router.get("/campaigns/{campaign_id}/profile")
def campaign_profile(
    campaign_id: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> dict:
    """The caller's persisted meta-progression for a campaign (default shape if no runs yet)."""
    user = get_or_create_user(session, current)
    progress = _load_progress(session, user.id, campaign_id)
    mastery = (progress.mastery_by_topic if progress else {}) or {}
    unlocked = sorted(_unlocked_set(progress))
    return {
        "level": progress.level if progress else 1,
        "totalXp": progress.total_xp if progress else 0,
        "bestScore": (progress.best_score if progress else 0) or 0,
        "insight": progress.meta_currency if progress else 0,
        "masteryByTopic": mastery,
        "unlockedRelics": [relics.relic_public(r) for r in unlocked if r in relics.RELICS],
        "startBonusMaxHp": meta.start_bonus_max_hp(mastery),
    }


# --------------------------------------------------------------------------- #
# Classes (M3-T1): join by code + list memberships
# --------------------------------------------------------------------------- #
class JoinIn(BaseModel):
    join_code: str


@router.post("/classes/join")
def join_class(
    body: JoinIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> dict:
    user = get_or_create_user(session, current)
    code = body.join_code.strip().upper()
    cls = session.exec(select(Class).where(Class.join_code == code)).first()
    if not cls:
        raise HTTPException(404, "no class with that code")
    existing = session.exec(
        select(Enrollment).where(
            Enrollment.class_id == cls.id, Enrollment.student_id == user.id
        )
    ).first()
    if not existing:
        session.add(Enrollment(class_id=cls.id, student_id=user.id))
        session.commit()
    return {"id": cls.id, "name": cls.name}


@router.get("/classes")
def my_classes(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> list[dict]:
    user = get_or_create_user(session, current)
    enrollments = session.exec(select(Enrollment).where(Enrollment.student_id == user.id)).all()
    out = []
    for enr in enrollments:
        cls = session.get(Class, enr.class_id)
        if cls:
            out.append({"id": cls.id, "name": cls.name})
    return out


@router.get("/assignments")
def my_assignments(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_student),
) -> list[dict]:
    user = get_or_create_user(session, current)
    enrollments = session.exec(select(Enrollment).where(Enrollment.student_id == user.id)).all()
    out = []
    for enr in enrollments:
        cls = session.get(Class, enr.class_id)
        rows = session.exec(select(Assignment).where(Assignment.class_id == enr.class_id)).all()
        for a in rows:
            camp = session.get(Campaign, a.campaign_id)
            out.append(
                {
                    "assignment_id": a.id,
                    "campaign_id": a.campaign_id,
                    "title": camp.title if camp else "(deleted)",
                    "class_name": cls.name if cls else "(class)",
                    "due_at": a.due_at.isoformat() if a.due_at else None,
                }
            )
    return out
