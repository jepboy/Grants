"""Schema/validation tests for funder models. No DB, no network."""

from __future__ import annotations

import pytest

from funders.models import FunderDeadline, FunderProfile


def test_ein_is_normalized_to_dash_format():
    f = FunderProfile(slug="x", name="X", ein="123456789")
    assert f.ein == "12-3456789"


def test_ein_with_dashes_is_accepted():
    f = FunderProfile(slug="x", name="X", ein="12-3456789")
    assert f.ein == "12-3456789"


def test_invalid_ein_rejected():
    with pytest.raises(ValueError):
        FunderProfile(slug="x", name="X", ein="not-an-ein")


def test_slug_is_lowercased_and_dashed():
    f = FunderProfile(slug="Northern NY Foundation", name="X")
    assert f.slug == "northern-ny-foundation"


def test_government_program_can_have_no_ein():
    f = FunderProfile(
        slug="nys-ocfs",
        name="OCFS",
        classification="government_program",
        geographies=["new york state"],
    )
    assert f.ein is None
    assert f.classification == "government_program"


def test_headline_includes_geo_and_typical_grant():
    f = FunderProfile(
        slug="x",
        name="Acme",
        geographies=["lewis county, ny", "rural ny"],
        typical_grant_usd=75_000,
    )
    h = f.headline()
    assert "Acme" in h
    assert "lewis county, ny" in h
    assert "$75,000" in h


def test_deadlines_default_empty():
    f = FunderProfile(slug="x", name="X")
    assert f.deadlines == []
    f2 = FunderProfile(
        slug="x",
        name="X",
        deadlines=[FunderDeadline(program_name="General", rolling=True)],
    )
    assert f2.deadlines[0].rolling is True
