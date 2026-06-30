"""Run the M1 generation pipeline on the demo fixture end-to-end (LIVE — costs a few cents).

    cd backend && uv run python scripts/m1_demo.py

Writes the generated game to docs/examples/cell_biology_game.json and prints a
usage/cost/eval report.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.assembly import build_game
from app.services.ingestion import parse_markdown

_BACKEND = Path(__file__).resolve().parents[1]
_REPO = _BACKEND.parent
FIXTURE = _BACKEND / "tests" / "fixtures" / "cell_biology.md"


def main() -> None:
    parsed = parse_markdown(FIXTURE.read_text(encoding="utf-8"))
    result = build_game(
        parsed=parsed,
        source_document_id="doc_cell_biology",
        title="Cell Biology: The Organelle Wars",
    )

    out_dir = _REPO / "docs" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "cell_biology_game.json"
    out_file.write_text(json.dumps(result["game"], indent=2), encoding="utf-8")

    print("=== USAGE ===", result["usage"])
    print("=== ESTIMATED COST (USD) ===", result["estimated_cost_usd"])
    print("=== EVAL ===")
    print(json.dumps(result["eval"], indent=2))

    g = result["game"]
    print(f"\n=== GAME: {g['title']} — {len(g['acts'])} acts ===")
    for act in g["acts"]:
        print(f"  Act: {act['title']}  ({len(act['encounters'])} encounters)")
        for enc in act["encounters"]:
            print(
                f"    [{enc['kind']}] {enc['title']} — {len(enc['questions'])} Q, "
                f"enemyHP {enc['combat']['enemyMaxHp']}"
            )
            for q in enc["questions"]:
                tag = f"{q['questionType']}/{q['bloomLevel']}/{q['difficulty']}"
                print(f"        ({tag}) {q['prompt'][:72]}")
    print(f"\nWrote {out_file}")


if __name__ == "__main__":
    main()
