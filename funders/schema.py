"""Postgres schema for funder data.

Run `python -m funders.schema init` to create. Co-exists with the kb tables
in the same database so cross-querying (e.g. matching) is easy in Phase 3.

The raw ProPublica payload is stored as JSONB so we can re-derive structured
fields after schema changes without re-hitting the API.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from typing import Iterator

from common.settings import settings


DDL = """
CREATE TABLE IF NOT EXISTS funders (
    id                          BIGSERIAL PRIMARY KEY,
    slug                        TEXT NOT NULL UNIQUE,
    name                        TEXT NOT NULL,
    legal_name                  TEXT,
    ein                         TEXT UNIQUE,
    classification              TEXT NOT NULL DEFAULT 'other',
    min_grant_usd               BIGINT,
    max_grant_usd               BIGINT,
    typical_grant_usd           BIGINT,
    applicant_min_budget_usd    BIGINT,
    applicant_max_budget_usd    BIGINT,
    funds_capacity_building     BOOLEAN NOT NULL DEFAULT FALSE,
    funds_executive_director    BOOLEAN NOT NULL DEFAULT FALSE,
    funds_general_operating     BOOLEAN NOT NULL DEFAULT FALSE,
    funds_program               BOOLEAN NOT NULL DEFAULT TRUE,
    application_url             TEXT,
    requires_loi                BOOLEAN NOT NULL DEFAULT FALSE,
    by_invitation_only          BOOLEAN NOT NULL DEFAULT FALSE,
    website                     TEXT,
    contact_email               TEXT,
    contact_phone               TEXT,
    notes                       TEXT,
    sources                     TEXT[] NOT NULL DEFAULT '{}',
    last_verified               TIMESTAMPTZ,
    propublica_raw              JSONB,
    last_synced_at              TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS funder_geographies (
    id           BIGSERIAL PRIMARY KEY,
    funder_id    BIGINT NOT NULL REFERENCES funders(id) ON DELETE CASCADE,
    region       TEXT NOT NULL,
    UNIQUE (funder_id, region)
);

CREATE TABLE IF NOT EXISTS funder_priorities (
    id           BIGSERIAL PRIMARY KEY,
    funder_id    BIGINT NOT NULL REFERENCES funders(id) ON DELETE CASCADE,
    priority     TEXT NOT NULL,
    UNIQUE (funder_id, priority)
);

CREATE TABLE IF NOT EXISTS funder_deadlines (
    id              BIGSERIAL PRIMARY KEY,
    funder_id       BIGINT NOT NULL REFERENCES funders(id) ON DELETE CASCADE,
    program_name    TEXT NOT NULL,
    deadline        DATE,
    rolling         BOOLEAN NOT NULL DEFAULT FALSE,
    application_url TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS funder_grants (
    id              BIGSERIAL PRIMARY KEY,
    funder_id       BIGINT NOT NULL REFERENCES funders(id) ON DELETE CASCADE,
    grantee_name    TEXT NOT NULL,
    grantee_ein     TEXT,
    amount_usd      BIGINT,
    purpose         TEXT,
    fiscal_year     INT,
    source          TEXT NOT NULL DEFAULT 'manual'
);

CREATE INDEX IF NOT EXISTS funders_classification_idx ON funders(classification);
CREATE INDEX IF NOT EXISTS funder_geographies_region_idx ON funder_geographies(region);
CREATE INDEX IF NOT EXISTS funder_priorities_priority_idx ON funder_priorities(priority);
CREATE INDEX IF NOT EXISTS funder_deadlines_deadline_idx ON funder_deadlines(deadline);
CREATE INDEX IF NOT EXISTS funder_grants_grantee_idx ON funder_grants(grantee_name);
"""


@contextmanager
def connect() -> Iterator["psycopg.Connection"]:  # type: ignore[name-defined]
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def init_schema() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Funder schema management")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create funder tables and indices")
    args = parser.parse_args()

    if args.cmd == "init":
        init_schema()
        print(f"funder schema initialized at {settings.database_url}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
