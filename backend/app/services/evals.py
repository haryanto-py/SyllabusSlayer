"""Content evals / guardrails over generated questions (docs/BUILD-SPEC.md §4.4, §5.5).

Structured Outputs guarantees JSON *shape*, not pedagogical *correctness*. This layer
checks the things that matter and that strict mode cannot enforce:
  - source grounding: is `sourceQuote` actually present (fuzzily) in the source text?
  - single-answer integrity for MCQ
  - duplicate / empty options
  - Bloom-level spread across an encounter
The aggregate report is the visible "AI engineering" artifact for the portfolio.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from app.schemas.game import Question, QuestionType

_GROUNDING_THRESHOLD = 0.6


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def fuzzy_contains(needle: str, haystack: str) -> float:
    """Fraction of `needle` found as a contiguous run inside `haystack` (0..1).

    `autojunk=False` is essential: difflib's autojunk heuristic treats frequent
    characters as junk on inputs >200 chars, which destroys matching against a
    full source document and produces false 0.0 grounding scores.
    """
    n, h = _norm(needle), _norm(haystack)
    if not n:
        return 0.0
    if n in h:
        return 1.0
    match = difflib.SequenceMatcher(None, n, h, autojunk=False).find_longest_match(
        0, len(n), 0, len(h)
    )
    return match.size / len(n)


@dataclass
class QuestionEval:
    question_id: str
    grounding: float
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def evaluate_question(q: Question, context: str) -> QuestionEval:
    issues: list[str] = []

    grounding = fuzzy_contains(q.sourceQuote, context)
    if grounding < _GROUNDING_THRESHOLD:
        issues.append(f"weak source grounding ({grounding:.2f} < {_GROUNDING_THRESHOLD})")

    if q.questionType in (QuestionType.multiple_choice, QuestionType.multi_select):
        opts = q.options or []
        texts = [_norm(o.text) for o in opts]
        if len(set(texts)) != len(texts):
            issues.append("duplicate option text")
        if any(not t for t in texts):
            issues.append("empty option text")
        if q.questionType is QuestionType.multiple_choice and len(q.correctOptionIds or []) != 1:
            issues.append("multiple_choice without exactly one correct option")

    if not _norm(q.explanation):
        issues.append("missing explanation")

    return QuestionEval(question_id=q.questionId, grounding=round(grounding, 3), issues=issues)


@dataclass
class EncounterEval:
    encounter_id: str
    questions: list[QuestionEval]
    bloom_distribution: dict[str, int]

    @property
    def bloom_diversity(self) -> int:
        return len([k for k, v in self.bloom_distribution.items() if v > 0])


def evaluate_encounter(encounter_id: str, questions: list[Question], context: str) -> EncounterEval:
    evals = [evaluate_question(q, context) for q in questions]
    dist: dict[str, int] = {}
    for q in questions:
        dist[q.bloomLevel.value] = dist.get(q.bloomLevel.value, 0) + 1
    return EncounterEval(encounter_id=encounter_id, questions=evals, bloom_distribution=dist)


@dataclass
class GameEval:
    encounters: list[EncounterEval]

    @property
    def total_questions(self) -> int:
        return sum(len(e.questions) for e in self.encounters)

    @property
    def grounded_pct(self) -> float:
        qs = [q for e in self.encounters for q in e.questions]
        if not qs:
            return 0.0
        grounded = sum(1 for q in qs if q.grounding >= _GROUNDING_THRESHOLD)
        return round(100 * grounded / len(qs), 1)

    @property
    def clean_pct(self) -> float:
        qs = [q for e in self.encounters for q in e.questions]
        if not qs:
            return 0.0
        return round(100 * sum(1 for q in qs if q.ok) / len(qs), 1)

    def flagged(self) -> list[QuestionEval]:
        return [q for e in self.encounters for q in e.questions if not q.ok]

    def summary(self) -> dict:
        return {
            "total_questions": self.total_questions,
            "grounded_pct": self.grounded_pct,
            "clean_pct": self.clean_pct,
            "flagged": [{"questionId": q.question_id, "issues": q.issues} for q in self.flagged()],
        }
