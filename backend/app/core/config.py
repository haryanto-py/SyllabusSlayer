"""Application settings, loaded from environment / .env (see backend/.env.example)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # --- RAG ---
    # If a section's token count exceeds this, use retrieval; else direct long-context.
    rag_token_threshold: int = 100_000

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
