"""Aggregate play attempts into teacher-dashboard analytics (M3-T4).

Pure functions over a question index (built from the game JSON) and a list of attempts
(anything exposing ``question_id`` and ``is_correct``). The router supplies persistence.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Protocol


class _Attempt(Protocol):
    question_id: str
    is_correct: bool


def build_question_index(game: dict) -> dict[str, dict]:
    """question_id -> {topic, encounter_id, prompt}. Topic = the act (syllabus unit)."""
    index: dict[str, dict] = {}
    for act in game.get("acts", []):
        topic = act.get("title") or act.get("syllabusTopic") or "Topic"
        for enc in act.get("encounters", []):
            for q in enc.get("questions", []):
                index[q["questionId"]] = {
                    "topic": topic,
                    "encounter_id": enc.get("encounterId"),
                    "prompt": q.get("prompt", ""),
                }
    return index


def _rate(correct: int, total: int) -> float:
    return round(correct / total, 3) if total else 0.0


def aggregate(attempts: list[_Attempt], qindex: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Return (per-topic mastery, per-item difficulty)."""
    topic_total: dict[str, int] = defaultdict(int)
    topic_correct: dict[str, int] = defaultdict(int)
    item_total: dict[str, int] = defaultdict(int)
    item_correct: dict[str, int] = defaultdict(int)

    for a in attempts:
        meta = qindex.get(a.question_id, {})
        topic = meta.get("topic", "(unknown)")
        topic_total[topic] += 1
        topic_correct[topic] += 1 if a.is_correct else 0
        item_total[a.question_id] += 1
        item_correct[a.question_id] += 1 if a.is_correct else 0

    topics = [
        {
            "topic": t,
            "attempts": topic_total[t],
            "correct": topic_correct[t],
            "accuracy": _rate(topic_correct[t], topic_total[t]),
        }
        for t in topic_total
    ]
    items = [
        {
            "question_id": qid,
            "encounter_id": qindex.get(qid, {}).get("encounter_id"),
            "prompt": qindex.get(qid, {}).get("prompt", "")[:80],
            "attempts": item_total[qid],
            "p_value": _rate(item_correct[qid], item_total[qid]),  # item difficulty (% correct)
        }
        for qid in item_total
    ]
    return topics, items
