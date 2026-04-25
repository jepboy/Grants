"""Claim extraction.

We use two complementary methods:

1. **Deterministic regex extraction.** Numbers, currency, percentages, years,
   and dates. These are the highest-risk claims and we never want to depend on
   the LLM agreeing with us about whether they exist in the text.

2. **LLM-based extraction** (in `verify.py`) for named entities, partnerships,
   and qualitative outcomes — categories that regexes can't capture cleanly.

The deterministic layer is the "belt"; the LLM layer is the "suspenders".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# A "claim" here is just a string the verifier will try to match against the
# source chunks. We keep type as a tag so the report can group by category.
@dataclass(frozen=True)
class NumericClaim:
    surface: str  # exact text as it appears in the draft
    kind: str  # money | percent | year | count | date


_MONEY_RE = re.compile(
    r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s?(?:million|billion|k|m|b)\b)?",
    re.I,
)
_PERCENT_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?\s?%")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_DATE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?\b",
    re.I,
)
# Standalone counts of 2+ digits, including comma-grouped (e.g. "9,876").
# Money/percent/year matches are recorded first and the post-filter skips
# anything inside an already-claimed span.
_COUNT_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{2,}\b")

# Anything inside [NEEDS INPUT: ...] or after the "Projected:" label is excluded
# from numeric verification. Projections are explicitly forward-looking and
# don't need a source.
_NEEDS_INPUT_BLOCK_RE = re.compile(r"\[NEEDS INPUT:[^\]]+\]")
_PROJECTION_LINE_RE = re.compile(r"(?im)^\s*Projected:.*$")
# Legal/structural identifiers — not factual claims about the organization.
# IRC section references, USC citations, EIN format placeholders, etc.
_LEGAL_ID_RE = re.compile(
    r"\b501\s*\(\s*c\s*\)\s*\(\s*3\s*\)|\b501c3\b|\bsection\s+\d+\s*\([a-z]\)\s*\(\d+\)\b",
    re.I,
)


def _strip_exempt_regions(text: str) -> str:
    text = _NEEDS_INPUT_BLOCK_RE.sub(" ", text)
    text = _PROJECTION_LINE_RE.sub(" ", text)
    text = _LEGAL_ID_RE.sub(" ", text)
    return text


def extract_numeric_claims(text: str) -> list[NumericClaim]:
    """Pull numeric/date claims from `text`, excluding NEEDS-INPUT and projections."""
    text = _strip_exempt_regions(text)

    found: list[NumericClaim] = []
    seen_spans: list[tuple[int, int]] = []

    def _add(match: re.Match, kind: str) -> None:
        span = match.span()
        # Skip if already covered by an earlier (more specific) match
        for s, e in seen_spans:
            if span[0] >= s and span[1] <= e:
                return
        seen_spans.append(span)
        found.append(NumericClaim(surface=match.group(0).strip(), kind=kind))

    for m in _MONEY_RE.finditer(text):
        _add(m, "money")
    for m in _PERCENT_RE.finditer(text):
        _add(m, "percent")
    for m in _DATE_RE.finditer(text):
        _add(m, "date")
    for m in _YEAR_RE.finditer(text):
        _add(m, "year")
    for m in _COUNT_RE.finditer(text):
        _add(m, "count")

    return found


def normalize(s: str) -> str:
    """Lowercase, collapse whitespace, drop common punctuation for fuzzy matching."""
    s = s.lower()
    s = re.sub(r"[,$%]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def claim_supported_by_chunks(claim: NumericClaim, chunk_texts: Iterable[str]) -> bool:
    needle = normalize(claim.surface)
    for ch in chunk_texts:
        if needle in normalize(ch):
            return True
    return False
