"""Curated seed funder list for Youth of Lewis County.

Every entry is a `FunderProfile` populated from public sources cited in
`sources`. The matching engine (Phase 3) is responsible for ranking these
against YOLC's profile — entries with a geographic mismatch (e.g. Mary
Reynolds Babcock, which only funds the U.S. South) are kept in the list so
the matcher can demonstrably score them low rather than us silently drop them.

Truthfulness rules (mirror the org KB):

1. Every numeric value below comes from a public source URL listed in the
   funder's `sources`. If a number isn't sourced, leave the field None
   rather than guess. The UI badges unsourced funders for review.
2. `priorities` and `geographies` are paraphrased from public materials, not
   invented. Tags use canonical lowercase strings so the matcher can compare
   them deterministically.
3. Application URLs and contact info are subject to drift. `last_verified`
   is set when an entry is touched manually; the UI highlights stale entries.

Wyatt or any human reviewer should re-verify each entry before submission.
"""

from __future__ import annotations

from datetime import datetime

from funders.models import FunderDeadline, FunderProfile


# Helper: dataset-wide verification date — set this when you sweep the list.
_VERIFIED = datetime(2026, 4, 25)


SEED_FUNDERS: list[FunderProfile] = [
    # ------------------------------------------------------------------
    # Direct geographic match: Northern NY, including Lewis County.
    # ------------------------------------------------------------------
    FunderProfile(
        slug="northern-ny-community-foundation",
        name="Northern New York Community Foundation",
        legal_name="Northern New York Community Foundation, Inc.",
        ein="23-7434243",
        classification="community_foundation",
        geographies=["lewis county, ny", "jefferson county, ny", "st. lawrence county, ny", "northern ny"],
        priorities=[
            "youth development",
            "education",
            "rural communities",
            "community capacity",
        ],
        funds_capacity_building=True,
        funds_general_operating=True,
        funds_program=True,
        website="https://www.nnycf.org/",
        application_url="https://www.nnycf.org/grants/",
        notes=(
            "Direct geographic fit. Operates the Lewis County Fund and a number of "
            "donor-advised and field-of-interest funds that have supported youth "
            "programs in Lewis County. Confirm current grant cycles before applying."
        ),
        sources=["https://www.nnycf.org/grants/"],
        last_verified=_VERIFIED,
    ),
    FunderProfile(
        slug="adirondack-foundation",
        name="Adirondack Foundation",
        ein="14-1505596",
        classification="community_foundation",
        geographies=["adirondack region, ny", "northern ny", "rural ny"],
        priorities=["youth development", "rural communities", "education", "arts"],
        funds_capacity_building=True,
        funds_general_operating=True,
        funds_program=True,
        website="https://generousact.org/",
        notes=(
            "Adjacent geography. Lewis County is on the western edge of the "
            "Adirondack Foundation's service region; verify county eligibility "
            "for each fund."
        ),
        sources=["https://generousact.org/"],
        last_verified=_VERIFIED,
    ),
    # ------------------------------------------------------------------
    # Statewide NY funders.
    # ------------------------------------------------------------------
    FunderProfile(
        slug="ny-community-trust",
        name="The New York Community Trust",
        ein="13-3062214",
        classification="community_foundation",
        geographies=["new york state", "new york city"],
        priorities=[
            "youth development",
            "education",
            "human services",
            "behavioral health",
        ],
        funds_capacity_building=True,
        funds_program=True,
        website="https://www.nycommunitytrust.org/",
        application_url="https://www.nycommunitytrust.org/information-for/for-nonprofits/",
        notes=(
            "Statewide community foundation. Most competitive grants go to "
            "NYC-based orgs; review upstate eligibility for each program."
        ),
        sources=["https://www.nycommunitytrust.org/"],
        last_verified=_VERIFIED,
    ),
    FunderProfile(
        slug="robert-sterling-clark-foundation",
        name="Robert Sterling Clark Foundation",
        ein="51-0175253",
        classification="private_foundation",
        geographies=["new york city", "new york state"],
        priorities=["leadership development", "civic engagement", "arts"],
        funds_capacity_building=True,
        funds_general_operating=True,
        website="https://www.rsclark.org/",
        notes=(
            "Primarily NYC focus. Listed as a stretch option — verify upstate "
            "eligibility before pursuing."
        ),
        sources=["https://www.rsclark.org/"],
        last_verified=_VERIFIED,
    ),
    FunderProfile(
        slug="pinkerton-foundation",
        name="The Pinkerton Foundation",
        ein="13-6161266",
        classification="private_foundation",
        geographies=["new york city"],
        priorities=["youth development", "out-of-school time", "education"],
        funds_capacity_building=True,
        funds_program=True,
        by_invitation_only=False,
        website="https://thepinkertonfoundation.org/",
        notes=(
            "Major NYC youth-development funder. Not a geographic fit for Lewis "
            "County, but listed for the matcher to demonstrate geographic exclusion."
        ),
        sources=["https://thepinkertonfoundation.org/"],
        last_verified=_VERIFIED,
    ),
    # ------------------------------------------------------------------
    # National funders that explicitly support capacity / EDs.
    # ------------------------------------------------------------------
    FunderProfile(
        slug="kresge-foundation",
        name="The Kresge Foundation",
        ein="38-1359217",
        classification="private_foundation",
        geographies=["national"],
        priorities=[
            "human services",
            "youth development",
            "community capacity",
            "rural communities",
        ],
        funds_capacity_building=True,
        funds_general_operating=False,
        website="https://kresge.org/",
        by_invitation_only=True,
        notes=(
            "Mostly invitation-only or RFP-driven. Watch their Human Services and "
            "Education program RFPs for capacity-building windows."
        ),
        sources=["https://kresge.org/"],
        last_verified=_VERIFIED,
    ),
    FunderProfile(
        slug="hearst-foundations",
        name="Hearst Foundations",
        ein="13-1684331",
        classification="private_foundation",
        geographies=["national"],
        priorities=["education", "health", "culture", "youth"],
        funds_capacity_building=True,
        funds_program=True,
        min_grant_usd=50000,
        max_grant_usd=200000,
        website="https://www.hearstfdn.org/",
        application_url="https://www.hearstfdn.org/how-to-apply",
        notes="National funder; rolling LOI process. Verify that Lewis County aligns with their current geographic strategy before applying.",
        sources=["https://www.hearstfdn.org/how-to-apply"],
        last_verified=_VERIFIED,
    ),
    FunderProfile(
        slug="wm-g-mcgowan-charitable-fund",
        name="William G. McGowan Charitable Fund",
        ein="36-3266878",
        classification="private_foundation",
        geographies=["national"],
        priorities=["education", "human services", "ethics", "leadership"],
        funds_capacity_building=True,
        website="https://www.mcgowanfund.org/",
        notes="Capacity-building grants; geographic priorities shift annually.",
        sources=["https://www.mcgowanfund.org/"],
        last_verified=_VERIFIED,
    ),
    # ------------------------------------------------------------------
    # Listed in spec; geographic mismatch retained for matcher demo.
    # ------------------------------------------------------------------
    FunderProfile(
        slug="mary-reynolds-babcock",
        name="Mary Reynolds Babcock Foundation",
        ein="56-6035458",
        classification="private_foundation",
        geographies=["us south"],  # AL, AR, FL, GA, KY, LA, MS, NC, SC, TN, VA
        priorities=["community capacity", "rural communities", "racial equity"],
        funds_capacity_building=True,
        funds_general_operating=True,
        website="https://www.mrbf.org/",
        notes=(
            "Geographic mismatch: MRBF only funds organizations in 11 Southern "
            "states. Retained in the seed list so the matching engine can "
            "demonstrably score it low for Lewis County, NY."
        ),
        sources=["https://www.mrbf.org/our-grantmaking"],
        last_verified=_VERIFIED,
    ),
    # ------------------------------------------------------------------
    # State and federal funding streams (not 501(c)(3) funders).
    # ------------------------------------------------------------------
    FunderProfile(
        slug="nys-ocfs-youth-development",
        name="NYS OCFS Youth Development Program",
        classification="government_program",
        geographies=["new york state"],
        priorities=["youth development", "positive youth development", "prevention"],
        funds_capacity_building=False,
        funds_program=True,
        website="https://ocfs.ny.gov/programs/youth/",
        notes=(
            "Funded through municipal youth bureaus. Lewis County-based orgs "
            "typically access these funds through the county youth bureau "
            "rather than directly."
        ),
        sources=["https://ocfs.ny.gov/programs/youth/"],
        last_verified=_VERIFIED,
    ),
    FunderProfile(
        slug="nys-ocfs-youth-safe-spaces",
        name="NYS OCFS Youth Safe Spaces (and equivalents)",
        classification="government_program",
        geographies=["new york state"],
        priorities=["lgbtq+ youth", "drop-in", "youth development"],
        funds_capacity_building=False,
        funds_program=True,
        website="https://ocfs.ny.gov/",
        notes=(
            "OCFS periodically issues RFPs for youth safe-space and drop-in "
            "programming. Track grants.gov and the OCFS site for active "
            "solicitations."
        ),
        sources=["https://ocfs.ny.gov/"],
        last_verified=_VERIFIED,
    ),
    FunderProfile(
        slug="nys-omh-adolescent-behavioral-health",
        name="NYS OMH Adolescent Behavioral Health Funding",
        classification="government_program",
        geographies=["new york state"],
        priorities=["adolescent mental health", "behavioral health", "prevention"],
        funds_capacity_building=False,
        funds_program=True,
        website="https://omh.ny.gov/",
        notes=(
            "OMH issues periodic RFPs targeting adolescent behavioral health and "
            "youth peer support. Track the OMH grants page for live solicitations."
        ),
        sources=["https://omh.ny.gov/"],
        last_verified=_VERIFIED,
    ),
]


def seed_index() -> dict[str, FunderProfile]:
    """Slug-keyed index of the seed list, for lookups during ingest tests."""
    return {f.slug: f for f in SEED_FUNDERS}
