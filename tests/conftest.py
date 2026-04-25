"""Test config: fake Anthropic client + KB chunks for unit tests.

Most tests should run without any network or DB. Tests that require a live
Anthropic API or pgvector instance are marked with `@pytest.mark.live` or
`@pytest.mark.db` and skipped by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from common.citations import Chunk


@dataclass
class FakeContentBlock:
    type: str
    text: str = ""
    citations: list[Any] = field(default_factory=list)


@dataclass
class FakeCitation:
    document_index: int
    cited_text: str
    start_char_index: int = 0
    end_char_index: int = 0
    document_title: str = ""
    type: str = "char_location"


@dataclass
class FakeMessage:
    content: list[FakeContentBlock]


class FakeAnthropic:
    """Minimal stand-in for `anthropic.Anthropic`.

    Constructed with a queue of FakeMessage objects to return on successive
    `messages.create` calls. Tests use this to drive the drafter and verifier
    without hitting the real API.
    """

    def __init__(self, responses: list[FakeMessage]):
        self._responses = list(responses)
        self.calls: list[dict] = []

        class _Messages:
            def __init__(inner_self, parent):
                inner_self.parent = parent

            def create(inner_self, **kwargs):
                inner_self.parent.calls.append(kwargs)
                if not inner_self.parent._responses:
                    raise RuntimeError("FakeAnthropic ran out of queued responses")
                return inner_self.parent._responses.pop(0)

        self.messages = _Messages(self)


@pytest.fixture
def org_chunks() -> list[Chunk]:
    """A small synthetic KB: a few real-shaped facts, no outcome numbers."""
    return [
        Chunk(
            chunk_id="c1",
            source_filename="501c3_letter.pdf",
            document_type="501c3_letter",
            page=1,
            text=(
                "Internal Revenue Service determination letter dated June 2022 recognizing "
                "Youth of Lewis County as a tax-exempt organization under IRC section 501(c)(3). "
                "EIN: 88-1234567."
            ),
            verified=True,
        ),
        Chunk(
            chunk_id="c2",
            source_filename="ocfs_agreement.pdf",
            document_type="ocfs_agreement",
            page=2,
            text=(
                "The New York State Office of Children and Family Services has entered into "
                "a service agreement with Youth of Lewis County to provide mentor services to "
                "youth in Lewis County."
            ),
            verified=True,
        ),
        Chunk(
            chunk_id="c3",
            source_filename="programs.md",
            document_type="program_data",
            page=None,
            text=(
                "Programs operated by Youth of Lewis County include a drop-in center, an annual "
                "theater camp, the Renaissance Faire, and the Talent Show. The organization is "
                "based in Lewis County, NY."
            ),
            verified=True,
        ),
    ]
