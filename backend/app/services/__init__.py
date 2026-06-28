"""Service layer (implemented in milestone M1+):

- ingestion.py     : Docling/MarkItDown parsing -> Markdown + section tree
- chunking.py      : section-aware chunking + tiktoken size check (RAG gate)
- embeddings.py    : text-embedding-3-small -> pgvector
- generation.py    : OpenAI Structured Outputs (outline -> per-encounter batches)
- combat_tuning.py : deterministic HP/damage/XP from difficulty + Bloom
- evals.py         : groundedness / single-answer / distractor-quality checks
- scoring.py       : authoritative answer scoring (mirrors the client domain layer)
"""
