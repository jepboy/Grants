"""Unit tests for parsing + chunking. No DB, no API."""

from __future__ import annotations

from pathlib import Path

from kb.chunking import chunk_document
from kb.parsing import parse_document


def test_parse_text_file(tmp_path: Path):
    p = tmp_path / "notes.txt"
    p.write_text("Mission: serve rural youth.\nWe operate a drop-in center.")
    parsed = parse_document(p, document_type="program_data")
    assert parsed.filename == "notes.txt"
    assert parsed.document_type == "program_data"
    assert len(parsed.pages) == 1
    assert parsed.pages[0].page is None
    assert "drop-in center" in parsed.pages[0].text


def test_parse_markdown_file(tmp_path: Path):
    p = tmp_path / "about.md"
    p.write_text("# Youth of Lewis County\n\nA youth-led 501(c)(3).")
    parsed = parse_document(p)
    assert any("Youth of Lewis County" in pg.text for pg in parsed.pages)


def test_chunking_word_window(tmp_path: Path):
    big = " ".join([f"word{i}" for i in range(1000)])
    p = tmp_path / "big.txt"
    p.write_text(big)
    parsed = parse_document(p)
    chunks = chunk_document(parsed, target_words=100, overlap_words=20)
    # 1000 words / step=80 ≈ 13 chunks
    assert 10 <= len(chunks) <= 15
    # Each chunk has stable id
    ids = {c.chunk_id for c in chunks}
    assert len(ids) == len(chunks)


def test_chunk_preserves_source_metadata(tmp_path: Path):
    p = tmp_path / "src.txt"
    p.write_text("alpha beta gamma delta epsilon zeta")
    parsed = parse_document(p, document_type="bylaws")
    chunks = chunk_document(parsed, target_words=3, overlap_words=1)
    assert chunks
    for c in chunks:
        assert "src.txt" in c.chunk_id
