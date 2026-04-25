"""Word-window chunking with overlap.

We use word counts (not token counts) for simplicity and determinism. Default
~250-word chunks with ~50-word overlap; the embedding model can comfortably
handle these. Chunk IDs encode source filename + page + offset so they are
stable across re-ingest.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from kb.parsing import ParsedDocument


@dataclass
class TextChunk:
    chunk_id: str
    page: int | None
    section: str | None
    text: str


_WORD_RE = re.compile(r"\S+")


def _split_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _stable_chunk_id(filename: str, page: int | None, body: str) -> str:
    h = hashlib.sha1(f"{filename}|{page}|{body[:64]}".encode()).hexdigest()[:16]
    return f"{filename}:{page or 0}:{h}"


def chunk_document(
    doc: ParsedDocument,
    *,
    target_words: int = 250,
    overlap_words: int = 50,
) -> list[TextChunk]:
    if target_words <= 0 or overlap_words < 0 or overlap_words >= target_words:
        raise ValueError("Invalid chunk sizing parameters")

    out: list[TextChunk] = []
    for page in doc.pages:
        words = _split_words(page.text)
        if not words:
            continue

        step = target_words - overlap_words
        for start in range(0, len(words), step):
            window = words[start : start + target_words]
            if not window:
                break
            body = " ".join(window)
            out.append(
                TextChunk(
                    chunk_id=_stable_chunk_id(doc.filename, page.page, body),
                    page=page.page,
                    section=None,
                    text=body,
                )
            )
            if start + target_words >= len(words):
                break
    return out
