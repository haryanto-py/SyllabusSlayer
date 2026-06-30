"""Server-authoritative play scoring (M2).

The student client receives a REDACTED game (no answer fields) and submits each answer
to the backend, which checks correctness against the stored game, computes damage/XP/HP,
and persists the attempt. This keeps answers off the client and makes scoring trustworthy.
Pure functions here; the router handles persistence.
"""

from __future__ import annotations

from typing import Any

from app.schemas.game import CombatConfig

# Fields stripped from questions before sending the game to a student.
_ANSWER_FIELDS = {
    "correctOptionIds",
    "correctBoolean",
    "acceptedAnswers",
    "caseSensitive",
    "explanation",
    "sourceQuote",
    "sourceChunkIds",
    "sourcePage",
}


def redact_question(q: dict) -> dict:
    r = {k: v for k, v in q.items() if k not in _ANSWER_FIELDS}
    if q.get("orderedItems"):  # keep items to arrange, hide the correct order
        r["orderedItems"] = [
            {"itemId": it["itemId"], "text": it["text"]} for it in q["orderedItems"]
        ]
    if q.get("matchPairs"):  # present sides separately, unpaired
        pairs = q["matchPairs"]
        r["matchPairs"] = None
        r["matchLeft"] = [{"pairId": p["pairId"], "left": p["left"]} for p in pairs]
        r["matchRight"] = sorted(p["right"] for p in pairs)
    return r


def redact_game(game: dict) -> dict:
    out = {k: v for k, v in game.items() if k != "acts"}
    out["acts"] = [
        {
            **{k: v for k, v in act.items() if k != "encounters"},
            "encounters": [
                {
                    **{k: v for k, v in enc.items() if k != "questions"},
                    "questions": [redact_question(q) for q in enc.get("questions", [])],
                }
                for enc in act.get("encounters", [])
            ],
        }
        for act in game.get("acts", [])
    ]
    return out


def find_question(game: dict, encounter_id: str, question_id: str) -> dict | None:
    for act in game.get("acts", []):
        for enc in act.get("encounters", []):
            if enc.get("encounterId") != encounter_id:
                continue
            for q in enc.get("questions", []):
                if q.get("questionId") == question_id:
                    return q
    return None


def check_answer(q: dict, submitted: Any) -> tuple[bool, Any]:
    """Return (is_correct, canonical_correct_answer) for the question type."""
    qt = q.get("questionType")
    if qt == "multiple_choice":
        correct = q.get("correctOptionIds") or []
        first = correct[0] if correct else None
        return submitted == first, first
    if qt == "multi_select":
        correct = set(q.get("correctOptionIds") or [])
        return set(submitted or []) == correct, sorted(correct)
    if qt == "true_false":
        return bool(submitted) == bool(q.get("correctBoolean")), bool(q.get("correctBoolean"))
    if qt == "short_answer":
        accepted = q.get("acceptedAnswers") or []
        if q.get("caseSensitive"):
            return str(submitted) in accepted, accepted
        sub = str(submitted or "").strip().lower()
        return sub in [str(a).strip().lower() for a in accepted], accepted
    if qt == "ordering":
        items = sorted(q.get("orderedItems") or [], key=lambda x: x["order"])
        correct = [it["itemId"] for it in items]
        return list(submitted or []) == correct, correct
    if qt == "matching":
        correct = {p["pairId"]: p["right"] for p in (q.get("matchPairs") or [])}
        return dict(submitted or {}) == correct, correct
    return False, None


def streak_multiplier(streak: int, cfg: CombatConfig) -> float:
    tiers = cfg.streakMultipliers or [1.0]
    if streak <= 0:
        return 1.0
    return tiers[min(streak - 1, len(tiers) - 1)]


def xp_for_difficulty(difficulty: str, cfg: CombatConfig) -> int:
    return getattr(cfg.xpPerCorrectByDifficulty, difficulty, cfg.xpPerCorrectByDifficulty.medium)


def level_for_xp(xp: int, cfg: CombatConfig) -> int:
    level = 1
    for i, threshold in enumerate(cfg.levelXpCurve):
        if xp >= threshold:
            level = i + 1
    return level


def trailing_streak(is_correct_sequence: list[bool]) -> int:
    """Number of consecutive correct answers at the end of the sequence."""
    streak = 0
    for ok in is_correct_sequence:
        streak = streak + 1 if ok else 0
    return streak


def score_answer(q: dict, submitted: Any, prev_streak: int, cfg: CombatConfig) -> dict:
    is_correct, correct = check_answer(q, submitted)
    if is_correct:
        new_streak = prev_streak + 1
        return {
            "is_correct": True,
            "correct": correct,
            "damage": round(cfg.baseDamagePerCorrect * streak_multiplier(new_streak, cfg)),
            "new_streak": new_streak,
            "xp_gain": xp_for_difficulty(q.get("difficulty", "medium"), cfg),
            "hp_cost": 0,
        }
    return {
        "is_correct": False,
        "correct": correct,
        "damage": 0,
        "new_streak": 0,
        "xp_gain": 0,
        "hp_cost": cfg.wrongAnswerHpCost,
    }
