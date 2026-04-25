"""Streamlit UI for Phase 1.

Three tabs:
    - Knowledge Base: upload org documents, see what's been ingested.
    - Draft from RFP: paste an RFP, get a grounded draft with citations and
      [NEEDS INPUT] flags.
    - Verification: see the verifier's report on the latest draft.

Run with: `streamlit run ui/app.py`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import streamlit as st

from common.citations import Draft, DocumentType
from drafter.orchestrate import draft_and_verify
from kb.ingest import ingest_path
from kb.retrieval import list_documents


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


st.set_page_config(page_title="YOLC Grants", layout="wide")
st.title("Youth of Lewis County — Grant System")
st.caption(
    "Grounded grant drafting. Every claim is traced to a source document or flagged "
    "[NEEDS INPUT]. The system never fabricates."
)


tab_kb, tab_draft, tab_verify, tab_funders = st.tabs(
    ["Knowledge Base", "Draft from RFP", "Verification", "Funders"]
)


with tab_kb:
    st.header("Upload organizational documents")
    st.write(
        "Supported: PDF, DOCX, TXT, MD. Choose the document type — it becomes "
        "metadata on every chunk and citation."
    )

    doc_type = st.selectbox("Document type", options=list(get_args(DocumentType)))
    files = st.file_uploader(
        "Select one or more files",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
    )
    if st.button("Ingest", disabled=not files):
        for uf in files:
            target = UPLOAD_DIR / uf.name
            target.write_bytes(uf.getvalue())
            try:
                result = ingest_path(target, document_type=doc_type)
                st.success(f"{uf.name}: {result['chunks']} chunks ingested")
            except Exception as e:  # noqa: BLE001
                st.error(f"{uf.name}: {e}")

    st.subheader("Ingested documents")
    try:
        docs = list_documents()
    except Exception as e:  # noqa: BLE001
        st.warning(f"DB not reachable: {e}")
        docs = []
    if docs:
        st.dataframe(docs, use_container_width=True)
    else:
        st.info("No documents ingested yet.")


def _render_draft(draft: Draft) -> None:
    st.markdown(f"**Model:** `{draft.model}` &nbsp;&nbsp; **AI-assisted:** ✅ (disclosure flag set)")
    if draft.funder:
        st.markdown(f"**Funder:** {draft.funder}")

    for i, section in enumerate(draft.sections, start=1):
        with st.expander(f"Section {i}: {section.question[:90]}", expanded=True):
            st.markdown(section.body)

            if section.needs_input:
                st.warning("Needs input from the team:")
                for n in section.needs_input:
                    st.markdown(f"- {n}")

            if section.citations:
                st.markdown("**Sources for this section**")
                for j, cit in enumerate(section.citations, start=1):
                    page = f", p.{cit.page}" if cit.page is not None else ""
                    verified_badge = " ✅ verified" if cit.verified else ""
                    st.markdown(
                        f"`[^c{j}]` **{cit.source_filename}**{page} ({cit.document_type}){verified_badge}\n\n"
                        f"> {cit.text_snippet[:400]}"
                    )


with tab_draft:
    st.header("Draft a grant section from an RFP")
    rfp_title = st.text_input("RFP title (optional)")
    funder = st.text_input("Funder name (optional)")
    funder_context = st.text_area(
        "Funder voice / length notes (optional, style cues only — not facts)",
        height=80,
    )
    rfp_text = st.text_area(
        "Paste the RFP questions here",
        height=240,
        placeholder="1. Describe your organization's mission and history...\n2. ...",
    )
    k = st.slider("Chunks retrieved per section", 4, 16, 8)

    run = st.button("Generate grounded draft", type="primary", disabled=not rfp_text.strip())
    if run:
        with st.spinner("Retrieving + drafting + verifying…"):
            try:
                draft, report, _ = draft_and_verify(
                    rfp_text,
                    rfp_title=rfp_title or None,
                    funder=funder or None,
                    funder_context=funder_context or None,
                    k_per_section=k,
                )
                st.session_state["last_draft"] = draft
                st.session_state["last_report"] = report
            except Exception as e:  # noqa: BLE001
                st.error(f"Draft failed: {e}")
                st.stop()

    if "last_draft" in st.session_state:
        draft = st.session_state["last_draft"]
        _render_draft(draft)
        st.download_button(
            "Download draft as JSON",
            data=json.dumps(draft.model_dump(mode="json"), indent=2, default=str),
            file_name="draft.json",
            mime="application/json",
        )


with tab_verify:
    st.header("Verification report")
    report = st.session_state.get("last_report")
    if not report:
        st.info("Generate a draft first.")
    else:
        if report.passed:
            st.success(report.summary)
        else:
            st.error(report.summary)
        st.write(f"Total claims checked: **{report.total_claims}**")
        st.write(f"Open [NEEDS INPUT] markers: **{report.needs_input_count}**")
        if report.flagged:
            st.subheader("Flagged claims")
            for f in report.flagged:
                st.markdown(
                    f"- **{f.kind}** — `{f.surface}`\n\n"
                    f"  Section: _{f.section_question[:80]}_\n\n"
                    f"  Reason: {f.reason}"
                )


with tab_funders:
    from funders.ingest import load_seed
    from funders.repo import list_funders
    from funders.seed import SEED_FUNDERS

    st.header("Funders")
    st.caption(
        "Curated seed list of capacity-building funders for rural NY youth-serving "
        "orgs. Re-load the seed list whenever you edit `funders/seed.py`. ProPublica "
        "enrichment runs from the CLI: `python -m funders.ingest enrich --all`."
    )

    col_a, col_b = st.columns([1, 3])
    with col_a:
        if st.button("(Re)load seed list", help="Upserts SEED_FUNDERS into Postgres"):
            try:
                n = load_seed()
                st.success(f"Loaded {n} seed funders.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Seed load failed: {e}")

    with col_b:
        st.metric("Seed list size", len(SEED_FUNDERS))

    try:
        funders = list_funders()
    except Exception as e:  # noqa: BLE001
        st.warning(f"DB not reachable — showing in-memory seed list. ({e})")
        funders = SEED_FUNDERS

    if not funders:
        st.info("No funders ingested yet. Click 'Reload seed list'.")
    else:
        prio_filter = st.text_input("Filter by priority tag (substring)", "")
        geo_filter = st.text_input("Filter by geography tag (substring)", "")
        for f in funders:
            if prio_filter and not any(prio_filter.lower() in p.lower() for p in f.priorities):
                continue
            if geo_filter and not any(geo_filter.lower() in g.lower() for g in f.geographies):
                continue
            with st.expander(f.headline()):
                st.markdown(f"**Classification:** {f.classification}")
                if f.ein:
                    st.markdown(f"**EIN:** {f.ein}")
                if f.geographies:
                    st.markdown("**Geographies:** " + ", ".join(f.geographies))
                if f.priorities:
                    st.markdown("**Priorities:** " + ", ".join(f.priorities))
                cap_bits = []
                if f.funds_capacity_building:
                    cap_bits.append("capacity building")
                if f.funds_executive_director:
                    cap_bits.append("ED salary")
                if f.funds_general_operating:
                    cap_bits.append("general operating")
                if f.funds_program:
                    cap_bits.append("program")
                if cap_bits:
                    st.markdown("**Funds:** " + ", ".join(cap_bits))
                if f.website:
                    st.markdown(f"**Website:** {f.website}")
                if f.application_url:
                    st.markdown(f"**Apply:** {f.application_url}")
                if f.notes:
                    st.markdown(f"**Notes:** {f.notes}")
                if f.sources:
                    st.markdown("**Sources:** " + ", ".join(f.sources))
