"""Retrieval: semantic kNN over chunks, returning Chunk objects ready for citation.

The drafter and verifier both call `retrieve(query, k)` — they never reach the
DB directly. That keeps citation construction in one place.
"""

from __future__ import annotations

from common.citations import Chunk, RetrievalHit
from kb.embeddings import Embedder, get_embedder
from kb.schema import connect


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def retrieve(
    query: str,
    *,
    k: int = 8,
    embedder: Embedder | None = None,
) -> list[RetrievalHit]:
    """Return top-k chunks most relevant to `query`, with scores in [0, 1]."""
    if not query.strip():
        return []

    embedder = embedder or get_embedder()
    qvec = embedder.embed([query], input_type="query")[0]
    qlit = _vector_literal(qvec)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.chunk_id, c.page, c.section, c.text,
                       d.filename, d.document_type, d.verified,
                       1 - (c.embedding <=> %s::vector) AS score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (qlit, qlit, k),
            )
            rows = cur.fetchall()

    hits: list[RetrievalHit] = []
    for r in rows:
        chunk = Chunk(
            chunk_id=r["chunk_id"],
            source_filename=r["filename"],
            document_type=r["document_type"],
            page=r["page"],
            section=r["section"],
            text=r["text"],
            verified=r["verified"],
        )
        hits.append(RetrievalHit(chunk=chunk, score=float(r["score"])))
    return hits


def list_documents() -> list[dict]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.filename, d.document_type, d.page_count, d.verified,
                       d.ingested_at, COUNT(c.id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.ingested_at DESC
                """
            )
            return [dict(r) for r in cur.fetchall()]
