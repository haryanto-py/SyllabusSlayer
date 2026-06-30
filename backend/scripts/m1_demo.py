"""Run the M1 generation pipeline on a document end-to-end (LIVE — costs money).

    cd backend && uv run python scripts/m1_demo.py [PATH]
        [--max-encounters N] [--outline-model M] [--question-model M] [--title T]

Defaults to the cell-biology markdown fixture. PDFs/DOCX/PPTX need `uv sync --extra
ingestion`. Writes the game to docs/examples/<stem>_game.json and prints a
usage/cost/eval report plus a duplicate-sub-topic check.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.assembly import build_game
from app.services.ingestion import parse_document

_BACKEND = Path(__file__).resolve().parents[1]
_REPO = _BACKEND.parent
DEFAULT_FIXTURE = _BACKEND / "tests" / "fixtures" / "cell_biology.md"


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=str(DEFAULT_FIXTURE))
    ap.add_argument("--max-encounters", type=int, default=None)
    ap.add_argument("--outline-model", default=None)
    ap.add_argument("--question-model", default=None)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    path = Path(args.path)
    parsed = parse_document(path)
    result = build_game(
        parsed=parsed,
        source_document_id=f"doc_{_slug(path.stem)}",
        title=args.title,
        outline_model=args.outline_model,
        question_model=args.question_model,
        max_encounters=args.max_encounters,
    )

    out_dir = _REPO / "docs" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{_slug(path.stem)}_game.json"
    out_file.write_text(json.dumps(result["game"], indent=2), encoding="utf-8")

    print("=== USAGE ===", result["usage"])
    print("=== ESTIMATED COST (USD) ===", result["estimated_cost_usd"])
    print("=== EVAL ===")
    print(json.dumps(result["eval"], indent=2))

    g = result["game"]
    print(f"\n=== GAME: {g['title']} — {len(g['acts'])} acts ===")
    subtopics: list[str] = []
    for act in g["acts"]:
        print(f"  Act: {act['title']}  ({len(act['encounters'])} encounters)")
        for enc in act["encounters"]:
            subtopics.append(enc["subTopic"])
            print(
                f"    [{enc['kind']}] {enc['title']} — sub:{enc['subTopic']!r} — "
                f"{len(enc['questions'])} Q, enemyHP {enc['combat']['enemyMaxHp']}"
            )
    dupes = sorted({s for s in subtopics if subtopics.count(s) > 1})
    print(f"\nDuplicate sub-topics across campaign: {dupes or 'NONE'}")
    print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
