"""Per-section grounded drafter.

Pipeline per section:
    1. Retrieve top-k chunks from the org KB.
    2. Pack those chunks as Anthropic citation-enabled documents.
    3. Call the Messages API with the drafter system prompt.
    4. Parse the JSON the model returned (body + needs_input).
    5. Walk the returned content blocks and turn each cited span into a
       [^cN] inline marker, building the section's Citation list along the way.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from anthropic import Anthropic

from common.citations import Citation, Chunk, Draft, DraftSection, RetrievalHit
from common.settings import settings
from drafter.prompts import DRAFTER_SYSTEM, build_user_message
from kb.retrieval import retrieve


_QUESTION_SPLIT_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+[.)]|[-*•]|Q\d+[:.])\s+",
    flags=re.IGNORECASE,
)


def parse_rfp_sections(rfp_text: str) -> list[str]:
    """Best-effort split of an RFP into discrete questions.

    Heuristic only — accepts numbered lists, bullets, and "Q1:" patterns. If
    nothing matches, returns the whole RFP as a single section.
    """
    text = rfp_text.strip()
    if not text:
        return []

    # If the very first character is a list marker, there is no preamble to
    # discard. Otherwise, the first split element is preamble; drop it only
    # when it looks like a short header (e.g., "Please answer the following:").
    starts_with_marker = bool(re.match(_QUESTION_SPLIT_RE, text))

    parts = [p.strip() for p in _QUESTION_SPLIT_RE.split(text) if p and p.strip()]
    if not starts_with_marker and len(parts) > 1 and len(parts[0].split()) < 12:
        parts = parts[1:]

    return parts if len(parts) > 1 else [text]


def _hits_to_documents(hits: list[RetrievalHit]) -> list[dict]:
    """Convert retrieval hits into Anthropic citation-enabled document blocks.

    Each hit becomes one document. The order of this list defines the
    document_index that comes back on each citation.
    """
    docs: list[dict] = []
    for h in hits:
        c = h.chunk
        title_bits = [c.source_filename]
        if c.page is not None:
            title_bits.append(f"p.{c.page}")
        title_bits.append(c.document_type)
        docs.append(
            {
                "type": "document",
                "source": {
                    "type": "text",
                    "media_type": "text/plain",
                    "data": c.text,
                },
                "title": " | ".join(title_bits),
                "citations": {"enabled": True},
            }
        )
    return docs


def _extract_json(text: str) -> dict:
    """Parse the model's JSON output, tolerant of leading/trailing whitespace."""
    text = text.strip()
    # Strip a fenced code block if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Drafter did not return a JSON object: {text[:200]}")
    return json.loads(text[start : end + 1])


def _block_get(block, key: str, default=None):
    """Read a field from either a dict-shaped or object-shaped content block."""
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _walk_content_blocks(
    content_blocks: Iterable, hits: list[RetrievalHit]
) -> tuple[str, list[Citation]]:
    """Reconstruct the model's text and pull out structured citations.

    Anthropic returns content as a list of text blocks; cited spans are their
    own blocks with a `citations` list attached. We append a [^cN] marker
    after each cited span and build a parallel Citation list ordered by
    appearance.
    """
    citations: list[Citation] = []
    seen: dict[tuple[str, int, int], int] = {}
    out_parts: list[str] = []

    for block in content_blocks:
        if _block_get(block, "type") != "text":
            continue
        out_parts.append(_block_get(block, "text", "") or "")

        cits = _block_get(block, "citations") or []
        for cit in cits:
            doc_idx = _block_get(cit, "document_index")
            cited_text = _block_get(cit, "cited_text", "") or ""
            start = _block_get(cit, "start_char_index", 0) or 0
            end = _block_get(cit, "end_char_index", 0) or 0

            if doc_idx is None or doc_idx >= len(hits):
                continue
            chunk: Chunk = hits[doc_idx].chunk
            key = (chunk.chunk_id, int(start), int(end))
            if key in seen:
                marker_idx = seen[key]
            else:
                marker_idx = len(citations) + 1
                seen[key] = marker_idx
                citations.append(Citation.from_chunk(chunk, snippet=cited_text or chunk.text[:240]))
            out_parts.append(f"[^c{marker_idx}]")
    return "".join(out_parts), citations


_NEEDS_INPUT_RE = re.compile(r"\[NEEDS INPUT:[^\]]+\]")


def _harvest_needs_input(body: str, declared: list[str]) -> list[str]:
    """Trust but verify — pull every literal marker from the body, then merge."""
    found = _NEEDS_INPUT_RE.findall(body)
    seen: set[str] = set()
    out: list[str] = []
    for item in [*found, *declared]:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def draft_section(
    question: str,
    *,
    funder_context: str | None = None,
    k: int = 8,
    client: Anthropic | None = None,
    model: str | None = None,
) -> DraftSection:
    """Draft one section of a grant application, grounded in the org KB."""
    client = client or Anthropic(api_key=settings.anthropic_api_key)
    model = model or settings.drafter_model

    hits = retrieve(question, k=k)

    # User content: documents first, then the actual question.
    user_content: list[dict] = []
    user_content.extend(_hits_to_documents(hits))
    user_content.append({"type": "text", "text": build_user_message(question, funder_context)})

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=DRAFTER_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    body_with_markers, citations = _walk_content_blocks(response.content, hits)

    # The model's output is JSON. We have to parse it from the reconstructed
    # text — but inline [^cN] markers were inserted into that same text, so
    # parse from a copy with markers stripped, then re-attach markers on the
    # body field by re-walking.
    raw_text = "".join(
        (_block_get(b, "text", "") or "")
        for b in response.content
        if _block_get(b, "type") == "text"
    )
    parsed = _extract_json(raw_text)
    body = parsed.get("body", "").strip()
    declared_needs = parsed.get("needs_input") or []
    if not isinstance(declared_needs, list):
        declared_needs = [str(declared_needs)]

    # If the model put the JSON-wrapped body in raw_text, the citation markers
    # we built in body_with_markers reference the *whole* response (including
    # the JSON braces). We do a best-effort: if body appears in
    # body_with_markers, return that slice; otherwise fall back to body alone.
    final_body = body
    idx = body_with_markers.find(body[:80]) if body else -1
    if idx != -1:
        # Take the marker-decorated slice that starts at the body
        candidate = body_with_markers[idx:]
        # Trim at the next JSON-y trailer if any
        candidate = re.split(r"\"\s*,\s*\"needs_input\"", candidate)[0]
        final_body = candidate.strip().rstrip('"').rstrip()

    needs_input = _harvest_needs_input(final_body, [str(x) for x in declared_needs])

    return DraftSection(
        question=question,
        body=final_body,
        citations=citations,
        needs_input=needs_input,
    )


def draft_application(
    rfp_text: str,
    *,
    rfp_title: str | None = None,
    funder: str | None = None,
    funder_context: str | None = None,
    k_per_section: int = 8,
    client: Anthropic | None = None,
    model: str | None = None,
) -> Draft:
    """Top-level entry: split an RFP into sections and draft each."""
    questions = parse_rfp_sections(rfp_text)
    client = client or Anthropic(api_key=settings.anthropic_api_key)
    model = model or settings.drafter_model

    sections = [
        draft_section(
            q,
            funder_context=funder_context,
            k=k_per_section,
            client=client,
            model=model,
        )
        for q in questions
    ]

    return Draft(
        rfp_title=rfp_title,
        funder=funder,
        sections=sections,
        ai_assisted=True,
        model=model,
    )
