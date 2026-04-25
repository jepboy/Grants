"""Invariants for the curated seed list.

We don't test specific names — those are likely to evolve. We do test that:
    - every entry is well-formed (Pydantic catches that),
    - every entry has at least one geography and one priority,
    - every entry has at least one source URL (so a human can verify),
    - slugs are unique,
    - there is at least one funder geographically aligned with Lewis County, NY,
    - there is at least one government_program entry (state/federal stream).
"""

from __future__ import annotations

import pytest

from funders.seed import SEED_FUNDERS, seed_index


def test_no_duplicate_slugs():
    slugs = [f.slug for f in SEED_FUNDERS]
    assert len(slugs) == len(set(slugs)), "duplicate slug in seed list"


def test_every_funder_has_geographies_and_priorities():
    for f in SEED_FUNDERS:
        assert f.geographies, f"{f.slug} has no geographies"
        assert f.priorities, f"{f.slug} has no priorities"


def test_every_funder_has_at_least_one_source():
    for f in SEED_FUNDERS:
        assert f.sources, f"{f.slug} has no source URL — unverifiable claims must be sourced"


def test_includes_lewis_county_or_northern_ny_match():
    matched = [
        f for f in SEED_FUNDERS
        if any("lewis county" in g or "northern ny" in g for g in f.geographies)
    ]
    assert matched, "seed list must include at least one direct-fit funder for Lewis County"


def test_includes_at_least_one_government_program():
    govt = [f for f in SEED_FUNDERS if f.classification == "government_program"]
    assert govt, "seed list must include OCFS / OMH / federal funding streams"


def test_seed_index_is_slug_keyed():
    idx = seed_index()
    for slug, profile in idx.items():
        assert profile.slug == slug


def test_eins_are_unique_when_present():
    eins = [f.ein for f in SEED_FUNDERS if f.ein]
    assert len(eins) == len(set(eins)), "duplicate EIN in seed list"


def test_geographic_mismatch_funder_is_documented():
    """MRBF is intentionally retained to demonstrate matcher's geo exclusion.
    Its notes must explain why."""
    mrbf = next((f for f in SEED_FUNDERS if "mary-reynolds-babcock" in f.slug), None)
    if mrbf is None:
        pytest.skip("MRBF not in current seed list")
    assert mrbf.notes and "mismatch" in mrbf.notes.lower()
