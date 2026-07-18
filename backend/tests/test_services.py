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


# --- scoring (M2) ----------------------------------------------------------- #
def _mcq_q(qid: str = "q1", correct: str = "a") -> dict:
    return {
        "questionId": qid,
        "questionType": "multiple_choice",
        "difficulty": "medium",
        "options": [{"optionId": "a", "text": "A"}, {"optionId": "b", "text": "B"}],
        "correctOptionIds": [correct],
        "explanation": "because",
        "sourceQuote": "A is right",
        "orderedItems": None,
        "matchPairs": None,
    }


def test_scoring_check_answer_types():
    from app.services import scoring

    assert scoring.check_answer(_mcq_q(), "a")[0] is True
    assert scoring.check_answer(_mcq_q(), "b")[0] is False
    tf = {"questionType": "true_false", "correctBoolean": True}
    assert scoring.check_answer(tf, True)[0] is True
    assert scoring.check_answer(tf, False)[0] is False
    sa = {"questionType": "short_answer", "acceptedAnswers": ["ATP"], "caseSensitive": False}
    assert scoring.check_answer(sa, " atp ")[0] is True


def test_scoring_streak_and_damage():
    from app.schemas.game import CombatConfig
    from app.services import scoring

    cfg = CombatConfig()  # base 10, multipliers [1.0, 1.25, 1.5, 2.0]
    r1 = scoring.score_answer(_mcq_q(), "a", prev_streak=0, cfg=cfg)
    assert r1["is_correct"] and r1["new_streak"] == 1 and r1["damage"] == 10
    r2 = scoring.score_answer(_mcq_q(), "a", prev_streak=1, cfg=cfg)
    assert r2["damage"] == round(10 * 1.25)  # streak 2 -> 1.25x
    wrong = scoring.score_answer(_mcq_q(), "b", prev_streak=3, cfg=cfg)
    assert not wrong["is_correct"] and wrong["new_streak"] == 0
    assert wrong["hp_cost"] == cfg.wrongAnswerHpCost


def test_scoring_redact_removes_answers():
    from app.services import scoring

    game = {"acts": [{"encounters": [{"questions": [_mcq_q()]}]}]}
    q = scoring.redact_game(game)["acts"][0]["encounters"][0]["questions"][0]
    assert "correctOptionIds" not in q
    assert "explanation" not in q
    assert q["options"]  # options still present to render


# --- run map (M5.1) --------------------------------------------------------- #
def test_runmap_deterministic_and_boss_terminal():
    from app.services.runmap import build_act_map

    encs = [
        {"encounterId": "e1", "kind": "minion", "title": "M1"},
        {"encounterId": "e2", "kind": "elite", "title": "E1"},
        {"encounterId": "eb", "kind": "boss", "title": "Boss"},
    ]
    m1 = build_act_map(encs, "camp:act1")
    assert m1 == build_act_map(encs, "camp:act1")  # deterministic

    nodes, edges = m1["nodes"], m1["edges"]
    bosses = [n for n in nodes if n["type"] == "boss"]
    assert len(bosses) == 1 and bosses[0]["encounterId"] == "eb"
    boss_id = bosses[0]["nodeId"]
    assert all(e["from"] != boss_id for e in edges)  # boss is terminal
    assert any(e["to"] == boss_id for e in edges)  # boss reachable
    incoming = {e["to"] for e in edges}
    assert [n for n in nodes if n["nodeId"] not in incoming]  # >= 1 entry node
    assert {n["encounterId"] for n in nodes if n["type"] == "battle"} == {"e1", "e2"}


def test_runmap_boss_only_act():
    from app.services.runmap import build_act_map

    m = build_act_map([{"encounterId": "eb", "kind": "boss", "title": "Boss"}], "c:a")
    assert len(m["nodes"]) == 1 and m["nodes"][0]["type"] == "boss"
    assert m["edges"] == []


# --- relics (M5.2) ---------------------------------------------------------- #
def test_relic_effects_amplify_scoring():
    from app.schemas.game import CombatConfig
    from app.services import relics, scoring

    cfg = CombatConfig()  # base damage 10, wrong-answer cost 8
    q = _mcq_q()
    base = scoring.score_answer(q, "a", 0, cfg)
    eff = relics.aggregate_effects(["keen_focus", "scholars_might"])  # +4 flat, +25%
    assert scoring.score_answer(q, "a", 0, cfg, eff)["damage"] > base["damage"]

    ward = relics.aggregate_effects(["aegis"])  # wrong cost -4
    assert scoring.score_answer(q, "b", 0, cfg, ward)["hp_cost"] == cfg.wrongAnswerHpCost - 4

    free = relics.aggregate_effects(["second_thought"])  # first wrong each encounter is free
    assert scoring.score_answer(q, "b", 0, cfg, free, wrong_this_encounter=0)["hp_cost"] == 0
    assert (
        scoring.score_answer(q, "b", 0, cfg, free, wrong_this_encounter=1)["hp_cost"]
        == cfg.wrongAnswerHpCost
    )


def test_relic_reward_options_exclude_owned_and_deterministic():
    from app.services import relics

    opts = relics.reward_options(owned=["keen_focus"], seed="s:1", n=3)
    ids = {o["relicId"] for o in opts}
    assert len(opts) == 3 and "keen_focus" not in ids
    assert relics.reward_options(["keen_focus"], "s:1") == relics.reward_options(["keen_focus"], "s:1")


def test_relic_reward_options_allowed_gate():
    from app.services import relics

    only = relics.reward_options(owned=[], seed="s:1", n=3, allowed={"keen_focus"})
    assert [o["relicId"] for o in only] == ["keen_focus"]  # pool gated to the allowed set
    legacy = relics.reward_options(owned=[], seed="s:1", n=3, allowed=None)
    assert len(legacy) == 3  # None preserves pre-M5.3 behavior


# --- meta-progression (M5.3) ------------------------------------------------ #
def test_meta_award_insight_rewards_learning_not_grinding():
    from app.services import meta

    fresh = [{"topic": "A", "attempts": 4, "correct": 4, "accuracy": 1.0}]
    assert meta.award_insight(fresh, prior={}) == 100  # 100 * 1.0 delta * full credit

    # replaying an already-mastered topic pays ~0 (the anti-grind guardrail, as an assertion)
    prior = {"A": {"attempts": 4, "correct": 4, "accuracy": 1.0}}
    grind = [{"topic": "A", "attempts": 8, "correct": 8, "accuracy": 1.0}]
    assert meta.award_insight(grind, prior) == 0

    # partial evidence earns partial insight (min-attempts credit)
    thin = [{"topic": "B", "attempts": 2, "correct": 2, "accuracy": 1.0}]
    assert meta.award_insight(thin, prior={}) == 50  # 100 * 1.0 * (2/4)


def test_meta_merge_mastery_is_monotonic():
    from app.services import meta

    prior = {"A": {"attempts": 4, "correct": 4, "accuracy": 1.0}}
    worse = [{"topic": "A", "attempts": 8, "correct": 6, "accuracy": 0.75}]
    merged = meta.merge_mastery(prior, worse)
    assert merged["A"]["accuracy"] == 1.0  # a bad run never lowers a proven topic
    assert merged["A"]["attempts"] == 8  # ...but cumulative counts still advance


def test_meta_unlock_gating():
    from app.services import meta

    none_mastered = {"A": {"attempts": 4, "correct": 2, "accuracy": 0.5}}  # below threshold
    assert set(meta.newly_unlocked_relics(none_mastered, [])) == set(meta.STARTER_RELICS)

    too_few = {"A": {"attempts": 2, "correct": 2, "accuracy": 1.0}}  # not enough attempts
    assert set(meta.newly_unlocked_relics(too_few, [])) == set(meta.STARTER_RELICS)

    one_mastered = {"A": {"attempts": 4, "correct": 4, "accuracy": 1.0}}
    newly = meta.newly_unlocked_relics(one_mastered, list(meta.STARTER_RELICS))
    assert newly == [meta.UNLOCK_ORDER[0]]  # exactly one new relic, beyond the starters
    # idempotent: already-unlocked relics are not re-reported
    assert meta.newly_unlocked_relics(one_mastered, meta.unlocked_pool(one_mastered)) == []


def test_meta_start_bonus_monotonic_and_capped():
    from app.services import meta

    def mastery(n: int) -> dict:
        return {f"T{i}": {"attempts": 4, "correct": 4, "accuracy": 1.0} for i in range(n)}

    assert meta.start_bonus_max_hp(mastery(0)) == 0
    assert meta.start_bonus_max_hp(mastery(1)) == meta.HP_PER_MASTERED_TOPIC
    assert meta.start_bonus_max_hp(mastery(2)) > meta.start_bonus_max_hp(mastery(1))
    assert meta.start_bonus_max_hp(mastery(100)) == meta.HP_BONUS_CAP  # hard cap holds


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
