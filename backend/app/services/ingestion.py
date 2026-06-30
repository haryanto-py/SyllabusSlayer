"""Document ingestion: parse an upload to Markdown + a section tree.

Strategy (docs/BUILD-SPEC.md §5.1): Docling (MIT) is the primary parser for
PDF/DOCX/PPTX/images, MarkItDown is the fallback for clean digital files, and
.md/.txt pass straight through. The heavy parsers are imported lazily so this
module loads fine without the `ingestion` extra (`uv sync --extra ingestion`).

The section tree mirrors Markdown heading structure and doubles as the basis for
the campaign map (acts/encounters).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_PASSTHROUGH = {".md", ".markdown", ".txt"}


@dataclass
class Section:
    title: str
    level: int
    content: str = ""
    children: list[Section] = field(default_factory=list)

    def text(self) -> str:
        """Full text of this section including its descendants (for generation context)."""
        parts = [f"{'#' * self.level} {self.title}".strip(), self.content.strip()]
        parts += [c.text() for c in self.children]
        return "\n".join(p for p in parts if p).strip()


@dataclass
class ParsedDocument:
    markdown: str
    sections: list[Section]


def parse_document(path: str | Path) -> ParsedDocument:
    """Parse a file to Markdown + section tree. Raises if no parser is available."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in _PASSTHROUGH:
        markdown = path.read_text(encoding="utf-8")
    else:
        markdown = _parse_binary(path)
    return ParsedDocument(markdown=markdown, sections=build_section_tree(markdown))


def parse_markdown(markdown: str) -> ParsedDocument:
    """Build a ParsedDocument directly from Markdown text (used by tests/fixtures)."""
    return ParsedDocument(markdown=markdown, sections=build_section_tree(markdown))


def _parse_binary(path: Path) -> str:
    # Docling first (handles PDF/DOCX/PPTX/images + OCR), then MarkItDown.
    try:
        from docling.document_converter import DocumentConverter  # type: ignore

        return DocumentConverter().convert(str(path)).document.export_to_markdown()
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 — fall back to MarkItDown on any Docling failure
        pass
    try:
        from markitdown import MarkItDown  # type: ignore

        return MarkItDown().convert(str(path)).text_content
    except ImportError as exc:
        raise RuntimeError(
            f"No parser available for '{path.name}'. Install parsing extras: "
            "uv sync --extra ingestion"
        ) from exc


def build_section_tree(markdown: str) -> list[Section]:
    """Parse Markdown headings into a nested section tree."""
    root = Section(title="", level=0)
    stack: list[Section] = [root]
    for line in markdown.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            section = Section(title=m.group(2).strip(), level=len(m.group(1)))
            while stack[-1].level >= section.level:
                stack.pop()
            stack[-1].children.append(section)
            stack.append(section)
        else:
            stack[-1].content += line + "\n"
    return root.children


def flatten(sections: list[Section]) -> list[Section]:
    """Depth-first flattened list of all sections."""
    out: list[Section] = []
    for s in sections:
        out.append(s)
        out.extend(flatten(s.children))
    return out
