"""Layer 2: Funder intelligence.

Public surface:
    - models   : Pydantic FunderProfile and friends
    - seed     : curated seed list (rural-NY youth capacity builders)
    - propublica : ProPublica Nonprofit Explorer client
    - ingest   : sync seed + ProPublica into Postgres
    - repo     : query helpers (used by UI/API/Phase 3 matcher)
"""

from funders.models import (
    FunderProfile,
    FunderClassification,
    FunderDeadline,
    FunderGrant,
)

__all__ = [
    "FunderProfile",
    "FunderClassification",
    "FunderDeadline",
    "FunderGrant",
]
