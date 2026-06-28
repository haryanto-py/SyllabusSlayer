# SyllabusSlayer 🗡️📚

> Upload a syllabus, get a roguelike. **SyllabusSlayer** is an AI pipeline that turns a teacher's own learning resources into a **roguelike quiz-RPG** — students battle topic "bosses" where correct answers deal damage, streaks multiply, and wrong answers cost HP — wrapped in a lightweight LMS (create → review → assign → monitor).

An AI-Engineer portfolio project. The headline isn't "generate a quiz from a PDF" (that's commodity) — it's **source-grounded, cited questions**, a **syllabus-mapped roguelike campaign**, a real **teacher LMS loop**, and a visible **eval/guardrail harness**.

## Architecture

```
Next.js (Vercel)  ──HTTPS+JWT──▶  FastAPI (Render)  ──▶  OpenAI (Structured Outputs, Batch API)
  React+Tailwind                   ingestion · generation        ──▶  Supabase (Postgres+pgvector,
  +Motion+XState+Zustand           combat-tuning · evals               Auth, Storage)
```

- **Game client:** plain React + Tailwind + **Motion** + **XState** + **Zustand** (no canvas engine — combat is turn-based/UI-driven).
- **Game data:** the LLM generates the *pedagogical* layer via **OpenAI Structured Outputs** (a flat discriminated-union `Question`, generated outline → per-encounter batches); the backend computes the *combat tuning* (HP/damage/XP) deterministically.
- **Ingestion:** **Docling** (MIT) → Markdown + section tree; **RAG** (text-embedding-3-small + **pgvector**) gated behind a `tiktoken` size check.
- **Infra (decided):** Supabase (DB+Auth+Storage) · Render (API) · RAG in v1.

📄 **Full build spec:** [`docs/BUILD-SPEC.md`](docs/BUILD-SPEC.md) · raw research: [`docs/research/recovered-findings.json`](docs/research/recovered-findings.json)

## Repo layout

```
SyllabusSlayer/
├── backend/            # FastAPI + SQLModel (the AI pipeline + LMS API)
│   └── app/
│       ├── core/       # config, db, security (Supabase JWT)
│       ├── models/     # SQLModel tables (the data model)
│       ├── schemas/    # Pydantic — incl. the AI-generated game schema
│       ├── routers/    # API endpoints
│       └── services/   # ingestion, generation, evals, scoring (M1+)
├── frontend/           # Next.js client (scaffolded next)
└── docs/               # build spec + research
```

## Quickstart — backend

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). On this machine use `py`/`uv`.

```bash
cd backend
cp .env.example .env          # defaults run on SQLite, no secrets needed
uv sync                       # base deps (add --extra ingestion for Docling later)
uv run uvicorn app.main:app --reload
# → http://localhost:8000/docs   ·   GET /health
```

## Status

- ✅ **M0 — Scaffold:** backend skeleton, data model, game-content schema, health endpoint.
- ⬜ **M1 — Ingestion + generation** · ⬜ **M2 — Play one game** · ⬜ **M3 — LMS + dashboard** · ⬜ **M4 — Polish + deploy**

See the roadmap in [`docs/BUILD-SPEC.md`](docs/BUILD-SPEC.md) §9.

> ⚠️ OpenAI model ids/prices and host free-tiers in the spec are research-current (mid-2026) — re-verify before committing budget. Model ids are pinned in `backend/.env`.
