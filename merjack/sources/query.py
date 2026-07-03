"""Translate a ``BuyBox`` into a BizBuySell search URL.

The live browser agent (M5) will navigate from this URL; the manual source ignores
it. BizBuySell encodes the location as a path slug (``/new-york-businesses-for-sale/``)
and filters as query params. Exact param names get validated against the live site
when the browser agent runs — treat this as a best-effort starting URL.
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..models import BuyBox

BASE_URL = "https://www.bizbuysell.com"

# 2-letter code -> BizBuySell location slug.
STATE_SLUGS = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california",
    "CO": "colorado", "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia",
    "HI": "hawaii", "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa",
    "KS": "kansas", "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi", "MO": "missouri",
    "MT": "montana", "NE": "nebraska", "NV": "nevada", "NH": "new-hampshire", "NJ": "new-jersey",
    "NM": "new-mexico", "NY": "new-york", "NC": "north-carolina", "ND": "north-dakota", "OH": "ohio",
    "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania", "RI": "rhode-island", "SC": "south-carolina",
    "SD": "south-dakota", "TN": "tennessee", "TX": "texas", "UT": "utah", "VT": "vermont",
    "VA": "virginia", "WA": "washington", "WV": "west-virginia", "WI": "wisconsin", "WY": "wyoming",
    "DC": "washington-dc",
}


def state_slug(state: str) -> str:
    return STATE_SLUGS.get(state.strip().upper(), state.strip().lower().replace(" ", "-"))


def build_search_url(buybox: BuyBox) -> str:
    """Best-effort BizBuySell search URL for the buy-box."""
    if buybox.state:
        path = f"/{state_slug(buybox.state)}-businesses-for-sale/"
    else:
        path = "/businesses-for-sale/"

    params: dict[str, str] = {}
    if buybox.max_asking_price is not None:
        params["priceMax"] = str(int(buybox.max_asking_price))
    if buybox.min_cash_flow is not None:
        params["cashFlowMin"] = str(int(buybox.min_cash_flow))
    if buybox.industries:
        params["q"] = " ".join(buybox.industries)

    query = urlencode(params)
    return f"{BASE_URL}{path}" + (f"?{query}" if query else "")
