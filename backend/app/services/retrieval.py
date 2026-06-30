"""In-memory chunk retrieval for focused generation context (the RAG path).

Used when a document has no usable section structure (e.g. a heading-less PDF): instead
of feeding the whole document to every question-generation call, we chunk + embed once
and fetch only the top-k chunks relevant to each encounter's sub-topic. This keeps
question-gen context (and cost) bounded regardless of document size.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services import embeddings
from app.services.chunking import Chunk, chunk_document
from app.services.ingestion import ParsedDocument


@dataclass
class RetrievalIndex:
    chunks: list[Chunk]
    vectors: list[list[float]]

    def search(self, query: str, k: int = 5) -> list[Chunk]:
        if not self.chunks or not self.vectors:
            return []
        qv = embeddings.embed_texts([query])
        if not qv:
            return self.chunks[:k]
        return [self.chunks[i] for i in embeddings.top_k(qv[0], self.vectors, k)]


def build_index(
    parsed: ParsedDocument, *, max_tokens: int = 600, overlap: int = 80
) -> tuple[RetrievalIndex, dict]:
    """Chunk the document and embed every chunk once. Returns (index, embedding-usage)."""
    chunks = chunk_document(parsed, max_tokens=max_tokens, overlap=overlap)
    vectors, usage = embeddings.embed_texts_with_usage([c.text for c in chunks])
    return RetrievalIndex(chunks=chunks, vectors=vectors), usage
