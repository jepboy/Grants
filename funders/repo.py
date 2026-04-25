"""Read/write helpers for the funders tables.

The ingest module writes through here; the UI/API/Phase-3 matcher read
through here. Centralizing access keeps the row<->FunderProfile mapping in
one place.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable, Optional

from funders.models import FunderDeadline, FunderGrant, FunderProfile
from funders.schema import connect


# ---------- Mapping helpers --------------------------------------------------


def _profile_from_rows(
    funder_row: dict,
    geographies: list[str],
    priorities: list[str],
    deadlines: list[dict],
    grants: list[dict],
) -> FunderProfile:
    return FunderProfile(
        slug=funder_row["slug"],
        name=funder_row["name"],
        legal_name=funder_row.get("legal_name"),
        ein=funder_row.get("ein"),
        classification=funder_row.get("classification") or "other",
        geographies=geographies,
        priorities=priorities,
        min_grant_usd=funder_row.get("min_grant_usd"),
        max_grant_usd=funder_row.get("max_grant_usd"),
        typical_grant_usd=funder_row.get("typical_grant_usd"),
        applicant_min_budget_usd=funder_row.get("applicant_min_budget_usd"),
        applicant_max_budget_usd=funder_row.get("applicant_max_budget_usd"),
        funds_capacity_building=bool(funder_row.get("funds_capacity_building")),
        funds_executive_director=bool(funder_row.get("funds_executive_director")),
        funds_general_operating=bool(funder_row.get("funds_general_operating")),
        funds_program=bool(funder_row.get("funds_program", True)),
        application_url=funder_row.get("application_url"),
        requires_loi=bool(funder_row.get("requires_loi")),
        by_invitation_only=bool(funder_row.get("by_invitation_only")),
        deadlines=[FunderDeadline(**d) for d in deadlines],
        website=funder_row.get("website"),
        contact_email=funder_row.get("contact_email"),
        contact_phone=funder_row.get("contact_phone"),
        past_grants=[FunderGrant(**g) for g in grants],
        notes=funder_row.get("notes"),
        sources=list(funder_row.get("sources") or []),
        last_verified=funder_row.get("last_verified"),
    )


# ---------- Writes -----------------------------------------------------------


def upsert_funder(profile: FunderProfile, *, propublica_raw: Optional[dict] = None) -> int:
    """Insert or update a funder by slug. Returns the row id.

    Children (geographies, priorities, deadlines, grants) are replaced wholesale —
    simpler than diff-and-merge and these tables are small.
    """
    now = datetime.now(timezone.utc)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO funders (
                    slug, name, legal_name, ein, classification,
                    min_grant_usd, max_grant_usd, typical_grant_usd,
                    applicant_min_budget_usd, applicant_max_budget_usd,
                    funds_capacity_building, funds_executive_director,
                    funds_general_operating, funds_program,
                    application_url, requires_loi, by_invitation_only,
                    website, contact_email, contact_phone, notes, sources,
                    last_verified, propublica_raw, last_synced_at, updated_at
                ) VALUES (
                    %(slug)s, %(name)s, %(legal_name)s, %(ein)s, %(classification)s,
                    %(min_grant_usd)s, %(max_grant_usd)s, %(typical_grant_usd)s,
                    %(applicant_min_budget_usd)s, %(applicant_max_budget_usd)s,
                    %(funds_capacity_building)s, %(funds_executive_director)s,
                    %(funds_general_operating)s, %(funds_program)s,
                    %(application_url)s, %(requires_loi)s, %(by_invitation_only)s,
                    %(website)s, %(contact_email)s, %(contact_phone)s, %(notes)s,
                    %(sources)s, %(last_verified)s, %(propublica_raw)s,
                    %(last_synced_at)s, %(updated_at)s
                )
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    legal_name = EXCLUDED.legal_name,
                    ein = EXCLUDED.ein,
                    classification = EXCLUDED.classification,
                    min_grant_usd = EXCLUDED.min_grant_usd,
                    max_grant_usd = EXCLUDED.max_grant_usd,
                    typical_grant_usd = EXCLUDED.typical_grant_usd,
                    applicant_min_budget_usd = EXCLUDED.applicant_min_budget_usd,
                    applicant_max_budget_usd = EXCLUDED.applicant_max_budget_usd,
                    funds_capacity_building = EXCLUDED.funds_capacity_building,
                    funds_executive_director = EXCLUDED.funds_executive_director,
                    funds_general_operating = EXCLUDED.funds_general_operating,
                    funds_program = EXCLUDED.funds_program,
                    application_url = EXCLUDED.application_url,
                    requires_loi = EXCLUDED.requires_loi,
                    by_invitation_only = EXCLUDED.by_invitation_only,
                    website = EXCLUDED.website,
                    contact_email = EXCLUDED.contact_email,
                    contact_phone = EXCLUDED.contact_phone,
                    notes = EXCLUDED.notes,
                    sources = EXCLUDED.sources,
                    last_verified = EXCLUDED.last_verified,
                    propublica_raw = COALESCE(EXCLUDED.propublica_raw, funders.propublica_raw),
                    last_synced_at = EXCLUDED.last_synced_at,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
                """,
                {
                    "slug": profile.slug,
                    "name": profile.name,
                    "legal_name": profile.legal_name,
                    "ein": profile.ein,
                    "classification": profile.classification,
                    "min_grant_usd": profile.min_grant_usd,
                    "max_grant_usd": profile.max_grant_usd,
                    "typical_grant_usd": profile.typical_grant_usd,
                    "applicant_min_budget_usd": profile.applicant_min_budget_usd,
                    "applicant_max_budget_usd": profile.applicant_max_budget_usd,
                    "funds_capacity_building": profile.funds_capacity_building,
                    "funds_executive_director": profile.funds_executive_director,
                    "funds_general_operating": profile.funds_general_operating,
                    "funds_program": profile.funds_program,
                    "application_url": profile.application_url,
                    "requires_loi": profile.requires_loi,
                    "by_invitation_only": profile.by_invitation_only,
                    "website": profile.website,
                    "contact_email": profile.contact_email,
                    "contact_phone": profile.contact_phone,
                    "notes": profile.notes,
                    "sources": profile.sources,
                    "last_verified": profile.last_verified,
                    "propublica_raw": json.dumps(propublica_raw) if propublica_raw else None,
                    "last_synced_at": now if propublica_raw else None,
                    "updated_at": now,
                },
            )
            funder_id = cur.fetchone()["id"]

            # Replace children
            cur.execute("DELETE FROM funder_geographies WHERE funder_id = %s", (funder_id,))
            for g in profile.geographies:
                cur.execute(
                    "INSERT INTO funder_geographies (funder_id, region) VALUES (%s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (funder_id, g),
                )

            cur.execute("DELETE FROM funder_priorities WHERE funder_id = %s", (funder_id,))
            for p in profile.priorities:
                cur.execute(
                    "INSERT INTO funder_priorities (funder_id, priority) VALUES (%s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (funder_id, p),
                )

            cur.execute("DELETE FROM funder_deadlines WHERE funder_id = %s", (funder_id,))
            for d in profile.deadlines:
                cur.execute(
                    """
                    INSERT INTO funder_deadlines
                        (funder_id, program_name, deadline, rolling, application_url, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        funder_id,
                        d.program_name,
                        d.deadline,
                        d.rolling,
                        d.application_url,
                        d.notes,
                    ),
                )

            cur.execute("DELETE FROM funder_grants WHERE funder_id = %s", (funder_id,))
            for grant in profile.past_grants:
                cur.execute(
                    """
                    INSERT INTO funder_grants
                        (funder_id, grantee_name, grantee_ein, amount_usd, purpose,
                         fiscal_year, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        funder_id,
                        grant.grantee_name,
                        grant.grantee_ein,
                        grant.amount_usd,
                        grant.purpose,
                        grant.fiscal_year,
                        grant.source,
                    ),
                )
        conn.commit()
        return funder_id


# ---------- Reads ------------------------------------------------------------


def list_funders() -> list[FunderProfile]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM funders ORDER BY name")
            funders = cur.fetchall()
            cur.execute(
                "SELECT funder_id, region FROM funder_geographies ORDER BY funder_id"
            )
            geos: dict[int, list[str]] = {}
            for r in cur.fetchall():
                geos.setdefault(r["funder_id"], []).append(r["region"])
            cur.execute(
                "SELECT funder_id, priority FROM funder_priorities ORDER BY funder_id"
            )
            pris: dict[int, list[str]] = {}
            for r in cur.fetchall():
                pris.setdefault(r["funder_id"], []).append(r["priority"])
            cur.execute("SELECT * FROM funder_deadlines ORDER BY funder_id")
            dls: dict[int, list[dict]] = {}
            for r in cur.fetchall():
                dls.setdefault(r["funder_id"], []).append(
                    {
                        "program_name": r["program_name"],
                        "deadline": r["deadline"],
                        "rolling": r["rolling"],
                        "application_url": r["application_url"],
                        "notes": r["notes"],
                    }
                )
            cur.execute("SELECT * FROM funder_grants ORDER BY funder_id")
            grs: dict[int, list[dict]] = {}
            for r in cur.fetchall():
                grs.setdefault(r["funder_id"], []).append(
                    {
                        "grantee_name": r["grantee_name"],
                        "grantee_ein": r["grantee_ein"],
                        "amount_usd": r["amount_usd"],
                        "purpose": r["purpose"],
                        "fiscal_year": r["fiscal_year"],
                        "source": r["source"],
                    }
                )

    return [
        _profile_from_rows(
            f,
            geographies=geos.get(f["id"], []),
            priorities=pris.get(f["id"], []),
            deadlines=dls.get(f["id"], []),
            grants=grs.get(f["id"], []),
        )
        for f in funders
    ]


def get_funder(slug: str) -> Optional[FunderProfile]:
    matches = [f for f in list_funders() if f.slug == slug]
    return matches[0] if matches else None


def funders_with_priority(tag: str) -> list[FunderProfile]:
    return [f for f in list_funders() if tag.lower() in [p.lower() for p in f.priorities]]


def upsert_many(profiles: Iterable[FunderProfile]) -> int:
    n = 0
    for p in profiles:
        upsert_funder(p)
        n += 1
    return n
