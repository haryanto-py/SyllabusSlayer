"""Deterministic unit tests for the M1 pipeline (no OpenAI calls)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.game import (
    BloomLevel,
    CombatConfig,
    Difficulty,
    EncounterKind,
    Option,
    Question,
    QuestionType,
)
from app.services import combat_tuning, evals
from app.services.chunking import chunk_document, count_tokens, needs_rag
from app.services.ingestion import build_section_tree, flatten, parse_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "cell_biology.md"


def _mcq(qid: str, diff: Difficulty, *, quote: str = "ATP production", dup: bool = False) -> Question:
    opts = [Option(optionId="a", text="A"), Option(optionId="b", text="A" if dup else "B")]
    return Question(
        questionId=qid,
        questionType=QuestionType.multiple_choice,
        bloomLevel=BloomLevel.remember,
        difficulty=diff,
        prompt="What does the mitochondrion do?",
        sourceChunkIds=["c1"],
        sourceQuote=quote,
        sourcePage=None,
        explanation="Because the source says so.",
        hint=None,
        options=opts,
        correctOptionIds=["a"],
        correctBoolean=None,
        acceptedAnswers=None,
        caseSensitive=None,
        orderedItems=None,
        matchPairs=None,
    )


# --- ingestion -------------------------------------------------------------- #
def test_section_tree_from_fixture():
    parsed = parse_markdown(FIXTURE.read_text(encoding="utf-8"))
    assert len(parsed.sections) == 1  # single H1 root
    root = parsed.sections[0]
    assert root.title.startswith("Cell Biology")
    act_titles = [c.title for c in root.children]
    assert "The Cell and Its Organelles" in act_titles
    assert "Cellular Respiration" in act_titles
    # Mitochondria sub-section should carry its body text
    mito = next(s for s in flatten(parsed.sections) if s.title == "Mitochondria")
    assert "ATP production" in mito.content


def test_build_section_tree_levels():
    md = "# A\nintro\n## B\nbody\n### C\ndeep\n## D\nmore"
    secs = build_section_tree(md)
    assert [s.title for s in secs] == ["A"]
    assert [c.title for c in secs[0].children] == ["B", "D"]
    assert secs[0].children[0].children[0].title == "C"


# --- chunking / RAG gate ---------------------------------------------------- #
def test_token_count_and_rag_gate():
    assert count_tokens("hello world") > 0
    assert needs_rag(50, 100) is False
    assert needs_rag(150, 100) is True


def test_chunk_document_tags_sections():
    parsed = parse_markdown(FIXTURE.read_text(encoding="utf-8"))
    chunks = chunk_document(parsed, max_tokens=600, overlap=40)
    assert chunks
    assert any(c.section == "Mitochondria" for c in chunks)
    assert all(c.text.strip() for c in chunks)


# --- combat tuning ---------------------------------------------------------- #
def test_combat_scales_with_kind():
    cfg = CombatConfig()
    qs = [_mcq("q1", Difficulty.medium), _mcq("q2", Difficulty.hard)]
    boss = combat_tuning.compute_encounter_combat(qs, EncounterKind.boss, cfg)
    minion = combat_tuning.compute_encounter_combat(qs, EncounterKind.minion, cfg)
    assert boss.enemyMaxHp > minion.enemyMaxHp > 0
    assert boss.kindHpMultiplier > minion.kindHpMultiplier


def test_rewards_by_kind():
    assert combat_tuning.rewards_for_encounter(EncounterKind.boss)
    assert combat_tuning.rewards_for_encounter(EncounterKind.minion) == []


# --- evals ------------------------------------------------------------------ #
def test_fuzzy_contains():
    ctx = "Mitochondria are the site of ATP production through aerobic respiration."
    assert evals.fuzzy_contains("ATP production", ctx) == 1.0
    assert evals.fuzzy_contains("the quheen of randomstan declared war", ctx) < 0.6


def test_fuzzy_contains_long_haystack_regression():
    # difflib's autojunk used to break matching on >200-char haystacks, yielding false 0.0.
    doc = (
        "The cell membrane is a phospholipid bilayer surrounding the cell. " * 8
        + "They have an inner membrane folded into cristae that increase the surface area."
    )
    assert len(doc) > 200
    assert evals.fuzzy_contains("their inner membrane folded into cristae", doc) >= 0.6


def test_evaluate_question_flags_problems():
    ctx = "Mitochondria are the site of ATP production."
    good = evals.evaluate_question(_mcq("q1", Difficulty.easy, quote="ATP production"), ctx)
    assert good.ok and good.grounding == 1.0

    ungrounded = evals.evaluate_question(_mcq("q2", Difficulty.easy, quote="totally unrelated text"), ctx)
    assert any("grounding" in i for i in ungrounded.issues)

    dup = evals.evaluate_question(_mcq("q3", Difficulty.easy, dup=True), ctx)
    assert any("duplicate" in i for i in dup.issues)


def test_game_eval_summary():
    ctx = "Mitochondria are the site of ATP production."
    enc = evals.evaluate_encounter("enc1", [_mcq("q1", Difficulty.easy)], ctx)
    game_eval = evals.GameEval(encounters=[enc])
    s = game_eval.summary()
    assert s["total_questions"] == 1
    assert s["grounded_pct"] == 100.0


# --- schema validator ------------------------------------------------------- #
def test_question_validator_rejects_bad_mcq():
    with pytest.raises(ValidationError):
        Question(
            questionId="bad",
            questionType=QuestionType.multiple_choice,
            bloomLevel=BloomLevel.remember,
            difficulty=Difficulty.easy,
            prompt="?",
            sourceChunkIds=[],
            sourceQuote="",
            sourcePage=None,
            explanation="",
            hint=None,
            options=None,  # MCQ with no options -> must fail
            correctOptionIds=None,
            correctBoolean=None,
            acceptedAnswers=None,
            caseSensitive=None,
            orderedItems=None,
            matchPairs=None,
        )
