"""ProPublica Nonprofit Explorer client.

Public API, no auth required. Endpoints used here:

    GET /v2/search.json?q=<name>&state%5Bid%5D=NY
    GET /v2/organizations/{ein}.json

The raw payload is intentionally returned as a dict so callers can persist it
verbatim into Postgres JSONB. We extract only the fields we need for matching;
everything else stays in the raw blob for future use.

Rate limits: ProPublica asks for "reasonable" use. We cap at 5 req/sec via the
`min_interval_s` knob and retry on transient 5xx with exponential backoff.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from common.settings import settings


BASE_URL = "https://projects.propublica.org/nonprofits/api/v2"


class ProPublicaError(RuntimeError):
    """Raised on non-retryable ProPublica responses (404, 4xx)."""


@dataclass
class ProPublicaSearchHit:
    ein: str
    name: str
    state: Optional[str]
    ntee_code: Optional[str]
    classification: Optional[str]
    raw: dict


class ProPublicaClient:
    def __init__(
        self,
        *,
        min_interval_s: float = 0.2,
        timeout_s: float = 15.0,
        api_key: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._min_interval = min_interval_s
        self._last_call = 0.0
        # ProPublica's public endpoint doesn't require an API key, but if one
        # is configured we send it as a header — harmless and future-proofs us.
        headers = {"User-Agent": "yolc-grants/0.1 (capacity-building research)"}
        if api_key or settings.propublica_api_key:
            headers["Authorization"] = f"Bearer {api_key or settings.propublica_api_key}"
        self._client = client or httpx.Client(
            base_url=BASE_URL, timeout=timeout_s, headers=headers
        )

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        self._throttle()
        resp = self._client.get(path, params=params or {})
        if resp.status_code == 404:
            raise ProPublicaError(f"Not found: {path}")
        if 400 <= resp.status_code < 500:
            raise ProPublicaError(
                f"Client error {resp.status_code} for {path}: {resp.text[:200]}"
            )
        resp.raise_for_status()
        return resp.json()

    def search(
        self,
        query: str,
        *,
        state: Optional[str] = None,
        ntee_major: Optional[int] = None,
    ) -> list[ProPublicaSearchHit]:
        params: dict = {"q": query}
        if state:
            params["state[id]"] = state
        if ntee_major is not None:
            params["ntee[id]"] = ntee_major

        data = self._get("/search.json", params=params)
        out: list[ProPublicaSearchHit] = []
        for org in data.get("organizations", []):
            raw_ein = str(org.get("ein") or "")
            digits = "".join(c for c in raw_ein if c.isdigit())
            if len(digits) != 9:
                # Short or malformed EINs are placeholders; skip them.
                continue
            ein = digits
            out.append(
                ProPublicaSearchHit(
                    ein=f"{ein[:2]}-{ein[2:]}",
                    name=org.get("name") or "",
                    state=org.get("state"),
                    ntee_code=str(org.get("ntee_code") or "") or None,
                    classification=org.get("subseccd") or None,
                    raw=org,
                )
            )
        return out

    def organization(self, ein: str) -> dict:
        """Fetch full org payload by EIN. Returns the raw ProPublica dict."""
        digits = "".join(c for c in ein if c.isdigit())
        if len(digits) != 9:
            raise ValueError(f"EIN must have 9 digits: {ein!r}")
        return self._get(f"/organizations/{digits}.json")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ProPublicaClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# ---------- Helpers for translating ProPublica payloads into our schema ------


# IRS subsection codes (subseccd) -> our classification labels
_SUBSECTION_TO_CLASSIFICATION = {
    3: "public_charity",  # 501(c)(3) — refined below by foundation_code
    4: "other",
    6: "other",
}

# IRS foundation_code (Form 990 line) -> classification
_FOUNDATION_CODE_TO_CLASSIFICATION = {
    2: "public_charity",      # school
    3: "public_charity",      # hospital
    4: "operating_foundation",
    10: "public_charity",     # publicly-supported
    15: "community_foundation",
    16: "public_charity",     # supporting org
    17: "public_charity",
    21: "private_foundation",
    22: "private_foundation",
    23: "private_foundation",
    24: "operating_foundation",
}


def classification_from_propublica(raw: dict) -> str:
    """Best-effort mapping of ProPublica fields to FunderClassification."""
    org = raw.get("organization", raw)
    fc = org.get("foundation_code")
    if isinstance(fc, int) and fc in _FOUNDATION_CODE_TO_CLASSIFICATION:
        return _FOUNDATION_CODE_TO_CLASSIFICATION[fc]
    sub = org.get("subseccd")
    if isinstance(sub, int) and sub in _SUBSECTION_TO_CLASSIFICATION:
        return _SUBSECTION_TO_CLASSIFICATION[sub]
    return "other"


def grants_from_990pf_filings(raw: dict) -> list[dict]:
    """Extract grant-by-grant detail from ProPublica filings, where available.

    ProPublica's API exposes summary fields but not the Schedule I/Part XV
    grant detail — those live in the filing PDF. This function returns what
    *is* in the JSON: the per-year totals. Detailed grant parsing is
    deferred to a future sub-phase that reads the 990-PF PDFs directly.
    """
    out: list[dict] = []
    for filing in raw.get("filings_with_data", []) or []:
        out.append(
            {
                "fiscal_year": filing.get("tax_prd_yr"),
                "grants_paid_total_usd": filing.get("grntpdt") or filing.get("totcntrbgfts"),
                "form_type": filing.get("formtype_str"),
                "pdf_url": filing.get("pdf_url"),
            }
        )
    return out
