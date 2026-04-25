"""Shared citation/chunk types used across kb, drafter, and verifier."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

DocumentType = Literal[
    "501c3_letter",
    "ocfs_agreement",
    "annual_budget",
    "financial_statement",
    "board_roster",
    "bylaws",
    "program_data",
    "prior_application",
    "event_record",
    "policy",
    "other",
]


class Chunk(BaseModel):
    """A chunk of a source document, with everything needed to cite it."""

    chunk_id: str
    source_filename: str
    document_type: DocumentType = "other"
    page: Optional[int] = None
    section: Optional[str] = None
    text: str
    verified: bool = False  # human-reviewed source
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class Citation(BaseModel):
    """Pointer back to the source chunk that supports a claim."""

    chunk_id: str
    source_filename: str
    document_type: DocumentType
    page: Optional[int] = None
    text_snippet: str  # the supporting text
    verified: bool = False

    @classmethod
    def from_chunk(cls, chunk: Chunk, snippet: str | None = None) -> "Citation":
        return cls(
            chunk_id=chunk.chunk_id,
            source_filename=chunk.source_filename,
            document_type=chunk.document_type,
            page=chunk.page,
            text_snippet=snippet or chunk.text,
            verified=chunk.verified,
        )


class RetrievalHit(BaseModel):
    chunk: Chunk
    score: float


class DraftSection(BaseModel):
    """A single drafted section of a grant application."""

    question: str
    body: str  # contains inline [^cN] markers
    citations: list[Citation] = Field(default_factory=list)
    needs_input: list[str] = Field(default_factory=list)


class Draft(BaseModel):
    """Full grant draft. AI-assistance flag is mandatory."""

    rfp_title: Optional[str] = None
    funder: Optional[str] = None
    sections: list[DraftSection]
    ai_assisted: bool = True  # disclosure flag, always True for our drafts
    model: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    def all_needs_input(self) -> list[str]:
        out: list[str] = []
        for s in self.sections:
            out.extend(s.needs_input)
        return out
