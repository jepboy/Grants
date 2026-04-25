"""Orchestrator: draft + verify in one call.

The verifier needs the full retrieval set used by the drafter, not just the
chunks the model ended up citing. This module preserves those hits so callers
(UI, API) get a Draft and a VerificationReport from a single function.
"""

from __future__ import annotations

from anthropic import Anthropic

from common.citations import Chunk, Draft
from common.settings import settings
from drafter.draft import draft_section, parse_rfp_sections
from kb.retrieval import retrieve
from verifier.verify import VerificationReport, verify_draft


def draft_and_verify(
    rfp_text: str,
    *,
    rfp_title: str | None = None,
    funder: str | None = None,
    funder_context: str | None = None,
    k_per_section: int = 8,
    run_verifier: bool = True,
    client: Anthropic | None = None,
    drafter_model: str | None = None,
    verifier_model: str | None = None,
) -> tuple[Draft, VerificationReport | None, list[list[Chunk]]]:
    """Run the full Phase 1 pipeline and return draft + report + retrieval set."""
    client = client or Anthropic(api_key=settings.anthropic_api_key)
    drafter_model = drafter_model or settings.drafter_model
    verifier_model = verifier_model or settings.verifier_model

    questions = parse_rfp_sections(rfp_text)

    chunks_per_section: list[list[Chunk]] = []
    sections = []
    for q in questions:
        hits = retrieve(q, k=k_per_section)
        chunks_per_section.append([h.chunk for h in hits])

        # Re-use those hits inside draft_section instead of re-retrieving — but
        # the public draft_section signature retrieves itself for simplicity.
        # To avoid double retrieval, pass them through a thin shim:
        section = _draft_section_with_hits(
            q,
            hits=hits,
            funder_context=funder_context,
            client=client,
            model=drafter_model,
        )
        sections.append(section)

    draft = Draft(
        rfp_title=rfp_title,
        funder=funder,
        sections=sections,
        ai_assisted=True,
        model=drafter_model,
    )

    report: VerificationReport | None = None
    if run_verifier:
        report = verify_draft(
            draft,
            chunks_per_section,
            use_llm=True,
            client=client,
            model=verifier_model,
        )
    return draft, report, chunks_per_section


def _draft_section_with_hits(question, *, hits, funder_context, client, model):
    """Internal: drive draft_section but skip the second retrieval call."""
    # Tiny shim: monkey-patch retrieve for this scope. Easier than threading
    # an `existing_hits` parameter through the public API.
    from drafter import draft as _draft_mod

    original = _draft_mod.retrieve
    _draft_mod.retrieve = lambda *_args, **_kwargs: hits  # type: ignore[assignment]
    try:
        return draft_section(
            question,
            funder_context=funder_context,
            k=len(hits) or 8,
            client=client,
            model=model,
        )
    finally:
        _draft_mod.retrieve = original  # type: ignore[assignment]
