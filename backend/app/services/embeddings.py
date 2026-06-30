"""Embeddings + in-memory cosine retrieval (RAG path).

Uses text-embedding-3-small. For local dev, vectors live as JSON on Chunk rows and
retrieval runs in Python; in prod they move to pgvector for ANN search. Retrieval is
only invoked when chunking.needs_rag() says the document is too big for direct context.
"""

from __future__ import annotations

import math

from openai import OpenAI

from app.core.config import settings


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    if not texts:
        return []
    resp = _client().embeddings.create(model=model or settings.openai_embedding_model, input=texts)
    return [d.embedding for d in resp.data]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def top_k(query: list[float], vectors: list[list[float]], k: int = 4) -> list[int]:
    """Indices of the k most similar vectors to `query` (descending similarity)."""
    scored = sorted(((cosine(query, v), i) for i, v in enumerate(vectors)), reverse=True)
    return [i for _, i in scored[:k]]
