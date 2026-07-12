"""Pipeline: ParsedDocument -> validated, combat-tuned, evaluated game JSON.

Orchestrates outline -> per-encounter questions -> deterministic combat tuning -> evals,
then assembles the final game dict (matching docs/BUILD-SPEC.md §4 example shape) and
reports token usage + an estimated cost.
"""

from __future__ import annotations

from app.core.config import settings
from app.schemas.game import SCHEMA_VERSION, CombatConfig
from app.services import combat_tuning, evals, generation, retrieval, runmap
from app.services.chunking import count_tokens
from app.services.ingestion import ParsedDocument, flatten

# Top-k chunks retrieved as question-gen context when a doc has no usable headings.
RETRIEVAL_K = 5

# Per-1M-token (input, output) USD — research-current mid-2026; re-verify before relying.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.5": (5.00, 30.00),
    # GPT-4 family fallbacks (more stable instruction-following per the user's experience)
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # embeddings (input-priced only)
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def _section_context(parsed: ParsedDocument, act_topic: str, sub_topic: str) -> str | None:
    """Focused context from the section tree, or None if no heading matches (→ use retrieval)."""
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
    return None


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
    question_model: str | None = None, max_encounters: int | None = None,
    outline_token_budget: int | None = None,
) -> dict:
    cfg = cfg or combat_tuning.default_combat_config()
    usages: list[dict] = []

    # Oversized docs: outline from a condensed digest (map step) so we stay within the
    # input budget. Normal-sized docs feed their cleaned text directly.
    budget = (
        outline_token_budget if outline_token_budget is not None
        else settings.outline_token_budget
    )
    if count_tokens(parsed.markdown) > budget:
        outline_source, digest_usages = generation.summarize_for_outline(
            parsed, model=outline_model
        )
        usages.extend(digest_usages)
    else:
        outline_source = parsed.markdown

    outline, u = generation.generate_outline(
        source_document_id=source_document_id, doc_markdown=outline_source, model=outline_model
    )
    usages.append(u)
    if title:
        outline.title = title

    # Remove any duplicated sub-topics the outline model may have produced, then optionally
    # cap the encounter count (used to bound cost when testing against large documents).
    outline = generation.dedupe_outline(outline)
    if max_encounters is not None:
        remaining = max_encounters
        for act in outline.acts:
            act.encounters = act.encounters[: max(0, remaining)]
            remaining -= len(act.encounters)
        outline.acts = [a for a in outline.acts if a.encounters]

    encounter_evals = []
    acts_out = []
    index: retrieval.RetrievalIndex | None = None
    for act in outline.acts:
        encounters_out = []
        for enc in act.encounters:
            # Prefer a matching section (free, focused). If the doc has no usable
            # structure, lazily build a retrieval index once and fetch top-k chunks so
            # question-gen context stays small regardless of document size.
            context = _section_context(parsed, act.syllabusTopic, enc.subTopic)
            chunk_ids = [f"{source_document_id}::{enc.subTopic}"]
            if context is None:
                if index is None:
                    index, emb_usage = retrieval.build_index(parsed)
                    usages.append(emb_usage)
                hits = index.search(enc.subTopic, k=RETRIEVAL_K)
                if hits:
                    context = "\n\n".join(h.text for h in hits)
                    chunk_ids = [f"{source_document_id}::chunk_{h.ord}" for h in hits]
                else:
                    context = parsed.markdown  # last-resort fallback
            batch, u2 = generation.generate_questions(
                encounter=enc,
                context_text=context,
                chunk_ids=chunk_ids,
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
                "map": runmap.build_act_map(
                    encounters_out, seed=f"{outline.campaignId}:{act.actId}"
                ),
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
