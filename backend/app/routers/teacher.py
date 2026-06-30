"""Teacher-facing routes (RBAC: teacher).

M1 endpoints:
  POST /teacher/documents          upload + parse a resource → Document
  POST /teacher/campaigns/generate run the AI pipeline → stored game Campaign
  GET  /teacher/campaigns/{id}     fetch the generated game JSON

The router-level dependency enforces the teacher role. Review/edit/assign + analytics
arrive in M3.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.security import CurrentUser, require_teacher
from app.models.tables import (
    Assignment,
    Campaign,
    CampaignStatus,
    Chunk,
    Class,
    Document,
    DocumentStatus,
    Enrollment,
    PlaySession,
    QuestionAttempt,
    SessionStatus,
    User,
)
from app.schemas.game import CombatConfig, EncounterKind, Question
from app.services import analytics, assembly, combat_tuning, embeddings
from app.services.chunking import chunk_document, count_tokens
from app.services.ingestion import flatten, parse_document, parse_markdown
from app.services.users import get_or_create_user

router = APIRouter(prefix="/teacher", tags=["teacher"], dependencies=[Depends(require_teacher)])

_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"


# Join codes avoid ambiguous characters (no 0/O, 1/I).
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _gen_join_code(session: Session, length: int = 6) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
        if not session.exec(select(Class).where(Class.join_code == code)).first():
            return code
    raise HTTPException(500, "could not allocate a unique join code")


@router.get("/me")
def whoami(user: CurrentUser = Depends(require_teacher)) -> dict:
    return {"role": user.role, "sub": user.sub, "email": user.email}


class DocumentOut(BaseModel):
    id: str
    filename: str
    status: str
    token_count: int
    section_count: int


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> DocumentOut:
    user = get_or_create_user(session, current)
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = str(uuid4())
    dest = _UPLOAD_DIR / f"{doc_id}_{file.filename or 'upload'}"
    dest.write_bytes(await file.read())

    try:
        parsed = parse_document(dest)
    except Exception as exc:  # noqa: BLE001
        session.add(
            Document(
                id=doc_id,
                owner_id=user.id,
                filename=file.filename or dest.name,
                storage_url=str(dest),
                mime=file.content_type or "application/octet-stream",
                status=DocumentStatus.failed,
            )
        )
        session.commit()
        raise HTTPException(422, f"parse failed: {exc}") from exc

    sections = flatten(parsed.sections)
    doc = Document(
        id=doc_id,
        owner_id=user.id,
        filename=file.filename or dest.name,
        storage_url=str(dest),
        mime=file.content_type or "text/markdown",
        status=DocumentStatus.parsed,
        parsed_markdown=parsed.markdown,
        section_tree={"section_titles": [s.title for s in sections]},
        token_count=count_tokens(parsed.markdown),
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    # Persist chunks for retrieval/reuse (T2). Embedding is best-effort: if it fails
    # (e.g. no API key), store chunks without vectors so the upload still succeeds.
    chunks = chunk_document(parsed)
    try:
        vectors, _ = embeddings.embed_texts_with_usage([c.text for c in chunks])
    except Exception:  # noqa: BLE001
        vectors = [None] * len(chunks)
    for chunk, vec in zip(chunks, vectors, strict=False):
        session.add(
            Chunk(
                document_id=doc.id, ord=chunk.ord, text=chunk.text,
                section=chunk.section, embedding=vec,
            )
        )
    session.commit()

    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        token_count=doc.token_count or 0,
        section_count=len(sections),
    )


class GenerateIn(BaseModel):
    document_id: str
    title: str | None = None


class GenerateOut(BaseModel):
    campaign_id: str
    title: str
    status: str
    eval: dict
    usage: dict
    estimated_cost_usd: float


@router.post("/campaigns/generate", response_model=GenerateOut)
def generate_campaign(
    body: GenerateIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> GenerateOut:
    user = get_or_create_user(session, current)
    doc = session.get(Document, body.document_id)
    if not doc or doc.owner_id != user.id:
        raise HTTPException(404, "document not found")
    if not doc.parsed_markdown:
        raise HTTPException(409, f"document not parsed (status={doc.status})")

    parsed = parse_markdown(doc.parsed_markdown)
    result = assembly.build_game(parsed=parsed, source_document_id=doc.id, title=body.title)
    game = result["game"]

    campaign = Campaign(
        document_id=doc.id,
        teacher_id=user.id,
        title=game["title"],
        status=CampaignStatus.ready,
        game_json=game,
        combat_config=game.get("combatConfig"),
        schema_version=game.get("schemaVersion", "1.0.0"),
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return GenerateOut(
        campaign_id=campaign.id,
        title=campaign.title,
        status=campaign.status.value,
        eval=result["eval"],
        usage=result["usage"],
        estimated_cost_usd=result["estimated_cost_usd"],
    )


@router.get("/campaigns/{campaign_id}")
def get_campaign(
    campaign_id: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> dict:
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "campaign not found")
    return {
        "id": campaign.id,
        "title": campaign.title,
        "status": campaign.status.value,
        "game": campaign.game_json,
    }


# --------------------------------------------------------------------------- #
# Classes & roster (M3-T1)
# --------------------------------------------------------------------------- #
class ClassCreate(BaseModel):
    name: str


class ClassOut(BaseModel):
    id: str
    name: str
    join_code: str
    student_count: int


@router.post("/classes", response_model=ClassOut)
def create_class(
    body: ClassCreate,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> ClassOut:
    user = get_or_create_user(session, current)
    cls = Class(teacher_id=user.id, name=body.name, join_code=_gen_join_code(session))
    session.add(cls)
    session.commit()
    session.refresh(cls)
    return ClassOut(id=cls.id, name=cls.name, join_code=cls.join_code, student_count=0)


@router.get("/classes", response_model=list[ClassOut])
def list_classes(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> list[ClassOut]:
    user = get_or_create_user(session, current)
    classes = session.exec(select(Class).where(Class.teacher_id == user.id)).all()
    out = []
    for cls in classes:
        count = len(session.exec(select(Enrollment).where(Enrollment.class_id == cls.id)).all())
        out.append(
            ClassOut(id=cls.id, name=cls.name, join_code=cls.join_code, student_count=count)
        )
    return out


@router.get("/classes/{class_id}")
def class_detail(
    class_id: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> dict:
    user = get_or_create_user(session, current)
    cls = session.get(Class, class_id)
    if not cls or cls.teacher_id != user.id:
        raise HTTPException(404, "class not found")
    enrollments = session.exec(select(Enrollment).where(Enrollment.class_id == class_id)).all()
    roster = []
    for enr in enrollments:
        student = session.get(User, enr.student_id)
        if student:
            roster.append(
                {"id": student.id, "display_name": student.display_name, "email": student.email}
            )
    return {"id": cls.id, "name": cls.name, "join_code": cls.join_code, "roster": roster}


# --------------------------------------------------------------------------- #
# Assignments (M3-T2): assign a campaign to a class
# --------------------------------------------------------------------------- #
class AssignmentCreate(BaseModel):
    campaign_id: str
    due_at: datetime | None = None


class AssignmentOut(BaseModel):
    id: str
    campaign_id: str
    campaign_title: str
    class_id: str
    due_at: datetime | None


def _require_owned_class(session: Session, class_id: str, user: User) -> Class:
    cls = session.get(Class, class_id)
    if not cls or cls.teacher_id != user.id:
        raise HTTPException(404, "class not found")
    return cls


@router.post("/classes/{class_id}/assignments", response_model=AssignmentOut)
def create_assignment(
    class_id: str,
    body: AssignmentCreate,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> AssignmentOut:
    user = get_or_create_user(session, current)
    _require_owned_class(session, class_id, user)
    campaign = session.get(Campaign, body.campaign_id)
    if not campaign or campaign.teacher_id != user.id:
        raise HTTPException(404, "campaign not found")
    assignment = Assignment(campaign_id=campaign.id, class_id=class_id, due_at=body.due_at)
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return AssignmentOut(
        id=assignment.id, campaign_id=campaign.id, campaign_title=campaign.title,
        class_id=class_id, due_at=assignment.due_at,
    )


@router.get("/classes/{class_id}/assignments", response_model=list[AssignmentOut])
def list_assignments(
    class_id: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> list[AssignmentOut]:
    user = get_or_create_user(session, current)
    _require_owned_class(session, class_id, user)
    rows = session.exec(select(Assignment).where(Assignment.class_id == class_id)).all()
    out = []
    for a in rows:
        camp = session.get(Campaign, a.campaign_id)
        out.append(
            AssignmentOut(
                id=a.id, campaign_id=a.campaign_id,
                campaign_title=camp.title if camp else "(deleted)",
                class_id=class_id, due_at=a.due_at,
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Campaign list + review/edit + publish (M3-T3)
# --------------------------------------------------------------------------- #
@router.get("/campaigns")
def list_campaigns(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> list[dict]:
    user = get_or_create_user(session, current)
    rows = session.exec(select(Campaign).where(Campaign.teacher_id == user.id)).all()
    return [{"id": c.id, "title": c.title, "status": c.status.value} for c in rows]


def _recompute_combat(enc: dict, cfg: CombatConfig) -> None:
    questions = [Question.model_validate(q) for q in enc.get("questions", [])]
    kind = EncounterKind(enc.get("kind", "minion"))
    enc["combat"] = combat_tuning.compute_encounter_combat(
        questions, kind, cfg
    ).model_dump(mode="json")


@router.put("/campaigns/{campaign_id}/questions/{question_id}")
def edit_question(
    campaign_id: str,
    question_id: str,
    body: Question,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> dict:
    user = get_or_create_user(session, current)
    campaign = session.get(Campaign, campaign_id)
    if not campaign or campaign.teacher_id != user.id or not campaign.game_json:
        raise HTTPException(404, "campaign not found")
    game = campaign.game_json
    cfg = CombatConfig.model_validate(campaign.combat_config or {})
    updated = body.model_copy(update={"questionId": question_id}).model_dump(mode="json")
    for act in game.get("acts", []):
        for enc in act.get("encounters", []):
            for i, q in enumerate(enc.get("questions", [])):
                if q.get("questionId") == question_id:
                    enc["questions"][i] = updated
                    _recompute_combat(enc, cfg)
                    campaign.game_json = game
                    flag_modified(campaign, "game_json")  # JSON in-place edit needs flagging
                    session.add(campaign)
                    session.commit()
                    return {"ok": True, "question": updated}
    raise HTTPException(404, "question not found in campaign")


@router.post("/campaigns/{campaign_id}/publish")
def publish_campaign(
    campaign_id: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> dict:
    user = get_or_create_user(session, current)
    campaign = session.get(Campaign, campaign_id)
    if not campaign or campaign.teacher_id != user.id:
        raise HTTPException(404, "campaign not found")
    campaign.status = CampaignStatus.published
    session.add(campaign)
    session.commit()
    return {"id": campaign.id, "status": campaign.status.value}


# --------------------------------------------------------------------------- #
# Dashboard analytics (M3-T4)
# --------------------------------------------------------------------------- #
@router.get("/campaigns/{campaign_id}/analytics")
def campaign_analytics(
    campaign_id: str,
    class_id: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_teacher),
) -> dict:
    user = get_or_create_user(session, current)
    campaign = session.get(Campaign, campaign_id)
    if not campaign or campaign.teacher_id != user.id or not campaign.game_json:
        raise HTTPException(404, "campaign not found")
    _require_owned_class(session, class_id, user)

    roster = session.exec(select(Enrollment).where(Enrollment.class_id == class_id)).all()
    qindex = analytics.build_question_index(campaign.game_json)
    all_attempts: list = []
    students = []
    for enr in roster:
        student = session.get(User, enr.student_id)
        sessions = session.exec(
            select(PlaySession).where(
                PlaySession.campaign_id == campaign_id,
                PlaySession.student_id == enr.student_id,
            )
        ).all()
        sess_ids = [s.id for s in sessions]
        attempts: list = []
        if sess_ids:
            attempts = session.exec(
                select(QuestionAttempt).where(QuestionAttempt.session_id.in_(sess_ids))
            ).all()
        all_attempts.extend(attempts)
        correct = sum(1 for a in attempts if a.is_correct)
        students.append(
            {
                "student_id": enr.student_id,
                "name": student.display_name if student else "?",
                "attempts": len(attempts),
                "correct": correct,
                "accuracy": round(correct / len(attempts), 3) if attempts else 0.0,
                "best_score": max((s.final_score or 0 for s in sessions), default=0),
                "completed": any(s.status == SessionStatus.completed for s in sessions),
            }
        )
    topics, items = analytics.aggregate(all_attempts, qindex)
    total_correct = sum(1 for a in all_attempts if a.is_correct)
    return {
        "campaign_id": campaign_id,
        "class_id": class_id,
        "students": students,
        "topics": topics,
        "items": items,
        "summary": {
            "roster_size": len(roster),
            "started": sum(1 for s in students if s["attempts"] > 0),
            "completed": sum(1 for s in students if s["completed"]),
            "avg_accuracy": round(total_correct / len(all_attempts), 3) if all_attempts else 0.0,
        },
    }
