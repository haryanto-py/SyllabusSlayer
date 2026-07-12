"""Relic catalog + effect aggregation (M5.2).

Relics amplify GOOD PLAY (more damage, HP cushions, XP) — they NEVER decide correctness.
Effects are applied server-side in scoring so a client can't tamper with them. Magnitudes
are authored here (the backend owns balance); the generator may only theme names later.
"""

from __future__ import annotations

import random

# effect.type ∈ bonus_damage(flat) · damage_pct(0.xx) · streak_bonus(tiers) ·
#              hp_ward(flat, reduces wrong-answer cost) · first_wrong_free(bool) ·
#              xp_pct(0.xx) · max_hp(flat, applied at pickup)
RELICS: dict[str, dict] = {
    "keen_focus": {
        "name": "Keen Focus", "icon": "🎯", "rarity": "common",
        "description": "+4 damage on every correct answer.",
        "effect": {"type": "bonus_damage", "magnitude": 4},
    },
    "scholars_might": {
        "name": "Scholar's Might", "icon": "💪", "rarity": "uncommon",
        "description": "+25% damage.",
        "effect": {"type": "damage_pct", "magnitude": 0.25},
    },
    "momentum": {
        "name": "Momentum", "icon": "🔥", "rarity": "uncommon",
        "description": "Your streak counts one tier higher for damage.",
        "effect": {"type": "streak_bonus", "magnitude": 1},
    },
    "aegis": {
        "name": "Aegis", "icon": "🛡️", "rarity": "common",
        "description": "Wrong answers cost 4 less HP.",
        "effect": {"type": "hp_ward", "magnitude": 4},
    },
    "second_thought": {
        "name": "Second Thought", "icon": "🍀", "rarity": "rare",
        "description": "The first wrong answer in each encounter costs no HP.",
        "effect": {"type": "first_wrong_free", "magnitude": 1},
    },
    "curious_mind": {
        "name": "Curious Mind", "icon": "📖", "rarity": "common",
        "description": "+50% XP from correct answers.",
        "effect": {"type": "xp_pct", "magnitude": 0.5},
    },
    "vitality": {
        "name": "Vitality", "icon": "❤️", "rarity": "uncommon",
        "description": "+25 max HP (and heal 25 now).",
        "effect": {"type": "max_hp", "magnitude": 25},
    },
}


def aggregate_effects(relic_ids: list[str] | None) -> dict:
    """Sum the modifiers from a run's owned relics into one effects dict."""
    eff = {
        "bonus_damage": 0,
        "damage_pct": 0.0,
        "streak_bonus": 0,
        "hp_ward": 0,
        "first_wrong_free": False,
        "xp_pct": 0.0,
        "max_hp": 0,
    }
    for rid in relic_ids or []:
        r = RELICS.get(rid)
        if not r:
            continue
        t, m = r["effect"]["type"], r["effect"]["magnitude"]
        if t == "first_wrong_free":
            eff["first_wrong_free"] = True
        elif t in eff:
            eff[t] += m
    return eff


def relic_public(relic_id: str) -> dict:
    r = RELICS[relic_id]
    return {
        "relicId": relic_id,
        "name": r["name"],
        "icon": r["icon"],
        "rarity": r["rarity"],
        "description": r["description"],
    }


def reward_options(owned: list[str] | None, seed: str, n: int = 3) -> list[dict]:
    """Return up to n relic choices the player doesn't already own (deterministic per seed)."""
    rng = random.Random(seed)
    pool = [rid for rid in RELICS if rid not in (owned or [])]
    rng.shuffle(pool)
    return [relic_public(rid) for rid in pool[:n]]
