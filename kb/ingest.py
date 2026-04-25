"""Ingestion pipeline: parse -> chunk -> embed -> upsert into Postgres.

Idempotent on document SHA-256: re-ingesting the same file is a no-op. Chunk
IDs are stable, so re-ingesting an edited document removes only the changed
chunks (full replace per document is the simpler default we ship now).
"""

from __future__ import annotations

from pathlib import Path

from common.citations import DocumentType
from kb.chunking import chunk_document
from kb.embeddings import Embedder, get_embedder
from kb.parsing import ParsedDocument, parse_document
from kb.schema import connect


def _vector_literal(vec: list[float]) -> str:
    """pgvector accepts a stringified array literal."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def _upsert_document(conn, doc: ParsedDocument) -> tuple[int, bool]:
    """Returns (document_id, was_new)."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM documents WHERE sha256 = %s", (doc.sha256,))
        row = cur.fetchone()
        if row:
            return row["id"], False
        cur.execute(
            """
            INSERT INTO documents (filename, document_type, sha256, page_count)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (doc.filename, doc.document_type, doc.sha256, len(doc.pages)),
        )
        return cur.fetchone()["id"], True


def _replace_chunks(conn, document_id: int, chunks, embeddings: list[list[float]]) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        for ch, emb in zip(chunks, embeddings):
            cur.execute(
                """
                INSERT INTO chunks (chunk_id, document_id, page, section, text, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                """,
                (ch.chunk_id, document_id, ch.page, ch.section, ch.text, _vector_literal(emb)),
            )


def ingest_path(
    path: str | Path,
    document_type: DocumentType = "other",
    *,
    embedder: Embedder | None = None,
) -> dict:
    """Ingest a single file. Returns a small result dict for the UI/CLI."""
    parsed = parse_document(path, document_type=document_type)
    if not parsed.pages:
        return {"filename": parsed.filename, "chunks": 0, "skipped": "empty"}

    chunks = chunk_document(parsed)
    embedder = embedder or get_embedder()
    vectors = embedder.embed([c.text for c in chunks], input_type="document")

    with connect() as conn:
        doc_id, was_new = _upsert_document(conn, parsed)
        # Always replace chunks so embedding-model changes propagate.
        _replace_chunks(conn, doc_id, chunks, vectors)
        conn.commit()

    return {
        "filename": parsed.filename,
        "document_type": parsed.document_type,
        "document_id": doc_id,
        "new_document": was_new,
        "chunks": len(chunks),
    }
