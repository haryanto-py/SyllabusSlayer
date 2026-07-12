"""Deterministic run-map generation (M5.1).

Turns an act's encounters into a small layered DAG the student navigates: pick a path
of nodes (battle sites + rest sites) that converges on the act's boss. Built at
generation time and stored in the game JSON, so the layout is fixed per campaign (no
runtime RNG, resume-safe). Richer crossing-path layouts (stsmapgen-style) can come later.

Design choice (M5.1): the boss is the mandatory act gate; non-boss encounters are nodes
on branching paths, so choosing a route is a real HP-economy decision (fight for practice
vs. rest). Coverage-vs-choice tuning is a later knob.
"""

from __future__ import annotations

import random

REST_HEAL_PCT = 30  # % of max HP a rest site restores


def build_act_map(encounters: list[dict], seed: str) -> dict:
    """Return {nodes, edges, restHealPct} for one act's encounters."""
    rng = random.Random(seed)  # str seed → deterministic across processes

    boss = next((e for e in encounters if e.get("kind") == "boss"), None)
    if boss is None and encounters:
        boss = encounters[-1]  # fallback: last encounter is the gate
    battles = [e for e in encounters if e is not boss]

    # Middle nodes: every non-boss battle + a few rest sites for HP-economy choices.
    items: list[dict] = [
        {
            "type": "battle",
            "encounterId": e["encounterId"],
            "kind": e.get("kind", "minion"),
            "title": e.get("title", "Battle"),
        }
        for e in battles
    ]
    if battles:
        for _ in range(max(1, (len(battles) + 1) // 2)):
            items.append({"type": "rest", "encounterId": None, "kind": None, "title": "Rest site"})
    rng.shuffle(items)

    nodes: list[dict] = []
    edges: list[dict] = []
    rows: list[list[str]] = []

    i = 0
    row = 0
    while i < len(items):
        width = 2 if (len(items) - i) >= 2 else 1
        row_ids = []
        for col in range(width):
            it = items[i]
            nid = f"n{row}_{col}"
            nodes.append({"nodeId": nid, "row": row, "col": col, **it})
            row_ids.append(nid)
            i += 1
        rows.append(row_ids)
        row += 1

    # Boss node — single, final row.
    boss_id = f"n{row}_0"
    nodes.append(
        {
            "nodeId": boss_id,
            "row": row,
            "col": 0,
            "type": "boss",
            "encounterId": boss["encounterId"] if boss else None,
            "kind": "boss",
            "title": (boss.get("title", "Boss") if boss else "Boss"),
        }
    )
    rows.append([boss_id])

    # Edges: fully connect adjacent rows (branching); last middle row → boss.
    for r in range(len(rows) - 1):
        for a in rows[r]:
            for b in rows[r + 1]:
                edges.append({"from": a, "to": b})

    return {"nodes": nodes, "edges": edges, "restHealPct": REST_HEAL_PCT}
