"""Teacher-facing routes (RBAC: teacher).

M1 endpoints:
  POST /teacher/documents          upload + parse a resource → Document
  POST /teacher/campaigns/generate run the AI pipeline → stored game Campaign
  GET  /teacher/campaigns/{id}     fetch the generated game JSON

The router-level dependency enforces the teacher role. Review/edit/assign + analytics
arrive in M3.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.security import CurrentUser, require_teacher
from app.models.tables import (
    Campaign,
    CampaignStatus,
    Document,
    DocumentStatus,
    User,
    UserRole,
)
from app.services import assembly
from app.services.chunking import count_tokens
from app.services.ingestion import flatten, parse_document, parse_markdown

router = APIRouter(prefix="/teacher", tags=["teacher"], dependencies=[Depends(require_teacher)])

_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"


def _get_or_create_user(session: Session, current: CurrentUser) -> User:
    user = session.exec(select(User).where(User.auth_provider_id == current.sub)).first()
    if user:
        return user
    user = User(
        email=current.email or f"{current.sub}@local",
        role=UserRole.teacher,
        display_name=(current.email or current.sub).split("@")[0],
        auth_provider_id=current.sub,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


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
    user = _get_or_create_user(session, current)
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
    user = _get_or_create_user(session, current)
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
