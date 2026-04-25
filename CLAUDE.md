# CLAUDE.md — Youth of Lewis County Grant System

This repository is a **single-organization** grant discovery, analysis, and
drafting system for **Youth of Lewis County**, a youth-led 501(c)(3) nonprofit
in Lewis County, NY. It is **not** a multi-tenant SaaS. Optimize for depth over
breadth. The single most important capacity-building target is funding a
full-time paid Executive Director position.

---

## Non-negotiable: Truthful Grounding

**The system must NEVER fabricate facts about the organization.**

Every factual claim in any generated draft must be traceable to a source
document in the knowledge base. Unsupported claims must be flagged as
`[NEEDS INPUT: <description>]`, never filled in with plausible-sounding
fabrications.

Grant fraud has serious legal consequences (civil penalties, debarment,
criminal exposure under 18 U.S.C. §§ 1001, 1341, 1343 for misrepresentation
in federal grant applications). This constraint is a first-class
architectural concern, not an afterthought.

### Rules

1. **No silent fact generation.** If the model would make a claim not present
   in the KB, it must instead emit `[NEEDS INPUT: <what's needed>]`.
2. **Every numeric claim is verified.** The verification pass extracts every
   number, date, name, partnership, and outcome from a draft and confirms
   each against retrieved source chunks. Unverified items are stripped or
   flagged.
3. **Source citations are mandatory.** Drafts include inline citation markers.
   We use Anthropic's native citations API
   (https://docs.claude.com/en/docs/build-with-claude/citations).
4. **Distinguish projection vs fact.** Forward-looking claims (projected youth
   served, projected revenue) are clearly labeled as projections. Past or
   current claims are labeled as facts and require sources.
5. **AI disclosure flag.** Every draft carries a metadata flag indicating AI
   assistance — some funders require disclosure.
6. **Truthfulness tests.** `tests/test_truthfulness.py` feeds synthetic
   "tempting" inputs (RFPs asking for outcome numbers when the KB has none)
   and asserts the system outputs `[NEEDS INPUT]` rather than fabricating.

---

## Architecture (5 Layers)

Build in order. Do not start a layer until the previous one works.

### Layer 1 — Organization Knowledge Base  (`kb/`)
Document ingestion (PDF, DOCX, TXT, MD), chunking with metadata, embeddings
(voyage-3 or text-embedding-3-large), Postgres + pgvector storage, structured
fact extraction, retrieval that always returns source citations.

### Layer 2 — Funder Intelligence  (`funders/`)
ProPublica 990-PF ingestion, funder profile schema, curated seed list for
rural NY youth-serving capacity grants.

### Layer 3 — Matching Engine  (`matching/`)
Hard filters (geography, budget eligibility, program area, funding range),
semantic similarity, LLM re-ranker, ranked output with reasoning.

### Layer 4 — Grounded Drafter  (`drafter/`)
Per-section RAG, Anthropic Messages API with native citations, funder-specific
tailoring, output = draft with inline citations + `[NEEDS INPUT]` list.

### Layer 5 — Verification Pass  (`verifier/`)
Separate LLM call as fact-checker. Extracts every numeric claim, date, name,
partnership, outcome. Verifies each against source chunks. **Anti-fraud layer
— do not skip.**

---

## Tech Stack

- **Python 3.11+**
- **FastAPI** for backend
- **Streamlit** for the initial UI (Phase 1); Next.js later if needed
- **Postgres + pgvector** for KB and funder data (simpler than a dedicated
  vector DB for single-org use)
- **Anthropic Python SDK** for LLM calls
  - `claude-opus-4-7` for drafting and verification
  - `claude-sonnet-4-6` for cheaper sub-tasks (chunk-level claim extraction,
    summarization)
- **Voyage AI** (`voyage-3`) for embeddings; OpenAI `text-embedding-3-large`
  is a drop-in fallback
- **pypdf** + **python-docx** for document parsing (light, no extra services).
  Unstructured.io / LlamaIndex are optional upgrades.

---

## Module Layout

```
kb/         # Layer 1: ingestion, chunking, embedding, retrieval
funders/    # Layer 2: 990-PF ingestion, funder profiles
matching/   # Layer 3: filtering + re-ranking
drafter/    # Layer 4: grounded section drafter (citations API)
verifier/   # Layer 5: claim extraction + cross-check
api/        # FastAPI app
ui/         # Streamlit app
tests/      # Module tests + truthfulness tests
uploads/    # User-uploaded org documents (gitignored)
```

Each module has its own tests under `tests/`.

---

## Citation Format

Internal representation:
```python
Citation(
    source_filename: str,
    document_type: str,        # e.g. "501c3_letter", "ocfs_agreement"
    chunk_id: str,
    page: int | None,
    text_snippet: str,         # the supporting text
    verified: bool,            # human-confirmed source
)
```

When using Anthropic's citations API, the SDK returns `cited_text`,
`document_index`, `document_title`, and `start_char_index`/`end_char_index`.
We map those to our `Citation` schema and persist them with the draft.

Inline rendering in drafts uses `[^cN]` markers, where `cN` is the citation
index. The end of each draft includes a `Sources` section listing all
citations with file + page + snippet.

---

## MVP Phases

**Phase 1 (current):** KB ingestion + retrieval; single-RFP grounded drafter
with citations and `[NEEDS INPUT]` flags; verification pass on every draft;
truthfulness tests.

**Phase 2:** Funder profile ingestion (990-PF) + curated funder list.

**Phase 3:** Matching engine + pipeline view with deadlines.

**Stop after Phase 1 ships end-to-end. Confirm with Wyatt before Phase 2.**

---

## Environment Variables

See `.env.example`. Required for Phase 1:
- `ANTHROPIC_API_KEY`
- `VOYAGE_API_KEY` (or `OPENAI_API_KEY` if using fallback)
- `DATABASE_URL` (Postgres with pgvector extension installed)

Required for Phase 2:
- `PROPUBLICA_API_KEY` (optional — endpoint is public but rate-limited)
