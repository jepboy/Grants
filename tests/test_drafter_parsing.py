"""RFP-splitting and JSON-extraction unit tests."""

from drafter.draft import _extract_json, parse_rfp_sections


def test_parse_numbered_rfp():
    rfp = (
        "Please answer the following:\n"
        "1. Describe your mission.\n"
        "2. Describe your programs.\n"
        "3. What is your annual budget?"
    )
    qs = parse_rfp_sections(rfp)
    assert len(qs) == 3
    assert qs[0].startswith("Describe your mission")


def test_parse_bullet_rfp():
    rfp = "- Mission?\n- Programs?\n- Budget?"
    qs = parse_rfp_sections(rfp)
    assert len(qs) == 3


def test_parse_unsplittable_rfp_returns_whole():
    rfp = "Tell us about your organization in one paragraph."
    qs = parse_rfp_sections(rfp)
    assert qs == [rfp]


def test_extract_json_handles_fenced_block():
    raw = '```json\n{"body": "hi", "needs_input": []}\n```'
    parsed = _extract_json(raw)
    assert parsed == {"body": "hi", "needs_input": []}


def test_extract_json_handles_extra_prose():
    raw = 'Sure! Here is the result: {"body": "hi", "needs_input": []} thanks'
    parsed = _extract_json(raw)
    assert parsed["body"] == "hi"
