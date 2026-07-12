# SyllabusSlayer 🗡️📚

> Upload a syllabus, get a roguelike. **SyllabusSlayer** is an AI pipeline that turns a teacher's own learning resources into a **roguelike quiz-RPG** — students battle topic "bosses" where correct answers deal damage, streaks multiply, and wrong answers cost HP — wrapped in a lightweight LMS (create → review → assign → monitor).

An AI-Engineer portfolio project. The headline isn't "generate a quiz from a PDF" (that's commodity) — it's **source-grounded, cited questions**, a **syllabus-mapped roguelike campaign**, a real **teacher LMS loop**, and a visible **eval/guardrail harness**.

## Why it's different

Two camps dominate this space; SyllabusSlayer sits in the gap between them:
- **Classroom quiz-games** (Kahoot, Quizizz, Blooket) — arcade skins over a shared question set; generic AI, no source grounding.
- **AI quiz generators** (Quizgecko, Conker, MagicSchool) — turn a doc into a *static* quiz; no game, no monitoring.

It occupies the intersection none of them do: **the teacher's own materials → source-grounded, *verified* questions → a real roguelike run mapped to the syllabus → a teacher review/assign/monitor loop.**

**The AI-engineering that makes it credible:**
- **Grounded generation + a verification guardrail.** Every question stores a verbatim `sourceQuote` (+ chunk id & page); an eval pass (`services/evals.py`) checks the quote is actually in the source and flags hallucinations. *Sample run (cell biology): 20 questions, **100% source-grounded**, **~$0.025**.*
- **A pipeline, not a prompt.** Two-layer design — the LLM writes only the *pedagogy* via **Structured Outputs**; the backend deterministically owns HP/damage/XP so balance can't be hallucinated. Staged generation (outline → per-encounter), per-encounter **retrieval** for focused/cheap context, a map-reduce fallback for large docs, and model tiering for cost.
- **Assessment integrity.** The game served to a student is **redacted** (no answers); correctness is checked **server-side**; every attempt is persisted.
- **Human-in-the-loop.** Teachers **review/edit** AI questions before publishing — nothing auto-assigns unreviewed content.

**Where to look:** AI core → `backend/app/services/{generation,evals,scoring,retrieval,runmap}.py` · LLM output contract → `backend/app/schemas/game.py` · research & decisions → [`docs/BUILD-SPEC.md`](docs/BUILD-SPEC.md), [`docs/GAME-FEEL-RESEARCH.md`](docs/GAME-FEEL-RESEARCH.md).

## Architecture

```
Next.js (Vercel)  ──HTTPS+JWT──▶  FastAPI (Render)  ──▶  OpenAI (Structured Outputs)
  React+Tailwind                   ingestion · generation        ──▶  Supabase (Postgres,
  +Motion+Zustand (run map)        combat-tuning · evals · scoring     Auth)
```

- **Game client:** React + Tailwind + **Motion** + a **Zustand** phase machine (turn-based, UI-driven) — students navigate a branching **run map**; a Phaser/Pixi canvas battle arena is planned (M5.4).
- **Game data:** the LLM generates the *pedagogical* layer via **OpenAI Structured Outputs** (a flat discriminated-union `Question`, generated outline → per-encounter batches); the backend computes the *combat tuning* (HP/damage/XP) deterministically.
- **Ingestion:** **MarkItDown** (default, light) / Docling (optional) → Markdown + section tree; **retrieval** (text-embedding-3-small) supplies focused per-encounter context, gated by a `tiktoken` size check.
- **Auth:** Supabase email+password; tokens verified server-side via **JWKS**. **Infra:** Supabase Postgres · Render (API) · Vercel (apps).

📄 **Full build spec:** [`docs/BUILD-SPEC.md`](docs/BUILD-SPEC.md) · raw research: [`docs/research/recovered-findings.json`](docs/research/recovered-findings.json)

## Repo layout

npm workspaces monorepo: teacher and student are **separate Next.js apps** sharing one package; the backend is a **single modular FastAPI service** (teacher/student isolated by RBAC routers).

```
SyllabusSlayer/
├── apps/
│   ├── teacher/        # Next.js — upload, review, assign, dashboard
│   └── student/        # Next.js — the roguelike game
├── packages/
│   └── shared/         # Zod game schema, API client, types (one source of truth)
├── backend/            # FastAPI + SQLModel (the AI pipeline + LMS API)
│   └── app/
│       ├── core/       # config, db, security (Supabase JWT + RBAC deps)
│       ├── models/     # SQLModel tables (the data model)
│       ├── schemas/    # Pydantic — incl. the AI-generated game schema
│       ├── routers/    # health, teacher (RBAC), student (RBAC)
│       └── services/   # ingestion, generation, evals, scoring (M1+)
├── docs/               # build spec + research
└── package.json        # npm workspaces root
```

## Quickstart — backend

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). On this machine use `py`/`uv`.

```bash
cd backend
cp .env.example .env          # defaults run on SQLite, no secrets needed
uv sync                       # base deps incl. MarkItDown parser (add --extra docling for Docling)
uv run uvicorn app.main:app --reload
# → http://localhost:8000/docs   ·   GET /health
```

## Quickstart — frontend (monorepo)

```bash
npm install              # from repo ROOT — installs both apps + shared package
npm run dev:teacher      # teacher app  → http://localhost:3000
npm run dev:student      # student app  → http://localhost:3001
# build both: npm run build
```
Each app needs a git-ignored `.env.local` with `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, and `NEXT_PUBLIC_API_URL`. Sign-up / login is required (Supabase email + password).

## Status

- ✅ **M0** scaffold (monorepo + backend) · ✅ **M1** AI generation pipeline (ingestion → Structured Outputs → combat tuning → evals; ~$0.025/game, source-grounded) · ✅ **M1.2** RAG per-encounter context · ✅ **M2** playable student combat (server-authoritative scoring) · ✅ **M3** LMS — classes, enrollment, assignments, review/edit, dashboard analytics + **Supabase auth (JWKS)** · ✅ **M4** deploy-ready (Docker + Render + Vercel) · 🔧 **M5** make it a game (**M5.1 run map ✅**; relics → meta-progression → Phaser canvas arena next).
- **Deploy:** [`docs/DEPLOY.md`](docs/DEPLOY.md) — Vercel (2 apps) + Render (`render.yaml` + `backend/Dockerfile`) + Supabase.
- Run the live generation pipeline: `cd backend && uv run python scripts/m1_demo.py` (needs `OPENAI_API_KEY` in the root `.env`).

Roadmap + progress: [`docs/BUILD-SPEC.md`](docs/BUILD-SPEC.md) §9 and [`docs/PROGRESS.md`](docs/PROGRESS.md).

> ⚠️ OpenAI model ids/prices and host free-tiers in the spec are research-current (mid-2026) — re-verify before committing budget. Model ids are pinned in `backend/.env`.
