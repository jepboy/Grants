"""Pydantic models for funder data.

Same truthfulness discipline as the org KB: every field that comes from a
specific source carries that source's name in `evidence`. Fields without
evidence are flagged so the matching engine can downweight them and the UI
can surface them for review.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


FunderClassification = Literal[
    "private_foundation",
    "public_charity",
    "community_foundation",
    "corporate_foundation",
    "government_program",  # state/federal funding stream, not a 501(c)(3)
    "operating_foundation",
    "other",
]


class FunderGrant(BaseModel):
    """A past grant a funder has made — useful signal for matching."""

    grantee_name: str
    grantee_ein: Optional[str] = None
    amount_usd: Optional[int] = None
    purpose: Optional[str] = None
    fiscal_year: Optional[int] = None
    source: str = "manual"  # 'propublica_990pf' | 'manual' | 'website'


class FunderDeadline(BaseModel):
    program_name: str
    deadline: Optional[date] = None  # None means rolling/unknown
    rolling: bool = False
    application_url: Optional[str] = None
    notes: Optional[str] = None


class FunderProfile(BaseModel):
    """A funder we might apply to.

    `ein` is the unique key for IRS-registered funders; for state/federal
    programs `ein` is None and `slug` is the unique key.
    """

    slug: str  # stable internal identifier (e.g. "northern-ny-community-foundation")
    name: str
    legal_name: Optional[str] = None
    ein: Optional[str] = None
    classification: FunderClassification = "other"

    # Geography — free-form labels matched by the engine. Use lowercase
    # canonical strings: "lewis county, ny", "rural ny", "new york state",
    # "us south", "national".
    geographies: list[str] = Field(default_factory=list)

    # Stated funding priorities. Short, lowercase tags.
    priorities: list[str] = Field(default_factory=list)

    # Funding range (per grant)
    min_grant_usd: Optional[int] = None
    max_grant_usd: Optional[int] = None
    typical_grant_usd: Optional[int] = None

    # Org-size eligibility (applicant budget bounds)
    applicant_min_budget_usd: Optional[int] = None
    applicant_max_budget_usd: Optional[int] = None

    # Capacity-building specific
    funds_capacity_building: bool = False
    funds_executive_director: bool = False  # explicit: pays for ED salary
    funds_general_operating: bool = False
    funds_program: bool = True

    # Process
    application_url: Optional[str] = None
    requires_loi: bool = False
    by_invitation_only: bool = False
    deadlines: list[FunderDeadline] = Field(default_factory=list)

    # Contact
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    # Track record
    past_grants: list[FunderGrant] = Field(default_factory=list)

    # Soft signals / human notes
    notes: Optional[str] = None

    # Sourcing — every claim that isn't directly verifiable from a public
    # source should land here so the matcher can downweight unverified entries.
    sources: list[str] = Field(default_factory=list)
    last_verified: Optional[datetime] = None

    @field_validator("ein")
    @classmethod
    def _normalize_ein(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 9:
            raise ValueError(f"EIN must have 9 digits, got {len(digits)}: {v!r}")
        return f"{digits[:2]}-{digits[2:]}"

    @field_validator("slug")
    @classmethod
    def _slug_lowercase(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "-")

    def headline(self) -> str:
        """Short human-readable summary for list views."""
        bits = [self.name]
        if self.geographies:
            bits.append("; ".join(self.geographies[:2]))
        if self.typical_grant_usd:
            bits.append(f"~${self.typical_grant_usd:,}")
        elif self.max_grant_usd:
            bits.append(f"up to ${self.max_grant_usd:,}")
        return " — ".join(bits)
