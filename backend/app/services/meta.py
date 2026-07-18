"""Meta-progression balance math (M5.3) — pure, DB-free, unit-testable.

Everything here rewards *demonstrated learning*, never grinding or luck, and NEVER
touches correctness (that lives only in ``scoring.check_answer``). Meta effects flow
out through two amplify-only channels the run already has: a capped run-start max-HP
bonus, and which relics are allowed into the reward pool. This module owns the balance
constants so the router stays declarative (mirrors how ``services/relics.py`` owns relics).

Mastery is a per-topic accuracy signal computed by ``services/analytics.aggregate`` over
real ``QuestionAttempt`` rows — the same computation the teacher dashboard trusts. A topic
is "mastered" at accuracy >= ``MASTERY_THRESHOLD`` over >= ``MIN_ATTEMPTS`` attempts.

``mastery_by_topic`` is stored as ``{topic: {"attempts", "correct", "accuracy"}}`` where
``accuracy`` is the sticky best-ever peak (monotonic), so a bad run never erases a proven
topic — see ``merge_mastery``.
"""

from __future__ import annotations

MASTERY_THRESHOLD = 0.8  # accuracy needed to count a topic as "mastered"
MIN_ATTEMPTS = 4  # ...over at least this many attempts (no lucky one-shot mastery)

INSIGHT_WEIGHT = 100  # Insight per +1.0 of fresh accuracy on a fully-evidenced topic
HP_PER_MASTERED_TOPIC = 5  # run-start max-HP bonus per mastered topic
HP_BONUS_CAP = 20  # ...hard-capped (never buys a fight you can't win)

# Relics always in the reward pool (commons — a fresh player always has something to pick).
STARTER_RELICS: tuple[str, ...] = ("keen_focus", "aegis")
# Additional relics unlocked one-by-one as the student masters more topics (roughly
# ascending power). Kept disjoint from STARTER_RELICS.
UNLOCK_ORDER: tuple[str, ...] = (
    "curious_mind",
    "momentum",
    "scholars_might",
    "vitality",
    "second_thought",
)


def _accuracy(entry: object) -> float:
    """Accuracy from a mastery entry (dict) or a bare float; 0.0 if absent/malformed."""
    if isinstance(entry, dict):
        return float(entry.get("accuracy", 0.0) or 0.0)
    if isinstance(entry, (int, float)):
        return float(entry)
    return 0.0


def _attempts(entry: object) -> int:
    if isinstance(entry, dict):
        return int(entry.get("attempts", 0) or 0)
    return 0


def is_mastered(entry: object) -> bool:
    return _accuracy(entry) >= MASTERY_THRESHOLD and _attempts(entry) >= MIN_ATTEMPTS


def mastered_count(mastery_by_topic: dict | None) -> int:
    return sum(1 for e in (mastery_by_topic or {}).values() if is_mastered(e))


def merge_mastery(prior: dict | None, current: list[dict]) -> dict:
    """Monotonic-max merge of a fresh cumulative aggregate into the persisted mastery.

    ``current`` is ``analytics.aggregate``'s per-topic list computed over ALL of the
    student's attempts for the campaign (so ``attempts``/``correct`` are cumulative). We
    keep those cumulative counts but pin ``accuracy`` to the best-ever peak, so replaying a
    topic badly can never lower a previously proven mastery.
    """
    merged: dict = dict(prior or {})
    for row in current:
        topic = row.get("topic")
        if topic is None:
            continue
        prior_acc = _accuracy(merged.get(topic))
        merged[topic] = {
            "attempts": int(row.get("attempts", 0) or 0),
            "correct": int(row.get("correct", 0) or 0),
            "accuracy": max(prior_acc, float(row.get("accuracy", 0.0) or 0.0)),
        }
    return merged


def award_insight(current: list[dict], prior: dict | None) -> int:
    """Insight minted this run = sum of *fresh* per-topic mastery gained.

    Per topic: ``INSIGHT_WEIGHT * max(0, current_accuracy - prior_peak_accuracy)`` scaled by
    an evidence credit ``min(1, attempts / MIN_ATTEMPTS)``. Because ``prior`` holds the sticky
    peak, replaying an already-mastered topic yields ~0 — grinding cannot buy power; only
    learning something new pays.
    """
    prior = prior or {}
    total = 0.0
    for row in current:
        topic = row.get("topic")
        if topic is None:
            continue
        delta = max(0.0, float(row.get("accuracy", 0.0) or 0.0) - _accuracy(prior.get(topic)))
        if delta <= 0:
            continue
        credit = min(1.0, int(row.get("attempts", 0) or 0) / MIN_ATTEMPTS)
        total += INSIGHT_WEIGHT * delta * credit
    return round(total)


def unlocked_pool(mastery_by_topic: dict | None) -> list[str]:
    """Relic ids the student is allowed to be offered, given their mastery."""
    n = mastered_count(mastery_by_topic)
    return list(STARTER_RELICS) + list(UNLOCK_ORDER[:n])


def newly_unlocked_relics(
    mastery_by_topic: dict | None, already_unlocked: list[str] | None
) -> list[str]:
    """Relic ids that just became available (not previously unlocked)."""
    have = set(already_unlocked or [])
    return [rid for rid in unlocked_pool(mastery_by_topic) if rid not in have]


def start_bonus_max_hp(mastery_by_topic: dict | None) -> int:
    """Capped run-start max-HP bonus: small forgiveness for proven knowledge, never a win."""
    return min(HP_BONUS_CAP, mastered_count(mastery_by_topic) * HP_PER_MASTERED_TOPIC)
