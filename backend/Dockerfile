# SyllabusSlayer backend — FastAPI, managed with uv.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install base deps first (cached layer). --no-dev excludes pytest/ruff; Docling is an
# optional extra and is intentionally NOT installed (heavy + not needed in prod).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App code + Alembic migrations, then install the project itself
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
RUN uv sync --frozen --no-dev

EXPOSE 8000
# Apply DB migrations (idempotent — no-ops when already at head) before serving.
CMD ["sh", "-c", "uv run --frozen --no-dev alembic upgrade head && uv run --frozen --no-dev uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
