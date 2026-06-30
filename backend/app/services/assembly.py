"""Pipeline: ParsedDocument -> validated, combat-tuned, evaluated game JSON.

Orchestrates outline -> per-encounter questions -> deterministic combat tuning -> evals,
then assembles the final game dict (matching docs/BUILD-SPEC.md §4 example shape) and
reports token usage + an estimated cost.
"""

from __future__ import annotations

from app.schemas.game import SCHEMA_VERSION, CombatConfig
from app.services import combat_tuning, evals, generation
from app.services.ingestion import ParsedDocument, flatten

# Per-1M-token (input, output) USD — research-current mid-2026; re-verify before relying.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.5": (5.00, 30.00),
}


def _context_for_encounter(parsed: ParsedDocument, act_topic: str, sub_topic: str) -> str:
    sections = flatten(parsed.sections)
    sub = (sub_topic or "").lower()
    for s in sections:
        title = (s.title or "").lower()
        if title and sub and (sub in title or title in sub):
            return s.text()
    for s in sections:
        title = (s.title or "").lower()
        if title and act_topic and act_topic.lower() in title:
            return s.text()
    return parsed.markdown


def _sum_usage(usages: list[dict]) -> dict:
    out = {"input": 0, "output": 0, "reasoning": 0, "calls": len(usages)}
    for u in usages:
        out["input"] += u.get("input", 0)
        out["output"] += u.get("output", 0)
        out["reasoning"] += u.get("reasoning", 0)
    return out


def _estimate_cost(usages: list[dict]) -> float:
    total = 0.0
    for u in usages:
        price_in, price_out = PRICING.get(u["model"], (0.0, 0.0))
        total += u.get("input", 0) / 1_000_000 * price_in
        total += u.get("output", 0) / 1_000_000 * price_out
    return round(total, 6)


def build_game(
    *, parsed: ParsedDocument, source_document_id: str, title: str | None = None,
    cfg: CombatConfig | None = None, outline_model: str | None = None,
    question_model: str | None = None,
) -> dict:
    cfg = cfg or combat_tuning.default_combat_config()
    usages: list[dict] = []

    outline, u = generation.generate_outline(
        source_document_id=source_document_id, doc_markdown=parsed.markdown, model=outline_model
    )
    usages.append(u)
    if title:
        outline.title = title

    encounter_evals = []
    acts_out = []
    for act in outline.acts:
        encounters_out = []
        for enc in act.encounters:
            context = _context_for_encounter(parsed, act.syllabusTopic, enc.subTopic)
            batch, u2 = generation.generate_questions(
                encounter=enc,
                context_text=context,
                chunk_ids=[f"{source_document_id}::{enc.encounterId}"],
                model=question_model,
            )
            usages.append(u2)
            combat = combat_tuning.compute_encounter_combat(batch.questions, enc.kind, cfg)
            rewards = combat_tuning.rewards_for_encounter(enc.kind)
            # Grounding is validated against the FULL source document — a sourceQuote is
            # "grounded" if it appears anywhere in the teacher's material, not only in the
            # narrow section we fed to generation (topics can recur across acts).
            encounter_evals.append(
                evals.evaluate_encounter(enc.encounterId, batch.questions, parsed.markdown)
            )
            encounters_out.append(
                {
                    "encounterId": enc.encounterId,
                    "order": enc.order,
                    "kind": enc.kind.value,
                    "title": enc.title,
                    "enemyName": enc.enemyName,
                    "enemyFlavor": enc.enemyFlavor,
                    "subTopic": enc.subTopic,
                    "combat": combat.model_dump(mode="json"),
                    "rewards": [r.model_dump(mode="json") for r in rewards],
                    "questions": [q.model_dump(mode="json") for q in batch.questions],
                }
            )
        acts_out.append(
            {
                "actId": act.actId,
                "order": act.order,
                "title": act.title,
                "syllabusTopic": act.syllabusTopic,
                "summary": act.summary,
                "encounters": encounters_out,
            }
        )

    game = {
        "schemaVersion": SCHEMA_VERSION,
        "campaignId": outline.campaignId,
        "title": outline.title,
        "description": outline.description,
        "sourceDocumentId": source_document_id,
        "combatConfig": cfg.model_dump(mode="json"),
        "acts": acts_out,
    }
    game_eval = evals.GameEval(encounters=encounter_evals)
    return {
        "game": game,
        "eval": game_eval.summary(),
        "usage": _sum_usage(usages),
        "estimated_cost_usd": _estimate_cost(usages),
    }
