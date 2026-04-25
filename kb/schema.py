"""Postgres + pgvector schema and connection helpers.

Run `python -m kb.schema init` to create the schema in the configured DATABASE_URL.
The vector dimension default is 1024 (voyage-3); override with --dim if you switch
embedding models (text-embedding-3-large -> 3072).
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from typing import Iterator

from common.settings import settings


DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id              BIGSERIAL PRIMARY KEY,
    filename        TEXT NOT NULL,
    document_type   TEXT NOT NULL DEFAULT 'other',
    sha256          TEXT NOT NULL UNIQUE,
    page_count      INT,
    verified        BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    chunk_id        TEXT NOT NULL UNIQUE,
    document_id     BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page            INT,
    section         TEXT,
    text            TEXT NOT NULL,
    embedding       VECTOR({dim})
);

CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks(document_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""


@contextmanager
def connect() -> Iterator["psycopg.Connection"]:  # type: ignore[name-defined]
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def init_schema(dim: int = 1024) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL.format(dim=dim))
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="KB schema management")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init", help="create extension, tables, indices")
    p_init.add_argument("--dim", type=int, default=1024, help="embedding dimension")
    args = parser.parse_args()

    if args.cmd == "init":
        init_schema(dim=args.dim)
        print(f"schema initialized (dim={args.dim}) at {settings.database_url}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
