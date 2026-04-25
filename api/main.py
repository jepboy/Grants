"""FastAPI app — optional Phase 1 surface alongside the Streamlit UI.

Exposes /draft for programmatic use (e.g., scripts or future pipeline runs).
Run with: `uvicorn api.main:app --reload`.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from common.citations import Draft
from drafter.orchestrate import draft_and_verify
from kb.retrieval import list_documents
from verifier.verify import VerificationReport


app = FastAPI(title="YOLC Grants — Phase 1")


class DraftRequest(BaseModel):
    rfp_text: str
    rfp_title: str | None = None
    funder: str | None = None
    funder_context: str | None = None
    k_per_section: int = 8
    run_verifier: bool = True


class DraftResponse(BaseModel):
    draft: Draft
    report: VerificationReport | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/documents")
def documents() -> list[dict]:
    return list_documents()


@app.post("/draft", response_model=DraftResponse)
def draft(req: DraftRequest) -> DraftResponse:
    draft_obj, report, _ = draft_and_verify(
        req.rfp_text,
        rfp_title=req.rfp_title,
        funder=req.funder,
        funder_context=req.funder_context,
        k_per_section=req.k_per_section,
        run_verifier=req.run_verifier,
    )
    return DraftResponse(draft=draft_obj, report=report)
