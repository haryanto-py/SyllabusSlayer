"""OpenAI Structured-Outputs generation (docs/BUILD-SPEC.md §5.3, §5.5).

Two staged calls keep each schema under the 100-property / 5-level limits:
  1. generate_outline  -> CampaignOutline (cheap model)
  2. generate_questions -> QuestionBatch per encounter (authoring model)

Uses the Responses API `parse` helper (preferred for gpt-5.x reasoning models) with
reasoning effort 'low' and a capped output budget to control cost. Pydantic models
carry strict-mode-friendly schemas (extra='forbid', all fields required, optionals as
`X | None`); their validators enforce per-type field correctness on parse.
"""

from __future__ import annotations

from openai import OpenAI

from app.core.config import settings
from app.schemas.game import CampaignOutline, EncounterStub, QuestionBatch

OUTLINE_INSTRUCTIONS = (
    "You are a curriculum designer turning a teacher's source material into the OUTLINE of a "
    "roguelike quiz-RPG campaign. Map the document's structure to the campaign: top-level topics "
    "become Acts; each Act gets 1-3 Encounters (minion/elite/boss) covering its sub-topics, with a "
    "boss for the act's most important sub-topic. Give vivid but tasteful enemy names/flavor tied to "
    "the topic. Do NOT write questions yet. Do NOT invent facts beyond the source. Set schemaVersion "
    "to '1.0.0' and use the provided sourceDocumentId. Give every act/encounter a stable, unique, "
    "slug-like id. targetQuestionCount should be 2-4 per encounter."
)

QUESTION_INSTRUCTIONS = (
    "You are an expert assessment author writing quiz questions for ONE encounter of a roguelike "
    "quiz-RPG, grounded STRICTLY in the provided source text. Rules:\n"
    "- Write exactly the requested number of questions, all about the encounter's sub-topic.\n"
    "- Ground BOTH the correct answer and the distractors in the source; never use outside facts.\n"
    "- For every item, set sourceQuote to a SHORT VERBATIM snippet copied from the source text that "
    "supports the answer, and sourceChunkIds to the provided chunk id(s).\n"
    "- multiple_choice: exactly ONE correct option plus 3 plausible, homogeneous distractors; no "
    "'all/none of the above'; no cueing.\n"
    "- Vary Bloom levels across the set (mix remember/understand/apply/analyze as the material allows).\n"
    "- Fill ONLY the fields for the chosen questionType; set every other per-type field to null.\n"
    "- Always write a one-sentence explanation justifying the correct answer.\n"
    "- Prefer multiple_choice and true_false for reliability; use other types only when they fit."
)


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _parse(model: str, instructions: str, user: str, text_format, max_output_tokens: int):
    resp = _client().responses.parse(
        model=model,
        instructions=instructions,
        input=[{"role": "user", "content": user}],
        text_format=text_format,
        reasoning={"effort": "low"},
        max_output_tokens=max_output_tokens,
    )
    parsed = resp.output_parsed
    if parsed is None:
        raise RuntimeError(
            f"no parsed output (status={resp.status}, "
            f"incomplete={getattr(resp, 'incomplete_details', None)})"
        )
    u = resp.usage
    details = getattr(u, "output_tokens_details", None)
    usage = {
        "model": model,
        "input": getattr(u, "input_tokens", 0) or 0,
        "output": getattr(u, "output_tokens", 0) or 0,
        "reasoning": getattr(details, "reasoning_tokens", 0) or 0,
    }
    return parsed, usage


def generate_outline(
    *, source_document_id: str, doc_markdown: str, model: str | None = None,
    max_output_tokens: int = 4000,
) -> tuple[CampaignOutline, dict]:
    user = f"sourceDocumentId: {source_document_id}\n\nSOURCE MATERIAL (Markdown):\n\n{doc_markdown}"
    return _parse(
        model or settings.openai_model_nano, OUTLINE_INSTRUCTIONS, user,
        CampaignOutline, max_output_tokens,
    )


def generate_questions(
    *, encounter: EncounterStub, context_text: str, chunk_ids: list[str] | None = None,
    model: str | None = None, max_output_tokens: int = 4000, max_retries: int = 1,
) -> tuple[QuestionBatch, dict]:
    model = model or settings.openai_model_mini
    chunk_ids = chunk_ids or [f"{encounter.encounterId}::ctx"]
    base_user = (
        f"encounterId: {encounter.encounterId}\n"
        f"title: {encounter.title}\n"
        f"subTopic: {encounter.subTopic}\n"
        f"number of questions to write: {encounter.targetQuestionCount}\n"
        f"available sourceChunkIds: {chunk_ids}\n\n"
        f"SOURCE TEXT for this encounter:\n\n{context_text}"
    )
    last_err: str | None = None
    for attempt in range(max_retries + 1):
        user = base_user if attempt == 0 else (
            base_user + f"\n\nThe previous attempt failed validation: {last_err}\n"
            "Fix ONLY that problem and return valid items."
        )
        try:
            batch, usage = _parse(model, QUESTION_INSTRUCTIONS, user, QuestionBatch, max_output_tokens)
            batch.encounterId = encounter.encounterId
            return batch, usage
        except Exception as exc:  # noqa: BLE001 — includes Pydantic validation from parse
            last_err = str(exc)[:300]
    raise RuntimeError(f"question generation failed for {encounter.encounterId}: {last_err}")
