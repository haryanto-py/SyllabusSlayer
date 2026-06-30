# SyllabusSlayer — Progress Tracker

Small, committed increments so work survives a mid-session cutoff. Tick items as they land; each ticked item = a commit.

## Current: M1.2 — RAG context + Docling ingestion

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
- [ ] **M2 — play one game (student client: React+Motion+XState combat) — next**
- [ ] M3 — LMS + dashboard (classes, assignments, analytics)
- [ ] M4 — polish + deploy (Vercel + Render + Supabase)

## Notes / constraints
- OpenAI budget ~$5 total; ~$0.15 spent. Use `gpt-5.4-nano` (outline) + `gpt-5.4-mini` (questions); avoid `gpt-5.4`/`5.5`/`pro`. `gpt-4o-mini` available as a stable fallback (not needed so far).
- Copyrighted test PDF + its derived game JSON are gitignored (local only).
- Run: backend `cd backend && uv run uvicorn app.main:app --reload`; tests `uv run pytest -q`; live `uv run python scripts/m1_demo.py [PATH]`.
