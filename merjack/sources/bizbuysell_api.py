"""BizBuySell API source (M5).

Calls BizBuySell's reverse-engineered search/listing API (discovered with libretto; see
``sourcing/README.md``) and normalizes the JSON into ``merjack.models.Listing``. Pure-Python
httpx at runtime: no browser, no LLM in the hot path.

STATUS: scaffold. The endpoint path, query params, results key, and field names below are
**placeholders to fill from the libretto recon capture**. The normalization, caching, and
``DealSource`` wiring are built and tested against a fixture (``tests/test_bizbuysell_api.py``).
Once the real shape is known, edit ``DEFAULT_*`` (or pass overrides to the constructor) and
add a fixture test from a captured response.
"""

from __future__ import annotations

from typing import Callable, Optional

import httpx

from .. import storage
from ..models import BuyBox, Listing
from .manual_source import row_to_listing

DEFAULT_BASE_URL = "https://www.bizbuysell.com"
DEFAULT_SEARCH_PATH = "/api/search"   # TODO(recon): real search endpoint path
DEFAULT_RESULTS_KEY = "results"        # TODO(recon): JSON key holding the listings array

# Our canonical Listing field -> the JSON key in the captured response.
# Edit to the real field names after the recon.
DEFAULT_FIELD_MAP = {
    "title": "header",
    "url": "listingUrl",
    "asking_price": "price",
    "cash_flow_sde": "cashFlow",
    "revenue": "grossRevenue",
    "ebitda": "ebitda",
    "location": "city",
    "state": "state",
    "industry": "industry",
    "description": "description",
    "year_established": "established",
}

# Polite defaults; the recon reveals which headers/cookies are actually required.
DEFAULT_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}


def default_params(buybox: BuyBox, limit: int) -> dict:
    """Placeholder query-param builder; replace with the captured params."""
    params: dict = {"pageSize": limit}
    if buybox.state:
        params["state"] = buybox.state
    if buybox.max_asking_price:
        params["priceMax"] = int(buybox.max_asking_price)
    if buybox.min_cash_flow:
        params["cashFlowMin"] = int(buybox.min_cash_flow)
    return params


class BizBuySellApiSource:
    """A ``DealSource`` backed by BizBuySell's listing API. Inject a configured client
    for tests; in production it builds its own httpx client."""

    name = "bizbuysell"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        search_path: str = DEFAULT_SEARCH_PATH,
        results_key: str = DEFAULT_RESULTS_KEY,
        field_map: Optional[dict] = None,
        headers: Optional[dict] = None,
        params_builder: Callable[[BuyBox, int], dict] = default_params,
        client: Optional[httpx.Client] = None,
        cache: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.search_path = search_path
        self.results_key = results_key
        self.field_map = field_map or DEFAULT_FIELD_MAP
        self.headers = headers or DEFAULT_HEADERS
        self.params_builder = params_builder
        self._client = client
        self.cache = cache

    def _get(self, params: dict) -> dict:
        client = self._client or httpx.Client(timeout=15.0, headers=self.headers)
        try:
            resp = client.get(f"{self.base_url}{self.search_path}", params=params)
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._client is None:
                client.close()

    def _normalize(self, raw: dict, index: int) -> Listing:
        row = {ours: raw.get(json_key) for ours, json_key in self.field_map.items()}
        listing = row_to_listing(row, index)   # reuses money parsing + Listing construction
        listing.source = "bizbuysell"
        return listing

    def fetch(self, buybox: BuyBox, limit: int = 25) -> list[Listing]:
        data = self._get(self.params_builder(buybox, limit))
        raw = data.get(self.results_key, []) if isinstance(data, dict) else (data or [])
        listings = [self._normalize(r, i) for i, r in enumerate(raw[:limit])]
        if self.cache:
            for listing in listings:
                storage.upsert_listing(listing)
        return listings
        # NOTE: pagination + defensive pacing (time.sleep between pages) get added once the
        # recon reveals whether results are paged and what the page param is.
