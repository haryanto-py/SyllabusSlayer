# SyllabusSlayer — Build Spec & Research Report

> **What this is:** the consolidated research + architecture spec for SyllabusSlayer — an AI-Engineer portfolio project where a teacher uploads learning resources and an AI pipeline turns them into a **roguelike quiz-RPG**, wrapped in a lightweight LMS (create → review → assign → monitor).
>
> **Locked decisions:** FastAPI (Python) backend · Next.js (React/TS) frontend · OpenAI for generation · cloud-only inference (dev machine has no GPU) · cheap/free-tier hosting · "balanced product" (polished product *and* real AI engineering).

> ⚠️ **Provenance & confidence.** Dimensions 1–5 below come from web-backed research agents with primary-source citations (see Sources). Dimension 6 (LMS architecture) was authored from first-principles expertise because its research agent was cut off by a usage limit. The final **adversarial cross-verification pass did not run** (also cut off). **Therefore: treat all OpenAI model names, per-token prices, and hosting free-tier limits as "research-current, re-verify before committing budget."** Pin model IDs in config behind an env var; the pricing page is the source of truth. Everything architectural (framework choice, schema design, data model, pipeline shape) is stable regardless of pricing drift.

---

## 1. Executive summary

- **Don't use a game engine.** The combat is turn-based and question-driven — build the client as **plain React + Tailwind + Motion (ex-Framer Motion)**, with combat modeled as a deterministic **XState** state machine over a **Zustand** store. SSR-safe, tiny, accessible, testable. Add a lazy **PixiJS/tsParticles** "boss FX" canvas only later, if you crave spectacle.
- **Two-layer game data.** Split content into a **pedagogical layer** (LLM-generated via OpenAI **Structured Outputs**) and a **combat-tuning layer** (HP/damage/XP **computed deterministically by the backend**). The LLM never invents balance numbers — it fills questions + difficulty/Bloom tags + source citations.
- **Schema = discriminated-union questions + staged generation.** A flat `Question` object tagged by `questionType`, generated in two passes (outline → per-encounter question batches) to stay under Structured Outputs' **100-property / 5-level** limits. Mirror with **Pydantic** (backend) and **Zod** (frontend).
- **Parse-first, RAG-optional.** Use **Docling** (MIT, all formats + OCR) to normalize uploads to Markdown; feed cleaned text straight into generation. Add retrieval (**text-embedding-3-small** + **pgvector**) only when a doc exceeds your per-call token budget, or as a deliberate showcase — gated by a `tiktoken` size check.
- **The differentiator is grounding + evals, not generation.** "Generate a quiz from a PDF" is commodity (Quizizz/Quizgecko/StudyQuest already do it). Win on: **source-grounded, cited questions** + a **true roguelike campaign mapped to the syllabus** + the **teacher review/assign/monitor LMS loop** + a visible **eval harness** (groundedness, single-answer, distractor quality).
- **Keep it cheap and async.** Generate **per-chapter** via the **Batch API** (50% off); cache the game spec so OpenAI cost is *one-time per upload* (low tens of cents per game). Defer live multiplayer — the roguelike is single-player async; poll for dashboard updates.

---

## 2. Recommended architecture

```
                        ┌──────────────────────────────────────────────┐
                        │                 Next.js (Vercel)              │
   Teacher / Student ──▶│  - Teacher: upload, review/edit, assign,      │
        (browser)       │    dashboard (mastery heatmap, at-risk)       │
                        │  - Student: join code, play roguelike,        │
                        │    React + Tailwind + Motion + XState/Zustand │
                        └───────────────┬──────────────────────────────┘
                                        │  HTTPS (JWT from Supabase Auth)
                                        ▼
                        ┌──────────────────────────────────────────────┐
                        │              FastAPI backend                  │
                        │  routers ▸ services ▸ models(SQLModel)        │
                        │  - /auth (verify Supabase JWT, RBAC)          │
                        │  - /documents (upload → parse job)            │
                        │  - /campaigns (generate, review/edit)         │
                        │  - /play (sessions, attempts, scoring)        │
                        │  - /analytics (dashboard aggregations)        │
                        │  ingestion(Docling) │ generation(OpenAI)      │
                        │  combat-tuning(deterministic) │ evals         │
                        └──────┬───────────────┬───────────────┬────────┘
                               │               │               │
                   ┌───────────▼───┐   ┌───────▼────────┐  ┌───▼────────────┐
                   │ Supabase      │   │ OpenAI API     │  │ Supabase       │
                   │ Postgres      │   │ - Structured   │  │ Storage        │
                   │ (+ pgvector)  │   │   Outputs      │  │ (uploaded      │
                   │ + Auth        │   │ - Batch API    │  │  files)        │
                   └───────────────┘   │ - embeddings   │  └────────────────┘
                                       └────────────────┘
```

**Data flow:** Teacher logs in (Supabase Auth → JWT) and uploads a file → FastAPI stores it in Supabase Storage and kicks a **background parse** (Docling → Markdown + section tree) → on parse-complete, a **generation** job runs per-chapter via OpenAI Structured Outputs (Batch API), and the backend **computes combat tuning** and assembles the campaign JSON → teacher **reviews/edits** generated questions, then **assigns** the campaign to a class → students join by code, **play** the roguelike (each answer POSTs an attempt; scoring/XP computed server-side or in the pure domain layer) → the teacher **dashboard** aggregates attempts into mastery/at-risk analytics.

---

## 3. Game framework decision

**Decision: plain React + Tailwind + Motion. No canvas game engine for the primary client.** All five candidates (Phaser 4, PixiJS v8, KAPLAY, Excalibur, Motion) are MIT and actively maintained in 2026 — the call is *fit*, not licensing. SyllabusSlayer's "combat" is a reactive, text-heavy, turn-based UI (read question → pick/type answer → animated feedback), which is exactly what React + a state machine models cleanly and exactly what a 60fps canvas render loop is wasteful for. Bonus: HTML stays **accessible** (real concern for a school LMS) and **SSR-friendly**, the bundle stays tiny, and combat logic stays **unit-testable** (feeds the evals story).

**Why not the engines (short version):**

| Option | Verdict | Reason |
|---|---|---|
| **React + Tailwind + Motion** ✅ | **Chosen** | Zero impedance mismatch with turn-based UI; SSR-safe; accessible; ~4.6KB initial via `LazyMotion`+`m`; testable. |
| Phaser 4 | Overkill | Full game framework + WebGL loop; ~400–500KB; canvas UI hurts a11y; needs `ssr:false` + ref bridging. |
| PixiJS v8 | Secondary only | A *renderer*, not a framework — great as a lazy "boss FX" layer behind the HUD, not the whole UI. |
| KAPLAY | Avoid | Still on a `4000.x` **alpha** line — API-churn risk for a showcase. |
| Excalibur.js | Avoid | Still **pre-1.0**; maintainers warn of breaking changes; tree-shaking immature. |

**How it wires into Next.js (App Router):** the combat UI is plain React → render it directly in a `'use client'` component, **no `ssr:false` hack needed**. Reserve the dynamic-import-`ssr:false` wrapper pattern *only* for any genuinely browser-only layer (e.g. an optional PixiJS/tsParticles FX canvas): make `BossFxCanvas.tsx`, then a thin `'use client'` wrapper `const BossFxCanvasNoSSR = dynamic(() => import('./BossFxCanvas'), { ssr:false })`, and import that with a Suspense fallback. Use Motion's `LazyMotion` + `m` to keep the animation bundle ~4.6KB instead of the full ~34KB `motion` component.

**How combat state is modeled (3 layers):**
1. **Domain layer** — a pure, framework-agnostic TS module: types (`Boss`, `Question`, `PlayerStats`, `Relic`) and pure reducers like `applyAnswer(state, answer) → {damage, hpDelta, streak, multiplier, events[]}`. Pure = unit-testable and reusable server-side for authoritative scoring.
2. **Orchestration layer** — an **XState** machine: `presentingQuestion → awaitingAnswer → resolving (guard: correct/incorrect) → applyingDamage → (bossDefeated | playerDown | nextQuestion) → rewardScreen`. Guards/parallel states map directly to streak multipliers, relic triggers, and "boss enrage" phases; the chart is an inspectable portfolio artifact.
3. **Store/UI binding** — **Zustand** (~3KB) holds the snapshot the React tree subscribes to; each XState transition emits `events[]` that the UI turns into **Motion `AnimatePresence`** animations (damage numbers, HP-bar tween, streak flash, level-up toast).

**Pragmatic start:** begin with a single Zustand store + a typed `dispatch(action)` reducer; graduate to full XState (or `@xstate/store`) once phases/relics make the implicit machine painful. **VFX escalation:** CSS/Motion for 90% of feedback; add `canvas-confetti` for victories and a lazy PixiJS/tsParticles boss canvas *only after* core combat ships.

---

## 4. The game content schema

**Core idea:** one schema per LLM call, generated in **two staged passes**, with a **flat discriminated-union `Question`** (all per-type fields present, `null` when unused — strict mode requires every field). Combat tuning is a **separate, backend-computed layer** the LLM never touches.

- **Stage 1 (outline):** one Structured Outputs call → `CampaignOutline` (campaign + acts + encounter **stubs**, no questions). Depth = `acts[].encounters[]` = 3 levels. Safe.
- **Stage 2 (per encounter):** one call per encounter → a `QuestionBatch`. Depth = `questions[].options[].text` = 3 levels. Safe.
- Backend **stitches by IDs** and **computes** `CombatConfig` / `EncounterCombat` / `Reward` deterministically.

### 4.1 Schema (Pydantic-style; mirror in Zod)

```python
# ---- ENUMS ----
QuestionType  = "multiple_choice" | "multi_select" | "true_false" | "short_answer" | "ordering" | "matching"
BloomLevel    = "remember" | "understand" | "apply" | "analyze" | "evaluate" | "create"   # Anderson/Krathwohl 2001
Difficulty    = "easy" | "medium" | "hard"
EncounterKind = "minion" | "elite" | "boss"
RewardKind    = "relic" | "powerup" | "xp" | "heal"

# ---- STAGE 1: CampaignOutline (LLM) ----
CampaignOutline:
  schemaVersion: str          # "1.0.0" (validate in code; SO won't enforce pattern)
  campaignId: str             # backend overwrites with UUID
  title: str
  description: str
  sourceDocumentId: str
  acts: list[ActStub]

ActStub:                      # one Act == one top-level syllabus topic
  actId: str
  order: int
  title: str
  syllabusTopic: str          # mapped chapter/heading from the source
  summary: str
  encounters: list[EncounterStub]

EncounterStub:                # boss/elite/minion, no questions yet
  encounterId: str
  order: int
  kind: EncounterKind
  title: str                  # "Mitochondria, the Powerhouse Boss"
  enemyName: str
  enemyFlavor: str            # short narrative blurb
  subTopic: str
  targetQuestionCount: int

# ---- STAGE 2: QuestionBatch (LLM, one call per encounter) ----
QuestionBatch:
  encounterId: str
  questions: list[Question]

# ---- THE DISCRIMINATED-UNION QUESTION (heart of the schema) ----
Question:
  questionId: str
  questionType: QuestionType          # discriminator
  bloomLevel: BloomLevel
  difficulty: Difficulty
  prompt: str
  # --- source grounding (REQUIRED on every item; powers evals/guardrails) ---
  sourceChunkIds: list[str]
  sourceQuote: str                    # verbatim snippet the item is grounded in
  sourcePage: int | null
  # --- feedback ---
  explanation: str
  hint: str | null
  # --- per-type clusters (exactly one cluster non-null per questionType) ---
  options: list[Option] | null            # multiple_choice, multi_select
  correctOptionIds: list[str] | null      # ids into options[]
  correctBoolean: bool | null             # true_false
  acceptedAnswers: list[str] | null       # short_answer
  caseSensitive: bool | null              # short_answer
  orderedItems: list[OrderedItem] | null  # ordering
  matchPairs: list[MatchPair] | null      # matching

Option:      { optionId: str, text: str }
OrderedItem: { itemId: str, text: str, order: int }     # order = correct 1-based position
MatchPair:   { pairId: str, left: str, right: str }      # right = correct counterpart
```

### 4.2 Combat / RPG tuning (computed by the backend, **not** the LLM)

```python
CombatConfig:                  # per campaign
  playerStartingHp: int                          # e.g. 100
  baseDamagePerCorrect: int                      # e.g. 10
  streakMultipliers: list[float]                 # [1.0, 1.25, 1.5, 2.0] by streak tier
  wrongAnswerHpCost: int                         # e.g. 8
  xpPerCorrectByDifficulty: {easy,medium,hard}   # {10, 20, 35}
  levelXpCurve: list[int]                         # cumulative thresholds

EncounterCombat:               # per encounter, derived
  enemyMaxHp: int              # ≈ Σ expectedDamage over questions, × kind multiplier
  enemyBaseDamage: int
  kindHpMultiplier: float      # minion 1.0 / elite 1.5 / boss 2.5

Reward:                        # authored catalog; backend assigns drops
  rewardId: str; kind: RewardKind; name: str; description: str; magnitude: int
```

### 4.3 Field reference (key fields)

| Field | Why it exists |
|---|---|
| `questionType` | Discriminator → exhaustive `switch` rendering in React; `Field(discriminator=...)` / `z.discriminatedUnion`. |
| `bloomLevel`, `difficulty` | Drive deterministic combat tuning + the dashboard's item analysis + prompt for a *spread* of cognitive levels. |
| `sourceChunkIds`, `sourceQuote`, `sourcePage` | **The differentiator.** Provenance per item → groundedness guardrail + "this came from slide 14" in the review/feedback UI. |
| `explanation` | In-game post-answer feedback + evidence for the grounding check. |
| per-type clusters (`options`, `correctOptionIds`, …) | All present, `null` when unused (strict mode). A post-parse validator asserts the right cluster is populated. |
| `schemaVersion` | Lets stored games survive schema evolution (enforce with a migration plan). |

### 4.4 Validation (Structured Outputs guarantees *shape*, not *content*)

Add a thin backend post-validation (Pydantic validators) + frontend `z.refine`:
1. exactly one correct answer; `correctOptionIds` in range; for the type, the right cluster is non-null & non-empty;
2. no duplicate/near-duplicate options;
3. **grounding check** — `sourceQuote` is a (fuzzy) substring of the referenced chunk; reject/flag fabrications;
4. **Bloom spread** across an encounter (not all `remember`);
5. on failure → bounded "fix only these problems" regeneration (≤2 retries). Log everything for the evals section.

**Standards borrowed for vocabulary only** (too heavy to adopt as wire formats): QTI 3.0 interaction types, H5P Question Set, Kahoot's flat question/choices model, GIFT, Twine/Ink for narrative flavor.

---

## 5. AI generation pipeline

### 5.1 Ingestion (parse-first)

- **Primary parser: Docling (IBM, MIT).** One library handles PDF/DOCX/PPTX/XLSX/HTML/images + built-in OCR, outputs Markdown/JSON, preserves reading order + headings + tables, **CPU-only** (fine without a GPU). Run it in a **FastAPI BackgroundTask/worker** so the slow ML parsing never blocks the request.
- **Fast path / fallback: MarkItDown (Microsoft, MIT)** for clean born-digital files.
- **Avoid PyMuPDF/pymupdf4llm as default** — it's **AGPL-3.0-or-commercial**; the AGPL network-use clause is a footgun if SyllabusSlayer is ever hosted/monetized. (Fastest for native PDFs, so OK only while the repo is genuinely open-source.)
- **OCR:** usually unnecessary as a separate stack — use Docling's integrated OCR, only on pages with no extractable text.
- **Normalize** to (a) full cleaned Markdown and (b) a **section/heading tree** — which doubles as your **campaign-map structure** (nice product/AI synergy).

### 5.2 RAG vs long-context — the decision rule

Measure the normalized Markdown with **`tiktoken`**:
- **If the material for one generation call (≈ one chapter → one boss) is under ~100K tokens → SKIP retrieval.** Pass the section's Markdown directly. Cheaper, easier to debug, *better* questions (model sees full context). Modern OpenAI context windows comfortably fit a single syllabus/chapter.
- **Add RAG only if:** (a) a single game's corpus exceeds your per-call token budget; (b) you want cross-doc citations; (c) you want a "student asks the tutor" chat over all course material; or (d) you explicitly want RAG on the résumé. **(d) is legitimate** — build it, but **gate it behind the size check** so the cheap path is used when it fits. *"I measured tokens and only paid for retrieval when it helped"* is itself the portfolio talking point.
- **When RAG is on:** chunk by syllabus section (~300–800 tokens, small overlap, keep section metadata) → embed with **`text-embedding-3-small`** (≈ $0.02/1M; ~half via Batch) → store in **pgvector in the same Postgres** (no second datastore to sync).

### 5.3 Structured generation (OpenAI)

- **Use Structured Outputs** (`response_format: {type:"json_schema", json_schema:{name, schema, strict:true}}`) for *every* call — constrained decoding guarantees schema-valid JSON, so you deserialize straight into Pydantic and skip JSON-repair loops. **Not** legacy JSON mode (no schema guarantee); **not** tool/function calling (that's for invoking app functions — reserve it for a future "regenerate this boss" agent feature).
- **Strict-mode constraints to respect:** root must be an object (no bare array — wrap as `{items:[...]}`); **every** property in `required`; `additionalProperties:false` on every object; optionals as a `null` union (`type:["string","null"]`); **no `default`**; **≤100 properties total, ≤5 nesting levels**, ≤500 enum values, ≤15K chars of names/defs/enums. `pattern`/`format`/`min`/`max`/`minItems` are **not enforced** → validate ranges in code. (These limits are exactly why we generate **per-chapter**, not whole-game-in-one-call.)
- The OpenAI Python SDK can take a **Pydantic model directly** (it generates the schema + sets strict). Keep a `schemaVersion` in every payload.

### 5.4 Model choice & cost *(⚠️ re-verify names/prices before launch — pin in config)*

Research-current (June 2026) lineup and per-1M-token pricing:

| Model | Input / Cached / Output (per 1M) | Use for |
|---|---|---|
| **gpt-5.5** (flagship) | $5.00 / $0.50 / $30.00 | Escalation for hard chapters / quality-critical authoring |
| **gpt-5.4** (workhorse) | $2.50 / $0.25 / $15.00 | Heavy generation: bosses + grounded, Bloom-varied question sets |
| **gpt-5.4-mini** | $0.75 / $0.075 / $4.50 | Question batches, lighter authoring |
| **gpt-5.4-nano** | $0.20 / $0.02 / $1.25 | Mechanical helpers: outline, Bloom-tagging, dedup, difficulty calibration |

- **Tiered routing:** nano for mechanical steps, gpt-5.4(-mini) for authoring, gpt-5.5 only to escalate. Set **reasoning effort low/none** on mechanical steps (hidden reasoning tokens bill as output).
- **Batch API** for the generation run: **flat 50% off** input *and* output, stacks with **prompt caching** (~90% off repeated system-prompt prefix). Generation isn't latency-sensitive (show a "building your game" state); keep a synchronous path for live demos.
- **Cost estimate:** a ~30-page doc (~15–20K tokens of text) → realistically **low tens of cents per game**, even with a critic/eval pass; **~$0.50–$1 sync, ~half via Batch** at the generous end. Generation is **one-time per upload**, cached thereafter — per-play OpenAI cost is ~$0.

### 5.5 Pedagogical prompt + evals (the part that impresses reviewers)

- **Prompt:** inject the source chunk; instruct the model to **ground both the key and the distractors** in that text; name the **target Bloom level + its definition** and require a spread; encode **item-writing rules** (clear stem, exactly one defensibly-correct answer, 3 plausible homogeneous distractors, no "all/none of the above", no cueing); return `sourceQuote` + `explanation`; use 1–2 few-shot exemplars.
- **Eval harness (portfolio centerpiece):** groundedness (LLM-as-judge faithfulness + fuzzy quote check), answerability, single-correct-answer, distractor quality, difficulty calibration, duplicate detection — surface the metrics in the README. Known LLM failure modes are ambiguous keys & weak distractors, so **human review stays the backstop** (and is a required teacher step anyway).

---

## 6. Data model & LMS backend  *(authored from expertise — research agent was cut off)*

**Backend layout (FastAPI + SQLModel + Alembic):**
```
app/
  main.py            # app factory, CORS, routers
  core/              # config (env), security (JWT verify), deps
  models/            # SQLModel tables
  schemas/           # Pydantic request/response + the game-content models
  routers/           # auth, documents, campaigns, assignments, play, analytics
  services/          # ingestion(Docling), generation(OpenAI), combat_tuning, evals, scoring
  workers/           # background parse/generate jobs
  alembic/           # migrations
```
**DB:** **SQLite** locally → **Postgres (Supabase)** in prod. **SQLModel** (SQLAlchemy + Pydantic, by FastAPI's author) keeps table models and API schemas coherent; **Alembic** for migrations.

### 6.1 Tables

| Table | Key columns | Relationships |
|---|---|---|
| `users` | id, email, role(`teacher`/`student`), display_name, auth_provider_id, created_at | 1─N classes (as teacher); N─M classes (as student, via enrollments) |
| `classes` | id, **teacher_id→users**, name, join_code (unique), created_at | N enrollments, N assignments |
| `enrollments` | id, **class_id→classes**, **student_id→users**, joined_at | join table users↔classes |
| `documents` | id, **owner_id→users**, filename, storage_url, mime, status(`uploaded`/`parsing`/`parsed`/`failed`), parsed_markdown, section_tree(JSONB), token_count, created_at | 1─N campaigns; 1─N chunks |
| `chunks` *(only if RAG)* | id, **document_id→documents**, ord, text, page, section, embedding(`vector`) | belongs to document |
| `campaigns` | id, **document_id→documents**, **teacher_id→users**, title, status(`draft`/`generating`/`ready`/`published`), game_json(JSONB), combat_config(JSONB), schema_version, created_at | the generated game; 1─N assignments |
| `assignments` | id, **campaign_id→campaigns**, **class_id→classes**, assigned_at, due_at, settings(JSONB) | links a game to a class |
| `play_sessions` | id, **assignment_id→assignments**, **student_id→users**, status, started_at, completed_at, final_score, final_xp, hp_remaining, run_seed | 1─N question_attempts (one roguelike "run") |
| `question_attempts` | id, **session_id→play_sessions**, question_id, encounter_id, is_correct, selected_answer(JSONB), time_ms, damage_dealt, streak_at_time, attempted_at | per-question telemetry (powers analytics) |
| `student_progress` | id, **student_id→users**, **campaign_id→campaigns**, level, total_xp, mastery_by_topic(JSONB), relics(JSONB), best_score, updated_at | persistent progression |

`question_id`/`encounter_id` are string IDs **within** `campaigns.game_json` (the game spec is stored as a JSON blob, not normalized into rows — it's generated-and-cached content, queried as a whole).

### 6.2 Auth & RBAC

**Recommendation: Supabase Auth.** The Next.js app authenticates via `supabase-js` (email magic-link / password / Google OAuth) and receives a **JWT**; FastAPI **verifies** that JWT (JWKS/secret) in a dependency and reads `role` from a `profiles`/`users` row. RBAC enforced via FastAPI dependencies (`require_teacher`, `require_student`). This avoids hand-rolling auth while still demonstrating real integration, and keeps Auth + DB + Storage in **one** provider (fewest moving parts).
- *Alternatives:* **Clerk** (best DX, adds a vendor), **Auth.js/NextAuth** (Next-native, you verify JWT in FastAPI), **FastAPI-Users** (full control, most boilerplate — strongest "I built auth" signal but slowest).

### 6.3 Dashboard analytics (compute from `question_attempts` + `play_sessions`)

- **Per-topic mastery** — % correct per act/topic, per student and class-aggregate → **heatmap**.
- **Item difficulty (p-value)** — % of students who got each question right; flag too-easy/too-hard.
- **Item discrimination (point-biserial)** *(stretch)* — do high scorers get an item right more than low scorers?
- **At-risk students** — low mastery, high HP loss, abandoned sessions.
- **Engagement/completion** — % started/finished, attempts, time-on-task, streak stats.
- Computed via SQL aggregations; materialize/cache for the dashboard.

### 6.4 Real-time / MVP decision

**Defer live multiplayer.** The roguelike is inherently **single-player async** — each student plays their own run. Synchronous "class battle" rooms (websockets) add real complexity that isn't core. **MVP = async play + polling** (SWR revalidation) for the dashboard/leaderboard. Add websockets later only for a live mode.

---

## 7. Deployment topology  *(⚠️ free-tier limits change — re-verify)*

| Component | Host | Notes |
|---|---|---|
| Next.js frontend | **Vercel** (Hobby/free) | First-class Next.js; trivial deploy. |
| FastAPI backend | **Render** or **Fly.io** | Render free spins down on idle (~cold start); Fly.io machines scale-to-zero. Run Docling parsing as a BackgroundTask on the instance for low volume. |
| Postgres + Auth + Storage (+ pgvector) | **Supabase** (free) | All-in-one → fewest moving parts. ⚠️ free projects **pause after ~1 week idle** — mitigate with a weekly **keep-alive ping** (GitHub Action/cron). |
| Heavy generation | **OpenAI Batch API** | Async fits the "building your game" UX; 50% cheaper. |

*Alternative if idle-pause is unacceptable:* **Neon** (Postgres + pgvector, scale-to-zero resume ~1s) + **Clerk** (auth) + **Cloudflare R2** (storage) — more pieces, no pause.

---

## 8. MVP scope (be ruthless)

**Must-have**
- Teacher: upload (PDF/DOCX/PPTX) → Docling parse → generate → **review/edit/discard** each question → assign to a class (join code).
- Generation: per-chapter, Structured Outputs, **3 question types done well: MCQ + multi-select + true/false** (highest generation reliability); **source-grounding stored + shown**.
- Student: join by code → play **one linear campaign** (acts→encounters→boss) with HP, streak multipliers, XP/level, per-answer feedback with citation.
- Teacher dashboard: class view + per-student view + **per-topic mastery heatmap** + at-risk flag.
- A small but **real eval harness** + README writeup with metrics + a 60-sec demo video.

**Should-have**
- `short_answer` (exact-match first, optional LLM-judge grading), relics/power-ups, class leaderboard, "tweak the game" (rename bosses, adjust HP), Smart-Repetition re-asking of missed questions, Batch API path.

**Later**
- `ordering`/`matching` types, RAG + tutor chat, procedural meta-progression, live multiplayer, standards alignment, deeper item-discrimination analytics, PixiJS/Lottie boss VFX.

---

## 9. Phased build roadmap

| Milestone | "Done" means |
|---|---|
| **M0 — Scaffold** | FastAPI + SQLModel + Alembic skeleton; Next.js + Tailwind app; Supabase project (DB+Auth+Storage); env/config; CI; deploy a hello-world of both. |
| **M1 — Ingestion + generation** | Upload → Docling parse (background) → Markdown + section tree persisted; per-chapter Structured-Outputs generation (MCQ/multi/TF) → validated game JSON + deterministic combat tuning stored; grounding + single-answer validators; basic eval script. |
| **M2 — Play one game** | Student joins by code; React+Motion+XState combat plays a full campaign end-to-end; attempts + scoring + XP/level persist; per-answer feedback with citation. |
| **M3 — LMS + dashboard** | Classes/enrollments/assignments; teacher review/edit screen; mastery heatmap + per-student view + at-risk flags; auth/RBAC enforced. |
| **M4 — Polish + deploy + showcase** | Should-have picks (relics, leaderboard, short-answer); keep-alive cron; README with architecture + eval metrics + grounding story; 60-sec demo video; live demo URLs. |

---

## 10. Risks & open questions

**Top risks (with mitigations)**
- **Looks like a StudyQuest clone** → make grounding/citations + the syllabus-mapped roguelike campaign + teacher monitoring *visible*; name the gap in the README.
- **Generation is commodity** → emphasize **grounding + evals + guardrails**, not "make a quiz."
- **Structured Outputs ≠ correct content** → always run the content-validation pass (single-answer, grounding, Bloom spread).
- **Model names/prices volatile** → pin model IDs in config behind env vars; re-verify on the OpenAI pricing page before spending.
- **Free-tier idle behavior** → Supabase pauses (~1wk) / Render cold starts → keep-alive cron; consider Neon for the DB.
- **Docling slow on the no-GPU dev box** → background jobs only; OCR only pages without text.
- **Scope creep** → one campaign shape, 2–3 question types, 2–3 boss mechanics; cache the game spec.
- **Grounding is genuinely hard** (messy PDFs) → have a fallback from span-level to page-level citation.

**Decisions — RESOLVED 2026-06-26**
1. ✅ **DB/auth/storage:** **Supabase** (all-in-one; mitigate idle-pause with a weekly keep-alive cron).
2. ✅ **Backend host:** **Render**.
3. ⬜ **Demo subject area:** still open (affects question-type mix — pick when seeding demo content).
4. ✅ **RAG:** **in scope for v1** (chunking + embeddings + pgvector retrieval from the start; still gate the long-context fast-path behind a `tiktoken` size check so we don't over-retrieve small docs).
5. ✅ **Auth depth:** managed — **Supabase Auth** (JWT verified in FastAPI).

> **Note (RAG in v1):** because Supabase is the DB, store embeddings in **pgvector in the same Postgres**. Still implement the size-check so a small single-chapter doc uses direct long-context generation and only larger corpora trigger retrieval — RAG is always available, but used when it helps.

---

## 11. Sources

1. OpenAI — Structured Outputs guide — https://developers.openai.com/api/docs/guides/structured-outputs
2. OpenAI — Introducing Structured Outputs — https://openai.com/index/introducing-structured-outputs-in-the-api/
3. OpenAI — Pricing — https://developers.openai.com/api/docs/pricing
4. OpenAI — GPT-5.5 model — https://developers.openai.com/api/docs/models/gpt-5.5
5. OpenAI — GPT-5.4 model — https://developers.openai.com/api/docs/models/gpt-5.4
6. OpenAI — Batch API — https://developers.openai.com/api/docs/guides/batch
7. OpenAI — text-embedding-3-small — https://developers.openai.com/api/docs/models/text-embedding-3-small
8. OpenAI — GPT-4.1 in the API — https://openai.com/index/gpt-4-1/
9. SO max depth/properties (OpenAI community) — https://community.openai.com/t/measuring-maximum-depth-and-object-properties-in-structured-outputs/918388
10. Structured Outputs JSON-schema practical guide — https://www.codewords.ai/blog/openai-structured-outputs-json-schema
11. Motion (ex-Framer Motion) — https://motion.dev/
12. Motion — reduce bundle size (LazyMotion/m) — https://motion.dev/docs/react-reduce-bundle-size
13. Next.js — lazy loading / next/dynamic ssr:false — https://nextjs.org/docs/pages/guides/lazy-loading
14. XState — https://github.com/statelyai/xstate
15. Introducing @xstate/store — https://tkdodo.eu/blog/introducing-x-state-store
16. Phaser releases — https://github.com/phaserjs/phaser/releases
17. PixiJS v8 launch — https://pixijs.com/blog/pixi-v8-launches
18. KAPLAY (GitHub) — https://github.com/kaplayjs/kaplay
19. Excalibur (npm, pre-1.0) — https://www.npmjs.com/package/excalibur
20. Docling (GitHub, MIT) — https://github.com/docling-project/docling
21. MarkItDown (Microsoft) — https://github.com/microsoft/markitdown
22. PyMuPDF licensing (AGPL/commercial) — https://github.com/pymupdf/PyMuPDF/discussions/971
23. Best OSS PDF→Markdown tools 2026 (licensing) — https://themenonlab.blog/blog/best-open-source-pdf-to-markdown-tools-2026
24. Supabase pricing/free tier 2026 — https://uibakery.io/blog/supabase-pricing
25. Neon serverless Postgres pricing 2026 — https://vela.simplyblock.io/articles/neon-serverless-postgres-pricing-2026/
26. Bloom's revised taxonomy — https://www.coloradocollege.edu/other/assessment/how-to-assess-learning/learning-outcomes/blooms-revised-taxonomy.html
27. QTI v3 implementation guide (1EdTech) — https://www.imsglobal.org/spec/qti/v3p0/impl
28. LLMs + Bloom's for quiz generation (arXiv) — https://arxiv.org/html/2401.05914v1
29. MCQ generation with LLMs — methodology & educator insights (arXiv) — https://arxiv.org/html/2506.04851v1
30. Personal AI Tutor — per-question source citation (arXiv 2309.13060) — https://arxiv.org/pdf/2309.13060
31. Quizizz AI question generator — https://quizizz.com/home/quizizz-ai/ai-question-generator
32. StudyQuest (closest analog) — https://www.studyquest.app/
33. Classcraft closure / alternatives — https://classcraft-alternative.com/
34. Duolingo gamification case study 2026 — https://trophy.so/blog/duolingo-gamification-case-study
35. Blooket vs Kahoot vs Gimkit vs Quizizz roundup — https://slideswith.com/blog/blooket-vs-kahoot-vs-gimkit-vs-quizizz

---

*Raw per-dimension research (full options/pros/cons/citations) is saved alongside this file at `docs/research/recovered-findings.json`.*
