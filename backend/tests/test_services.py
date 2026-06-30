"""Deterministic unit tests for the M1 pipeline (no OpenAI calls)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.game import (
    ActStub,
    BloomLevel,
    CampaignOutline,
    CombatConfig,
    Difficulty,
    EncounterKind,
    EncounterStub,
    Option,
    Question,
    QuestionType,
)
from app.services import combat_tuning, evals
from app.services.chunking import chunk_document, count_tokens, needs_rag
from app.services.generation import dedupe_outline
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


# --- outline dedup ---------------------------------------------------------- #
def _enc(eid: str, sub: str) -> EncounterStub:
    return EncounterStub(
        encounterId=eid, order=1, kind=EncounterKind.minion, title=sub,
        enemyName="E", enemyFlavor="f", subTopic=sub, targetQuestionCount=2,
    )


def test_dedupe_outline_removes_cross_act_duplicates():
    outline = CampaignOutline(
        schemaVersion="1.0.0", campaignId="c", title="t", description="d", sourceDocumentId="doc",
        acts=[
            ActStub(actId="a1", order=1, title="Act 1", syllabusTopic="Organelles", summary="s",
                    encounters=[_enc("e1", "Mitochondria"), _enc("e2", "Nucleus")]),
            ActStub(actId="a2", order=2, title="Act 2", syllabusTopic="Respiration", summary="s",
                    encounters=[_enc("e3", "mitochondria "), _enc("e4", "Glycolysis")]),
        ],
    )
    deduped = dedupe_outline(outline)
    subs = [e.subTopic for a in deduped.acts for e in a.encounters]
    assert subs == ["Mitochondria", "Nucleus", "Glycolysis"]  # normalized duplicate dropped
    assert deduped.acts[1].encounters[0].order == 1  # orders renumbered in the kept act


# --- retrieval (RAG) -------------------------------------------------------- #
def test_retrieval_returns_relevant_chunk(monkeypatch):
    from app.services import embeddings, retrieval

    def _bow(texts, model=None):
        # toy 2-D embedding: [count('alpha'), count('beta')]
        return [[float(t.lower().count("alpha")), float(t.lower().count("beta"))] for t in texts]

    monkeypatch.setattr(embeddings, "embed_texts", _bow)
    monkeypatch.setattr(
        embeddings,
        "embed_texts_with_usage",
        lambda texts, model=None: (_bow(texts), {"model": "fake", "input": 0, "output": 0}),
    )
    parsed = parse_markdown("# Doc\n## A\nalpha alpha alpha\n## B\nbeta beta beta\n")
    index, usage = retrieval.build_index(parsed)
    assert usage["model"] == "fake"
    hits = index.search("alpha", k=1)
    assert hits and "alpha" in hits[0].text


# --- large-document handling (T4) ------------------------------------------- #
def test_token_windows_cover_full_text():
    from app.services.chunking import token_windows

    text = "lorem ipsum dolor sit amet " * 200
    windows = token_windows(text, 50)
    assert len(windows) > 1
    assert "".join(windows) == text


def test_summarize_for_outline_maps_each_window(monkeypatch):
    from app.services import generation

    monkeypatch.setattr(
        generation,
        "_complete",
        lambda *a, **k: ("DIGEST_PART", {"model": "fake", "input": 0, "output": 0, "reasoning": 0}),
    )
    parsed = parse_markdown("word " * 300)  # ~300 tokens → several windows
    digest, usages = generation.summarize_for_outline(parsed, batch_tokens=50)
    assert "DIGEST_PART" in digest
    assert len(usages) >= 2


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
