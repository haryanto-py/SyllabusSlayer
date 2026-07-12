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
    User,
)
from app.schemas.game import CombatConfig
from app.services import runmap, scoring
from app.services.users import get_or_create_user

router = APIRouter(prefix="/student", tags=["student"], dependencies=[Depends(require_student)])


def _load_session(session: Session, session_id: str, user: User) -> PlaySession:
    ps = session.get(PlaySession, session_id)
    if not ps or ps.student_id != user.id:
        raise HTTPException(404, "play session not found")
    return ps


def _cfg(campaign: Campaign) -> CombatConfig:
    return CombatConfig.model_validate(campaign.combat_config or {})


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
    ps = PlaySession(
        campaign_id=campaign_id,
        assignment_id=assignment_id,
        student_id=user.id,
        status=SessionStatus.in_progress,
        hp_remaining=cfg.playerStartingHp,
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
    result = scoring.score_answer(question, body.answer, prev_streak, cfg)

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

    return {
        "isCorrect": result["is_correct"],
        "correctAnswer": result["correct"],
        "explanation": question.get("explanation"),
        "sourceQuote": question.get("sourceQuote"),
        "sourcePage": question.get("sourcePage"),
        "damage": result["damage"],
        "streak": result["new_streak"],
        "hp": ps.hp_remaining,
        "score": ps.final_score,
        "xp": ps.final_xp,
        "level": scoring.level_for_xp(ps.final_xp or 0, cfg),
        "playerDown": ps.hp_remaining <= 0,
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
        ps.status = SessionStatus.completed
        ps.completed_at = datetime.now(UTC)
        session.add(ps)
        session.commit()
    return {
        "status": ps.status.value,
        "score": ps.final_score or 0,
        "xp": ps.final_xp or 0,
        "hp": ps.hp_remaining,
        "level": scoring.level_for_xp(ps.final_xp or 0, cfg),
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
