"""Application settings, loaded from environment / .env (see backend/.env.example)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]  # .../backend
_REPO_ROOT = _BACKEND_DIR.parent  # repo root (holds the shared .env)


class Settings(BaseSettings):
    # Load the shared repo-root .env first, then backend/.env (which, if present,
    # overrides root). Real environment variables still take precedence over both.
    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT / ".env"), str(_BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- environment ---
    env: str = "dev"  # dev | prod

    # --- database ---
    # Local dev defaults to SQLite; prod uses the Supabase Postgres connection string.
    database_url: str = "sqlite:///./syllabusslayer.db"

    # --- Supabase (auth + storage) ---
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None  # used to verify auth JWTs (HS256)
    supabase_service_key: str | None = None  # server-side storage/admin ops
    supabase_storage_bucket: str = "uploads"

    # --- OpenAI (model ids are pinned here; RE-VERIFY against the pricing page) ---
    openai_api_key: str | None = None
    openai_model_heavy: str = "gpt-5.4"          # boss/question authoring
    openai_model_mini: str = "gpt-5.4-mini"      # lighter authoring
    openai_model_nano: str = "gpt-5.4-nano"      # mechanical helpers
    openai_model_escalation: str = "gpt-5.5"     # hard chapters
    openai_embedding_model: str = "text-embedding-3-small"

    # --- Ingestion ---
    # "markitdown" (default, reliable/low-memory) | "docling" (richer structure but OOMs
    # on large PDFs on a 16GB/no-GPU box) | "auto" (docling, fall back to markitdown).
    ingestion_parser: str = "markitdown"

    # --- RAG ---
    # If a section's token count exceeds this, use retrieval; else direct long-context.
    rag_token_threshold: int = 100_000
    # If the whole document exceeds this, build the outline from per-chunk summaries
    # (a map step) instead of raw text, so oversized uploads stay within the input budget.
    outline_token_budget: int = 50_000

    # --- CORS ---  (teacher app :3000, student app :3001)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]


settings = Settings()
