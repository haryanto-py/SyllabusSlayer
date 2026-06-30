"""Section-aware chunking + token counting + the RAG-vs-long-context gate.

Decision rule (docs/BUILD-SPEC.md §5.2): measure tokens; if the material for one
generation call fits comfortably in context, skip retrieval and pass cleaned text
directly. Only chunk + embed + retrieve when a document exceeds the threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from app.services.ingestion import ParsedDocument, Section, flatten

_ENC = None


def _enc():
    global _ENC
    if _ENC is None:
        try:
            _ENC = tiktoken.get_encoding("o200k_base")  # GPT-4o / GPT-5 family
        except Exception:  # noqa: BLE001
            _ENC = tiktoken.get_encoding("cl100k_base")
    return _ENC


def count_tokens(text: str) -> int:
    return len(_enc().encode(text or ""))


def needs_rag(total_tokens: int, threshold: int) -> bool:
    """True when the document is too large to feed directly and retrieval should kick in."""
    return total_tokens > threshold


@dataclass
class Chunk:
    ord: int
    text: str
    section: str | None = None
    page: int | None = None


def _split_tokens(text: str, max_tokens: int, overlap: int) -> list[str]:
    enc = _enc()
    ids = enc.encode(text)
    if len(ids) <= max_tokens:
        return [text] if text.strip() else []
    step = max(1, max_tokens - overlap)
    return [enc.decode(ids[i : i + max_tokens]) for i in range(0, len(ids), step)]


def chunk_document(
    parsed: ParsedDocument, *, max_tokens: int = 600, overlap: int = 80
) -> list[Chunk]:
    """Chunk by section, splitting long sections into overlapping token windows.

    Each chunk keeps its section title so retrieval results stay traceable
    (the basis for per-question source grounding).
    """
    chunks: list[Chunk] = []
    ord_ = 0
    sections: list[Section] = flatten(parsed.sections) or [
        Section(title="document", level=1, content=parsed.markdown)
    ]
    for section in sections:
        body = section.content.strip()
        if not body:
            continue
        for piece in _split_tokens(body, max_tokens, overlap):
            chunks.append(Chunk(ord=ord_, text=piece.strip(), section=section.title or None))
            ord_ += 1
    return chunks
