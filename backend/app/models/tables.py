"""SQLModel tables for SyllabusSlayer (see docs/BUILD-SPEC.md §6.1).

The generated game spec is stored as a JSON blob on ``Campaign.game_json`` rather
than normalised into rows -- it is generated-and-cached content queried as a whole.
``question_id`` / ``encounter_id`` on attempts are string IDs *inside* that blob.

NOTE on embeddings: for cross-DB local dev this scaffold stores ``Chunk.embedding``
as JSON (list[float]). When targeting Supabase Postgres, switch this column to a
pgvector ``Vector(1536)`` via an Alembic migration so retrieval can use ANN search.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class UserRole(str, Enum):
    teacher = "teacher"
    student = "student"


class DocumentStatus(str, Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    parsed = "parsed"
    failed = "failed"


class CampaignStatus(str, Enum):
    draft = "draft"
    generating = "generating"
    ready = "ready"
    published = "published"


class SessionStatus(str, Enum):
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
class User(SQLModel, table=True):
    __tablename__ = "users"
    id: str = Field(default_factory=_uuid, primary_key=True)
    email: str = Field(index=True, unique=True)
    role: UserRole = Field(default=UserRole.student)
    display_name: str
    auth_provider_id: str | None = Field(default=None, index=True)  # Supabase user id
    created_at: datetime = Field(default_factory=_now)


class Class(SQLModel, table=True):
    __tablename__ = "classes"
    id: str = Field(default_factory=_uuid, primary_key=True)
    teacher_id: str = Field(foreign_key="users.id", index=True)
    name: str
    join_code: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=_now)


class Enrollment(SQLModel, table=True):
    __tablename__ = "enrollments"
    id: str = Field(default_factory=_uuid, primary_key=True)
    class_id: str = Field(foreign_key="classes.id", index=True)
    student_id: str = Field(foreign_key="users.id", index=True)
    joined_at: datetime = Field(default_factory=_now)


class Document(SQLModel, table=True):
    __tablename__ = "documents"
    id: str = Field(default_factory=_uuid, primary_key=True)
    owner_id: str = Field(foreign_key="users.id", index=True)
    filename: str
    storage_url: str
    mime: str
    status: DocumentStatus = Field(default=DocumentStatus.uploaded)
    parsed_markdown: str | None = Field(default=None, sa_column=Column(Text))
    section_tree: dict | None = Field(default=None, sa_column=Column(JSON))
    token_count: int | None = None
    created_at: datetime = Field(default_factory=_now)


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"
    id: str = Field(default_factory=_uuid, primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    ord: int
    text: str = Field(sa_column=Column(Text))
    page: int | None = None
    section: str | None = None
    # TODO(prod): switch to pgvector Vector(1536) on Supabase Postgres.
    embedding: list[float] | None = Field(default=None, sa_column=Column(JSON))


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"
    id: str = Field(default_factory=_uuid, primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    teacher_id: str = Field(foreign_key="users.id", index=True)
    title: str
    status: CampaignStatus = Field(default=CampaignStatus.draft)
    game_json: dict | None = Field(default=None, sa_column=Column(JSON))
    combat_config: dict | None = Field(default=None, sa_column=Column(JSON))
    schema_version: str = "1.0.0"
    created_at: datetime = Field(default_factory=_now)


class Assignment(SQLModel, table=True):
    __tablename__ = "assignments"
    id: str = Field(default_factory=_uuid, primary_key=True)
    campaign_id: str = Field(foreign_key="campaigns.id", index=True)
    class_id: str = Field(foreign_key="classes.id", index=True)
    assigned_at: datetime = Field(default_factory=_now)
    due_at: datetime | None = None
    settings: dict | None = Field(default=None, sa_column=Column(JSON))


class PlaySession(SQLModel, table=True):
    __tablename__ = "play_sessions"
    id: str = Field(default_factory=_uuid, primary_key=True)
    # M2 plays a campaign directly; M3 will link an assignment. Both nullable for now.
    assignment_id: str | None = Field(default=None, foreign_key="assignments.id", index=True)
    campaign_id: str | None = Field(default=None, foreign_key="campaigns.id", index=True)
    student_id: str = Field(foreign_key="users.id", index=True)
    status: SessionStatus = Field(default=SessionStatus.in_progress)
    started_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    final_score: int | None = None
    final_xp: int | None = None
    hp_remaining: int | None = None
    bonus_max_hp: int = 0  # from relics (max HP = combatConfig.playerStartingHp + this)
    relics: list | None = Field(default=None, sa_column=Column(JSON))  # owned relic ids
    run_seed: str | None = None


class QuestionAttempt(SQLModel, table=True):
    __tablename__ = "question_attempts"
    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="play_sessions.id", index=True)
    question_id: str  # id within Campaign.game_json
    encounter_id: str
    is_correct: bool
    selected_answer: dict | None = Field(default=None, sa_column=Column(JSON))
    time_ms: int | None = None
    damage_dealt: int | None = None
    streak_at_time: int | None = None
    attempted_at: datetime = Field(default_factory=_now)


class StudentProgress(SQLModel, table=True):
    __tablename__ = "student_progress"
    id: str = Field(default_factory=_uuid, primary_key=True)
    student_id: str = Field(foreign_key="users.id", index=True)
    campaign_id: str = Field(foreign_key="campaigns.id", index=True)
    level: int = 1
    total_xp: int = 0
    mastery_by_topic: dict | None = Field(default=None, sa_column=Column(JSON))
    relics: list | None = Field(default=None, sa_column=Column(JSON))
    best_score: int | None = None
    updated_at: datetime = Field(default_factory=_now)
