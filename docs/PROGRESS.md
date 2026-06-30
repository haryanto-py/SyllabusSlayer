# SyllabusSlayer — Progress Tracker

Small, committed increments so work survives a mid-session cutoff. Tick items as they land; each ticked item = a commit.

## Current: M1.2 — RAG context + Docling ingestion

- [x] **T1. Ingestion parser decision** — DONE. Docling installs & extracts real headings (57 on the PDF), BUT its preprocess stage OOMs (`std::bad_alloc`) on ~20 of ~80 pages on this 16GB/no-GPU box and silently drops them (only 6k of 30k tokens survived). MarkItDown extracts the full 30,267 tokens reliably (no headings). **Default = `markitdown`**; config `ingestion_parser` = markitdown | docling | auto (auto = Docling then MarkItDown fallback on partial). Docling viable only on bigger hardware or small docs → RAG context (T2/T3) is what makes the structureless MarkItDown output work well.
- [ ] **T2. Embed + store chunks on ingestion** — chunk doc → `text-embedding-3-small` → persist on `Chunk` rows (JSON vectors locally; pgvector in prod).
- [ ] **T3. Per-encounter retrieval context** — in `assembly.build_game`, retrieve top-k chunks by the encounter sub-topic as question-gen context (replaces whole-doc fallback). Falls back to section text / whole doc for tiny docs.
- [ ] **T4. Large-document handling** — if doc tokens exceed an outline budget, build the outline from per-chunk **summaries** (cheap map step) instead of raw text, so oversized uploads still work. Question-gen already bounded by T3.
- [ ] **T5. Verify + tests + commit** — regression on cell-biology + the Korean PDF; check cost ↓ and grounding; add unit tests for retrieval + the size gate.

## Milestones
- [x] M0 — scaffold (monorepo: teacher/student apps + shared pkg; FastAPI backend)
- [x] M1 — AI pipeline (ingestion → Structured Outputs → combat tuning → evals); verified live
- [x] M1.1 — outline dedup + large-doc cap fixes; verified on real Korean PDF
- [ ] **M1.2 — RAG context + Docling (current)**
- [ ] M2 — play one game (student client: React+Motion+XState combat)
- [ ] M3 — LMS + dashboard (classes, assignments, analytics)
- [ ] M4 — polish + deploy (Vercel + Render + Supabase)

## Notes / constraints
- OpenAI budget ~$5 total; ~$0.15 spent. Use `gpt-5.4-nano` (outline) + `gpt-5.4-mini` (questions); avoid `gpt-5.4`/`5.5`/`pro`. `gpt-4o-mini` available as a stable fallback (not needed so far).
- Copyrighted test PDF + its derived game JSON are gitignored (local only).
- Run: backend `cd backend && uv run uvicorn app.main:app --reload`; tests `uv run pytest -q`; live `uv run python scripts/m1_demo.py [PATH]`.
