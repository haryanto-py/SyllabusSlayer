# SyllabusSlayer — Progress Tracker

Small, committed increments so work survives a mid-session cutoff. Tick items as they land; each ticked item = a commit.

## Done: M4 — polish + deploy ✅  (deploy-ready — live deploy is your Render/Vercel step; see docs/DEPLOY.md)

- [x] **T1. Backend prod-readiness** — DONE. `backend/Dockerfile` + `.dockerignore`; MarkItDown in base deps (Docling now `--extra docling`); tables created on Postgres at startup; binds `$PORT`; CORS via env; `ENV=prod` disables the dev shim. `render.yaml` blueprint.
- [x] **T2. Deploy docs** — DONE. `docs/DEPLOY.md` (Supabase Postgres URL + auth URLs, Render blueprint, Vercel × 2 apps, all env vars, smoke test) + README polish.
- [x] **T3. Verify** — 22 backend tests pass, ruff clean, both apps `next build` clean. *(Local `docker build` not run — Docker Desktop down; Render builds the image.)*

## Done: M3 — LMS + dashboard ✅

Real Supabase auth (T6) is wired; the dev `X-Dev-Role` shim remains only as a no-token fallback.

- [x] **T1. Classes + enrollment (backend)** — DONE. Teacher: `POST/GET /teacher/classes`, `GET /teacher/classes/{id}` (roster); student: `POST /student/classes/join` (by code, idempotent), `GET /student/classes`. Unambiguous 6-char join codes. Dev shim extended with `X-Dev-User` (multi-user sim); DRYed user upsert into `services/users.py`. 21 tests pass.
- [x] **T2. Assignments (backend)** — DONE. `POST/GET /teacher/classes/{id}/assignments`; `GET /student/assignments`; play `start` accepts `assignment_id`.
- [x] **T3. Teacher review/edit (backend)** — DONE. `GET /teacher/campaigns` (list); `PUT /teacher/campaigns/{id}/questions/{qid}` (schema-validated edit + recompute encounter combat); `POST /teacher/campaigns/{id}/publish`. *(UI in T5.)*
- [x] **T4. Dashboard analytics (backend)** — DONE. `services/analytics.py` + `GET /teacher/campaigns/{id}/analytics?class_id=` → per-student, per-topic mastery, item p-values, completion summary. *(UI in T5.)*
- [x] **T5. App pages** — DONE. Teacher app: `/classes` (list+create), `/classes/[id]` (roster, assign, inline dashboard), `/campaigns` (list), `/campaigns/[id]` (review: edit prompt/options/correct/explanation + publish). Student app: join-by-code + assigned-games list (`MyGames`). Both apps `next build` clean.
- [x] **T6. Real Supabase auth** — DONE. Backend verifies Supabase JWTs via **JWKS** (ES256/RS256), role from `user_metadata`; dev shim is now only a no-token fallback. Frontend: `AuthGate` (email+password login/signup, role set per app) + `authHeaders` attaches the token to every API call. Both apps build. *(Live browser login is the user's final check; may require disabling "Confirm email" in Supabase for a frictionless demo.)*

## Done: M2 — play one game (student client) ✅

- [x] **T1. Student play API + scoring (backend)** — DONE. `services/scoring.py` (redact_game, check_answer for all 6 types, streak/damage/XP/level); `routers/student.py` endpoints `POST /student/play/{campaign_id}/start` (returns redacted game + combatConfig + session), `/play/{session_id}/answer` (server-checks, persists `QuestionAttempt`, returns verdict + HP/streak/XP/score + explanation/citation), `/play/{session_id}/finish`. `PlaySession.campaign_id` added (nullable). 20 tests pass incl. a full play-flow API test.
- [x] **T2. Combat engine (shared/client)** — DONE. `apps/student/src/lib`: `types.ts` (redacted play types), `play.ts` (start/answer/finish client), `combatStore.ts` (Zustand phase machine: presenting → feedback → advance → victory/defeat, driven by server verdicts). Decision: Zustand phase machine over XState for M2 (spec-blessed pragmatic start); graduate later if relics/phases grow.
- [x] **T3. Combat UI (student app)** — DONE. `components/Combat.tsx` (boss panel + animated HP bars, player HUD, question cards for all 6 types, feedback with explanation + source citation, victory/defeat screens) via Motion; `/play/[campaignId]` route; `JoinForm` on the landing. `next build` passes.
- [x] **T4. Verify** — DONE. 20 backend tests (scoring units + play-flow API). Real-path live check: `X-Dev-Role` student auth, redacted game, start → correct answer (+10 dmg) → finish; teacher → /student = 403. Student app builds. (Dev auth shim `X-Dev-Role`; real Supabase auth in M3.)

## Done: M1.2 — RAG context + Docling ingestion

- [x] **T1. Ingestion parser decision** — DONE. Docling installs & extracts real headings (57 on the PDF), BUT its preprocess stage OOMs (`std::bad_alloc`) on ~20 of ~80 pages on this 16GB/no-GPU box and silently drops them (only 6k of 30k tokens survived). MarkItDown extracts the full 30,267 tokens reliably (no headings). **Default = `markitdown`**; config `ingestion_parser` = markitdown | docling | auto (auto = Docling then MarkItDown fallback on partial). Docling viable only on bigger hardware or small docs → RAG context (T2/T3) is what makes the structureless MarkItDown output work well.
- [x] **T2. Embed + store chunks on ingestion** — DONE. `embeddings.embed_texts_with_usage`; the upload endpoint chunks + embeds + persists `Chunk` rows (best-effort — stores text without vectors if embedding fails). Verified via stubbed API test.
- [x] **T3. Per-encounter retrieval context** — DONE. `services/retrieval.py` (`build_index`/`search`). `build_game` uses matching section context first (free for structured docs), else lazily builds an index and retrieves top-5 chunks per encounter. **PDF result (3 enc): input 124.8k→81.2k tokens, cost $0.094→$0.036, grounding 80%→100%** (per-encounter question input ~10× smaller; ~6× cheaper at full scale).
- [x] **T4. Large-document handling** — DONE. `generation.summarize_for_outline` maps the doc in token-windows (`_complete`, plain-text); `build_game` outlines from the digest when doc tokens > `outline_token_budget` (default 50k). Questions still retrieve from full content (T3). Verified by forcing budget=15k on the 30k PDF: digest → outline → game, 100% grounded.
- [x] **T5. Verify + tests + commit** — DONE. 16 tests pass, ruff clean. cell-biology regression: section path (no embeddings), $0.026, 100% grounded. PDF map-step: $0.041, 100% grounded, no duplicates.

## Milestones
- [x] M0 — scaffold (monorepo: teacher/student apps + shared pkg; FastAPI backend)
- [x] M1 — AI pipeline (ingestion → Structured Outputs → combat tuning → evals); verified live
- [x] M1.1 — outline dedup + large-doc cap fixes; verified on real Korean PDF
- [x] M1.2 — RAG context + Docling (parser config, chunk store, per-encounter retrieval, large-doc map step)
- [x] M2 — play one game (student combat client + server-authoritative play API)
- [x] M3 — LMS + dashboard (classes / enroll / assign / review / analytics + app pages + real Supabase auth via JWKS)
- [x] M4 — polish + deploy (Docker + render.yaml + DEPLOY.md; deploy-ready — live deploy is the user's dashboard step)
- [ ] **M5 — make it a game** (research done → `docs/GAME-FEEL-RESEARCH.md`). Phases: **M5.1 run map ✅** · M5.2 relics + reward choice · M5.3 meta-progression + permadeath · M5.4 Phaser canvas arena + juice · M5.5 polish. **Do structure (M5.1–M5.3) before canvas (M5.4).**
  - M5.1 DONE: backend `runmap.build_act_map` (deterministic layered DAG, attached per act + injected at serve-time for old campaigns); student client refactored to **map navigation** (Zustand phases map→presenting→feedback→map; boss node clears the act) + `MapView` (pick your path). Both apps build; 24 tests pass.

## Notes / constraints
- OpenAI budget ~$5 total; ~$0.15 spent. Use `gpt-5.4-nano` (outline) + `gpt-5.4-mini` (questions); avoid `gpt-5.4`/`5.5`/`pro`. `gpt-4o-mini` available as a stable fallback (not needed so far).
- Copyrighted test PDF + its derived game JSON are gitignored (local only).
- Run: backend `cd backend && uv run uvicorn app.main:app --reload`; tests `uv run pytest -q`; live `uv run python scripts/m1_demo.py [PATH]`.
