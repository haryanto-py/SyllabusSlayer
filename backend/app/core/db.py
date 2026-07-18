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
    """Ensure the schema exists.

    Dev/tests (SQLite): ``create_all`` for zero-friction setup. PROD: schema is owned by
    versioned **Alembic migrations** (``alembic upgrade head``, run at deploy — see the Docker
    CMD), so this is a no-op. That's the right split: ``create_all`` only creates MISSING tables
    (it never ALTERs existing ones), whereas migrations handle column/enum changes safely on the
    live Supabase Postgres DB. To evolve the schema: edit the models, then
    ``uv run alembic revision --autogenerate -m "..."`` and commit the migration.
    """
    if settings.env == "prod":
        return  # migrations own the schema in prod
    # Import models so they register on SQLModel.metadata before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
