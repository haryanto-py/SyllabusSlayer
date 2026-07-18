"""Database engine + session management (SQLModel)."""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Create tables. Fine for local/SQLite dev; use Alembic migrations for prod.

    NOTE: create_all only creates MISSING tables — it never ALTERs existing ones. When a
    model gains a column (e.g. M5.3 added StudentProgress.meta_currency + unlocked_relics and
    the SessionStatus.defeated value), a FRESH dev SQLite DB picks it up automatically, but an
    existing dev.db must be deleted/recreated, and Supabase Postgres prod needs a real migration:
        ALTER TABLE student_progress ADD COLUMN meta_currency INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE student_progress ADD COLUMN unlocked_relics JSONB;
    (SessionStatus is stored as a plain string column, so no enum-type migration is required.)
    """
    # Import models so they register on SQLModel.metadata before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
