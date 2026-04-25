"""ProPublica client tests with a mocked HTTP transport. No live network."""

from __future__ import annotations

import json

import httpx
import pytest

from funders.propublica import (
    BASE_URL,
    ProPublicaClient,
    ProPublicaError,
    classification_from_propublica,
    grants_from_990pf_filings,
)


def _client_with_handler(handler) -> ProPublicaClient:
    transport = httpx.MockTransport(handler)
    inner = httpx.Client(base_url=BASE_URL, transport=transport, timeout=5.0)
    return ProPublicaClient(client=inner, min_interval_s=0)


def test_search_normalizes_eins_and_returns_hits():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/nonprofits/api/v2/search.json"
        assert request.url.params.get("q") == "youth"
        return httpx.Response(
            200,
            json={
                "organizations": [
                    {"ein": 137434243, "name": "Acme Foundation", "state": "NY", "ntee_code": "T31", "subseccd": 3},
                    {"ein": 1234, "name": "Truncated", "state": "NY"},  # invalid — should be filtered
                ]
            },
        )

    with _client_with_handler(handler) as client:
        hits = client.search("youth")
    assert len(hits) == 1
    assert hits[0].ein == "13-7434243"
    assert hits[0].name == "Acme Foundation"


def test_search_passes_state_filter():
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json={"organizations": []})

    with _client_with_handler(handler) as client:
        client.search("youth", state="NY")
    assert seen_params.get("state[id]") == "NY"


def test_organization_404_raises_propublica_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "Not Found"})

    with _client_with_handler(handler) as client:
        with pytest.raises(ProPublicaError):
            client.organization("12-3456789")


def test_organization_returns_raw_payload():
    payload = {
        "organization": {
            "ein": 123456789,
            "name": "Test Foundation",
            "subseccd": 3,
            "foundation_code": 21,
        },
        "filings_with_data": [
            {"tax_prd_yr": 2023, "grntpdt": 250000, "formtype_str": "990PF"}
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/nonprofits/api/v2/organizations/123456789.json"
        return httpx.Response(200, json=payload)

    with _client_with_handler(handler) as client:
        raw = client.organization("12-3456789")
    assert raw == payload


def test_classification_from_propublica_uses_foundation_code():
    raw = {"organization": {"foundation_code": 21}}
    assert classification_from_propublica(raw) == "private_foundation"
    raw = {"organization": {"foundation_code": 15}}
    assert classification_from_propublica(raw) == "community_foundation"
    raw = {"organization": {"foundation_code": 4}}
    assert classification_from_propublica(raw) == "operating_foundation"


def test_classification_falls_back_to_subseccd_then_other():
    raw = {"organization": {"subseccd": 3}}
    assert classification_from_propublica(raw) == "public_charity"
    raw = {"organization": {}}
    assert classification_from_propublica(raw) == "other"


def test_grants_from_990pf_filings_extracts_summary():
    raw = {
        "filings_with_data": [
            {"tax_prd_yr": 2023, "grntpdt": 100_000, "formtype_str": "990PF", "pdf_url": "u"},
            {"tax_prd_yr": 2022, "totcntrbgfts": 80_000, "formtype_str": "990"},
        ]
    }
    out = grants_from_990pf_filings(raw)
    assert len(out) == 2
    assert out[0]["fiscal_year"] == 2023
    assert out[0]["grants_paid_total_usd"] == 100_000


def test_organization_invalid_ein_raises():
    def handler(_):
        return httpx.Response(200, json={})

    with _client_with_handler(handler) as client:
        with pytest.raises(ValueError):
            client.organization("not-numeric")
