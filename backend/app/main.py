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
    # Dev/SQLite: create tables on startup. Prod uses Alembic migrations.
    if settings.database_url.startswith("sqlite"):
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
