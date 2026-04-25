# Youth of Lewis County — Grant System

Grant discovery, analysis, and **grounded** drafting for Youth of Lewis County,
a youth-led 501(c)(3) in Lewis County, NY. Focus: capacity-building grants,
primarily a full-time paid Executive Director.

The system **never fabricates** facts about the organization. Every claim in
every draft is traceable to a source document or flagged `[NEEDS INPUT]`.
See [CLAUDE.md](./CLAUDE.md) for the architectural rules.

## Phase 1 Quickstart

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start Postgres + pgvector (Docker)
docker run -d --name grants-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=grants \
  pgvector/pgvector:pg16

# 3. Configure
cp .env.example .env  # then fill in keys

# 4. Initialize schema
python -m kb.schema init

# 5. Run the UI
streamlit run ui/app.py
```

## Layout

| Module     | Purpose                                                            |
|------------|--------------------------------------------------------------------|
| `kb/`      | Org knowledge base — ingest, chunk, embed, retrieve with citations |
| `funders/` | Funder intelligence (Phase 2)                                      |
| `matching/`| Org ↔ funder matching (Phase 3)                                   |
| `drafter/` | Per-section RAG drafter with Anthropic native citations            |
| `verifier/`| Anti-fraud claim verification pass                                 |
| `api/`     | FastAPI backend (optional alongside Streamlit)                     |
| `ui/`      | Streamlit app                                                      |
| `tests/`   | Module + truthfulness tests                                        |

## Running Tests

```bash
pytest                       # unit + truthfulness (no API/DB calls)
pytest -m live               # exercises live LLM endpoints (costs $$)
pytest -m db                 # requires Postgres+pgvector running
```
