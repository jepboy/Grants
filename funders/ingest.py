"""Funder ingestion CLI.

Two operations:

    python -m funders.ingest seed
        Upsert every entry in funders.seed.SEED_FUNDERS into Postgres.

    python -m funders.ingest enrich [--ein 12-3456789] [--slug northern-ny-community-foundation] [--all]
        Pull the ProPublica payload for a funder (or all funders that have an
        EIN) and store it in `propublica_raw`. We currently use the payload
        only for archival + future PDF parsing; we don't overwrite curated
        fields with auto-extracted ones (those are higher-trust manual values).

We deliberately do NOT auto-rewrite curated `priorities` / `geographies` from
ProPublica. The seed list is a human-verified source of truth; enrichment is
additive metadata only.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable

from funders.models import FunderProfile
from funders.propublica import (
    ProPublicaClient,
    ProPublicaError,
    classification_from_propublica,
)
from funders.repo import list_funders, upsert_funder
from funders.seed import SEED_FUNDERS


def load_seed() -> int:
    """Upsert every seed funder. Returns the count."""
    n = 0
    for profile in SEED_FUNDERS:
        upsert_funder(profile)
        n += 1
    return n


def enrich_funder(profile: FunderProfile, *, client: ProPublicaClient) -> dict | None:
    """Fetch ProPublica payload and persist it. Returns the raw payload."""
    if not profile.ein:
        return None
    try:
        raw = client.organization(profile.ein)
    except ProPublicaError as e:
        print(f"  skip {profile.slug} ({profile.ein}): {e}", file=sys.stderr)
        return None

    # Optional: refine classification if ours is "other" and ProPublica has a clearer signal
    refined = classification_from_propublica(raw)
    if profile.classification == "other" and refined != "other":
        profile = profile.model_copy(update={"classification": refined})

    upsert_funder(profile, propublica_raw=raw)
    return raw


def enrich_many(profiles: Iterable[FunderProfile], *, client: ProPublicaClient | None = None) -> int:
    client = client or ProPublicaClient()
    try:
        n = 0
        for p in profiles:
            if not p.ein:
                continue
            if enrich_funder(p, client=client) is not None:
                n += 1
        return n
    finally:
        if client is not None:
            client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Funder ingestion")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="upsert every entry in the seed list")
    enrich = sub.add_parser("enrich", help="pull ProPublica payload(s)")
    g = enrich.add_mutually_exclusive_group(required=True)
    g.add_argument("--ein", help="enrich a single funder by EIN")
    g.add_argument("--slug", help="enrich a single funder by slug")
    g.add_argument("--all", action="store_true", help="enrich every funder with an EIN")

    args = parser.parse_args()

    if args.cmd == "seed":
        n = load_seed()
        print(f"seeded {n} funders")
        return 0

    if args.cmd == "enrich":
        funders = list_funders()
        if args.ein:
            target = next((f for f in funders if f.ein == args.ein), None)
            if not target:
                print(f"no funder with EIN {args.ein}", file=sys.stderr)
                return 2
            with ProPublicaClient() as client:
                enrich_funder(target, client=client)
            print(f"enriched {target.slug}")
            return 0
        if args.slug:
            target = next((f for f in funders if f.slug == args.slug), None)
            if not target:
                print(f"no funder with slug {args.slug}", file=sys.stderr)
                return 2
            with ProPublicaClient() as client:
                enrich_funder(target, client=client)
            print(f"enriched {target.slug}")
            return 0
        if args.all:
            n = enrich_many(funders)
            print(f"enriched {n} funders")
            return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
