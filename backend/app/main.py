"""SyllabusSlayer FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import init_db
from app.routers import health, student, teacher


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create any missing tables on startup (idempotent) — works for SQLite (dev) and
    # Postgres (prod). Introduce Alembic migrations later for richer schema changes.
    init_db()
    yield


app = FastAPI(title="SyllabusSlayer API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(teacher.router)
app.include_router(student.router)


@app.get("/")
def root() -> dict:
    return {"name": "SyllabusSlayer API", "docs": "/docs"}
