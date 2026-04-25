"""Sanity tests for the shared Citation/Chunk schema."""

from common.citations import Chunk, Citation, Draft, DraftSection


def test_citation_from_chunk_uses_full_text_when_no_snippet():
    ch = Chunk(
        chunk_id="x",
        source_filename="bylaws.pdf",
        document_type="bylaws",
        page=3,
        text="Article III. The board shall meet quarterly.",
    )
    c = Citation.from_chunk(ch)
    assert c.text_snippet == ch.text
    assert c.page == 3


def test_draft_ai_assisted_default_true():
    d = Draft(
        sections=[DraftSection(question="Q?", body="A.")],
        model="claude-opus-4-7",
    )
    assert d.ai_assisted is True


def test_all_needs_input_aggregates_across_sections():
    d = Draft(
        sections=[
            DraftSection(question="A", body="x", needs_input=["[NEEDS INPUT: a]"]),
            DraftSection(question="B", body="y", needs_input=["[NEEDS INPUT: b]"]),
        ],
        model="claude-opus-4-7",
    )
    flags = d.all_needs_input()
    assert len(flags) == 2
