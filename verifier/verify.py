"""Verification pass.

Inputs: a Draft (from drafter) and the chunks that were available to the
drafter. Output: a VerificationReport flagging any claim that cannot be
matched to a source chunk.

We do this in two stages:

1. Deterministic numeric verification (free, fast, never wrong about presence).
2. Optional LLM-based fact-check pass — a separate Anthropic call that
   re-extracts qualitative claims and asks the model whether each is supported
   by the source chunks. The LLM is prompted to err on the side of "not
   supported" if uncertain.

The LLM pass is gated by a flag so unit tests can exercise the deterministic
path without API calls.
"""

from __future__ import annotations

import json
from typing import Iterable

from anthropic import Anthropic
from pydantic import BaseModel, Field

from common.citations import Chunk, Citation, Draft, DraftSection
from common.settings import settings
from verifier.extract import (
    NumericClaim,
    claim_supported_by_chunks,
    extract_numeric_claims,
)


class FlaggedClaim(BaseModel):
    section_question: str
    surface: str
    kind: str  # money | percent | year | count | date | qualitative
    reason: str


class VerificationReport(BaseModel):
    passed: bool
    total_claims: int
    flagged: list[FlaggedClaim] = Field(default_factory=list)
    needs_input_count: int = 0

    @property
    def summary(self) -> str:
        if self.passed:
            return f"OK — {self.total_claims} claims verified, {self.needs_input_count} [NEEDS INPUT] flags."
        return (
            f"BLOCKED — {len(self.flagged)} unsupported claim(s) of {self.total_claims}. "
            f"{self.needs_input_count} [NEEDS INPUT] flags."
        )


_FACT_CHECK_SYSTEM = """You are a strict grant-application fact checker. You will be given a drafted answer and a set of source chunks from the organization's knowledge base. Your job: list every factual claim about the organization that is NOT directly supported by the source chunks.

Be conservative. If a claim is even slightly beyond what the sources say, list it. Projections (lines starting with "Projected:") are exempt — do not flag them. Material inside [NEEDS INPUT: ...] is exempt.

Output JSON only:
{
  "unsupported": [
    {"surface": "<the exact claim text>", "reason": "<why the sources don't support it>"}
  ]
}
If everything is supported, return {"unsupported": []}.
"""


def _llm_fact_check(
    section: DraftSection,
    chunks: list[Chunk],
    *,
    client: Anthropic,
    model: str,
) -> list[FlaggedClaim]:
    if not chunks:
        # No sources available — every factual claim is unsupported by construction.
        # The drafter should have emitted [NEEDS INPUT] across the board; this is
        # a backstop in case it didn't.
        return [
            FlaggedClaim(
                section_question=section.question,
                surface=section.body[:200],
                kind="qualitative",
                reason="No source chunks were available to the drafter.",
            )
        ]

    documents = [
        {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": ch.text},
            "title": f"{ch.source_filename} | p.{ch.page or '-'} | {ch.document_type}",
            "citations": {"enabled": False},
        }
        for ch in chunks
    ]
    user_text = (
        f"DRAFT ANSWER TO CHECK:\n{section.body}\n\n"
        "Identify every claim about the organization that is not directly supported by the source documents above. "
        "Output the JSON object specified in the system prompt — nothing else."
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_FACT_CHECK_SYSTEM,
        messages=[
            {"role": "user", "content": [*documents, {"type": "text", "text": user_text}]}
        ],
    )

    raw = "".join(
        getattr(b, "text", "")
        for b in response.content
        if getattr(b, "type", None) == "text"
    ).strip()

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        parsed = json.loads(raw[start : end + 1]) if start != -1 else {"unsupported": []}
    except json.JSONDecodeError:
        # Fail closed: if we can't parse the checker's output, flag the whole section.
        return [
            FlaggedClaim(
                section_question=section.question,
                surface="<verifier output unparsable>",
                kind="qualitative",
                reason="LLM fact-checker returned unparsable output; treat as unsupported.",
            )
        ]

    out: list[FlaggedClaim] = []
    for item in parsed.get("unsupported", []) or []:
        out.append(
            FlaggedClaim(
                section_question=section.question,
                surface=str(item.get("surface", ""))[:400],
                kind="qualitative",
                reason=str(item.get("reason", "unsupported")),
            )
        )
    return out


def verify_draft(
    draft: Draft,
    chunks_per_section: list[list[Chunk]],
    *,
    use_llm: bool = True,
    client: Anthropic | None = None,
    model: str | None = None,
) -> VerificationReport:
    """Run both deterministic and (optionally) LLM-based verification.

    `chunks_per_section[i]` must be the list of chunks the drafter retrieved
    for `draft.sections[i]`. (The Draft itself only stores the citations the
    model actually used; verification needs the full retrieval set.)
    """
    if len(chunks_per_section) != len(draft.sections):
        raise ValueError("chunks_per_section must have one entry per draft section")

    flagged: list[FlaggedClaim] = []
    total_claims = 0
    needs_input_count = 0

    client = client or (Anthropic(api_key=settings.anthropic_api_key) if use_llm else None)
    model = model or settings.verifier_model

    for section, chunks in zip(draft.sections, chunks_per_section):
        needs_input_count += len(section.needs_input)

        # 0. Empty-chunks guard. If the drafter had no retrieval set for this
        # section, every factual claim is unsupported by construction. We flag
        # the section here so the deterministic path catches it without needing
        # the LLM checker. We exempt sections whose body is entirely
        # [NEEDS INPUT] markers and/or "Projected:" lines.
        from verifier.extract import _strip_exempt_regions

        if not chunks and _strip_exempt_regions(section.body).strip():
            flagged.append(
                FlaggedClaim(
                    section_question=section.question,
                    surface=section.body[:200],
                    kind="qualitative",
                    reason="No source chunks were available for this section.",
                )
            )
            total_claims += 1
            continue

        # 1. Deterministic numeric pass
        numeric_claims = extract_numeric_claims(section.body)
        total_claims += len(numeric_claims)
        chunk_texts = [c.text for c in chunks]
        for claim in numeric_claims:
            if not claim_supported_by_chunks(claim, chunk_texts):
                flagged.append(
                    FlaggedClaim(
                        section_question=section.question,
                        surface=claim.surface,
                        kind=claim.kind,
                        reason=f"{claim.kind} value not present in any retrieved source chunk",
                    )
                )

        # 2. LLM qualitative pass
        if use_llm and client is not None:
            qual = _llm_fact_check(section, chunks, client=client, model=model)
            total_claims += len(qual)
            flagged.extend(qual)

    return VerificationReport(
        passed=not flagged,
        total_claims=total_claims,
        flagged=flagged,
        needs_input_count=needs_input_count,
    )
