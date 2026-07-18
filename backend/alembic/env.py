"""Alembic environment for SyllabusSlayer.

Targets ``SQLModel.metadata`` (all tables from ``app.models``) and takes the connection URL from
the app's own settings, so ``alembic upgrade head`` uses the same DATABASE_URL as the running API
(SQLite in dev, Supabase Postgres in prod). ``render_as_batch`` is enabled so ALTER TABLE works on
SQLite too, which lets the same migrations run against both backends.
"""

from logging.config import fileConfig

from sqlmodel import SQLModel
from sqlalchemy import engine_from_config, pool

from alembic import context

# Import the app settings + register every model on SQLModel.metadata before autogenerate.
from app.core.config import settings
from app import models  # noqa: F401  (side-effect: populates SQLModel.metadata)

config = context.config

# Use the application's configured database URL (env / .env), not a hard-coded ini value.
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit SQL for a migration without a live DB connection (``alembic upgrade --sql``)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # batch mode → ALTER TABLE support on SQLite
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
