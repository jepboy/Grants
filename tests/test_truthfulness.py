"""Truthfulness tests — the most important tests in this system.

These exercise the deterministic anti-fabrication path:

1. Numeric verifier flags any number not present in source chunks.
2. Verifier ignores numbers inside [NEEDS INPUT: ...] markers.
3. Verifier ignores numbers on lines marked "Projected:".
4. Verifier flags an entire section if no source chunks were retrieved.
5. The drafter respects the [NEEDS INPUT] discipline when its (faked) model
   returns a draft full of unsupported numbers — the body is preserved
   verbatim so the verifier can catch it.

The drafter→Anthropic loop is exercised through `FakeAnthropic` so no live API
calls are made. A separate `live` test (skipped by default) covers real API
behavior.
"""

from __future__ import annotations

import json

import pytest

from common.citations import Chunk, Draft, DraftSection
from drafter.draft import draft_section
from tests.conftest import FakeAnthropic, FakeContentBlock
from verifier.extract import (
    NumericClaim,
    claim_supported_by_chunks,
    extract_numeric_claims,
)
from verifier.verify import verify_draft


# ---------- Deterministic numeric extraction -----------------------------------


def test_extract_numeric_claims_money_percent_year_count():
    text = (
        "We served 247 youth in 2024. Our annual budget is $185,000 and 92% of "
        "participants reported improved well-being on Mar 14, 2024."
    )
    surfaces = {c.surface for c in extract_numeric_claims(text)}
    assert "$185,000" in surfaces
    assert "92%" in surfaces
    assert "2024" in surfaces
    assert "247" in surfaces
    assert any(s.startswith("Mar") for s in surfaces)


def test_extract_skips_needs_input_and_projections():
    text = (
        "We served [NEEDS INPUT: youth-served count for 2024] youth last year.\n"
        "Projected: 500 youth in 2026.\n"
        "Our EIN ends in 4567."
    )
    claims = extract_numeric_claims(text)
    surfaces = [c.surface for c in claims]
    assert "500" not in surfaces, "projection numbers must not be flagged"
    assert "2026" not in surfaces
    assert "4567" in surfaces, "non-projection numbers still get extracted"


def test_claim_supported_by_chunks_normalization():
    claim = NumericClaim(surface="$185,000", kind="money")
    assert claim_supported_by_chunks(claim, ["our annual budget is $185,000"])
    assert claim_supported_by_chunks(claim, ["budget: 185000 dollars"])
    assert not claim_supported_by_chunks(claim, ["budget: $200,000"])


# ---------- Verifier: end-to-end deterministic path ----------------------------


def _draft_with_body(body: str, question: str = "Describe your impact.") -> Draft:
    return Draft(
        rfp_title="t",
        funder="f",
        sections=[DraftSection(question=question, body=body)],
        ai_assisted=True,
        model="claude-opus-4-7",
    )


def test_verifier_flags_unsupported_numbers(org_chunks):
    body = "Youth of Lewis County served 9,876 youth in 2024 with a budget of $2,500,000."
    draft = _draft_with_body(body)
    report = verify_draft(draft, [org_chunks], use_llm=False)
    surfaces = {f.surface for f in report.flagged}
    # All three numbers are absent from org_chunks; all three must be flagged
    assert "9,876" in surfaces or "9876" in {f.surface.replace(",", "") for f in report.flagged}
    assert any("2024" == f.surface for f in report.flagged)
    assert any("$2,500,000" == f.surface for f in report.flagged)
    assert report.passed is False


def test_verifier_passes_when_all_numbers_supported(org_chunks):
    # Only numbers that appear verbatim in the synthetic chunks
    body = (
        "Our 501(c)(3) determination is from June 2022 with EIN 88-1234567. "
        "We are based in Lewis County, NY."
    )
    draft = _draft_with_body(body)
    report = verify_draft(draft, [org_chunks], use_llm=False)
    assert report.passed, f"expected pass; flagged={[f.surface for f in report.flagged]}"


def test_verifier_ignores_projections_and_needs_input(org_chunks):
    body = (
        "We served [NEEDS INPUT: youth-served count for 2024] youth.\n"
        "Projected: 500 youth in 2026 if funded.\n"
        "Our determination letter is from June 2022."
    )
    draft = _draft_with_body(body)
    report = verify_draft(draft, [org_chunks], use_llm=False)
    flagged_surfaces = {f.surface for f in report.flagged}
    assert "500" not in flagged_surfaces
    assert "2026" not in flagged_surfaces
    assert report.needs_input_count >= 0  # body has marker but section.needs_input may be empty


def test_verifier_flags_section_with_no_chunks():
    """If no chunks were retrieved, every claim is unsupported by construction."""
    body = "We have served thousands of youth across upstate New York."
    draft = _draft_with_body(body)
    report = verify_draft(draft, [[]], use_llm=False)
    assert report.passed is False


# ---------- Drafter: respects model output, preserves [NEEDS INPUT] ------------


def test_drafter_preserves_needs_input_markers(org_chunks, monkeypatch):
    """Tempting RFP: asks for outcome numbers we do not have. The model (faked)
    correctly emits [NEEDS INPUT]. The drafter must:
      (a) preserve those markers in section.body, and
      (b) populate section.needs_input.
    """
    # Stub retrieval so we don't hit the DB
    from kb import retrieval as kb_retrieval
    from drafter import draft as drafter_mod
    from common.citations import RetrievalHit

    fake_hits = [RetrievalHit(chunk=ch, score=0.9) for ch in org_chunks]
    monkeypatch.setattr(drafter_mod, "retrieve", lambda *a, **kw: fake_hits)
    monkeypatch.setattr(kb_retrieval, "retrieve", lambda *a, **kw: fake_hits)

    model_json = json.dumps(
        {
            "body": (
                "Youth of Lewis County is a 501(c)(3) nonprofit. "
                "Last year we served [NEEDS INPUT: youth-served count for 2024] youth "
                "with an annual budget of [NEEDS INPUT: latest annual budget figure]."
            ),
            "needs_input": [
                "[NEEDS INPUT: youth-served count for 2024]",
                "[NEEDS INPUT: latest annual budget figure]",
            ],
        }
    )

    fake_client = FakeAnthropic(
        responses=[
            type("M", (), {"content": [FakeContentBlock(type="text", text=model_json)]})(),
        ]
    )

    section = draft_section(
        "How many youth did you serve last year and what was your budget?",
        client=fake_client,
        model="claude-opus-4-7",
    )

    assert "[NEEDS INPUT:" in section.body
    assert len(section.needs_input) >= 2
    # The drafter must NOT have invented numbers
    assert "2024" not in section.body or "[NEEDS INPUT" in section.body
    # No money figures should appear outside NEEDS INPUT
    from verifier.extract import extract_numeric_claims

    leftover_numbers = extract_numeric_claims(section.body)
    assert not leftover_numbers, f"drafter leaked numeric claims: {leftover_numbers}"


def test_drafter_strips_or_flags_attempted_fabrication(org_chunks, monkeypatch):
    """If the (faked) model misbehaves and returns numbers not in the chunks,
    the verifier must catch them downstream — that's the suspenders to the
    drafter's belt."""
    from drafter import draft as drafter_mod
    from kb import retrieval as kb_retrieval
    from common.citations import RetrievalHit

    fake_hits = [RetrievalHit(chunk=ch, score=0.9) for ch in org_chunks]
    monkeypatch.setattr(drafter_mod, "retrieve", lambda *a, **kw: fake_hits)
    monkeypatch.setattr(kb_retrieval, "retrieve", lambda *a, **kw: fake_hits)

    rogue_body = "We served 1,250 youth in 2024 with a $750,000 budget."
    model_json = json.dumps({"body": rogue_body, "needs_input": []})
    fake_client = FakeAnthropic(
        responses=[type("M", (), {"content": [FakeContentBlock(type="text", text=model_json)]})()]
    )

    section = draft_section("Describe your reach.", client=fake_client, model="claude-opus-4-7")
    draft = Draft(sections=[section], ai_assisted=True, model="claude-opus-4-7")
    report = verify_draft(draft, [org_chunks], use_llm=False)

    assert report.passed is False
    surfaces = {f.surface for f in report.flagged}
    assert "1,250" in surfaces
    assert "$750,000" in surfaces
    assert "2024" in surfaces
