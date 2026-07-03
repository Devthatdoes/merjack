"""BizBuySell API source: JSON -> Listing normalization, limit, params, DealSource shape.

Uses an injected fake httpx client + a synthetic response fixture. No network. When the real
endpoint shape is captured, replace the fixture with a real sample and adjust the field map.
"""

from merjack.models import BuyBox
from merjack.sources.base import DealSource
from merjack.sources.bizbuysell_api import BizBuySellApiSource


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return _FakeResp(self.payload)

    def close(self):
        pass


# Synthetic response shaped like the DEFAULT_FIELD_MAP placeholders.
FIXTURE = {"results": [
    {"header": "Acme HVAC", "listingUrl": "https://bizbuysell.com/1", "price": 900000,
     "cashFlow": 350000, "state": "TX", "industry": "hvac", "established": 2008,
     "description": "Recurring maintenance contracts; absentee owner."},
    {"header": "Print Co", "listingUrl": "https://bizbuysell.com/2", "price": 600000,
     "cashFlow": 310000, "state": "NY", "industry": "printing"},
]}


def test_normalizes_json_to_listings():
    src = BizBuySellApiSource(client=_FakeClient(FIXTURE), cache=False)
    listings = src.fetch(BuyBox(state="TX", max_asking_price=2_000_000), limit=10)
    assert len(listings) == 2
    first = listings[0]
    assert first.title == "Acme HVAC"
    assert first.url == "https://bizbuysell.com/1"
    assert first.asking_price == 900_000
    assert first.cash_flow_sde == 350_000
    assert first.state == "TX" and first.industry == "hvac"
    assert first.year_established == 2008
    assert first.source == "bizbuysell"
    assert first.has_core_financials()


def test_respects_limit_and_builds_params():
    payload = {"results": [
        {"header": f"Co {i}", "listingUrl": f"https://b/{i}", "price": 900000, "cashFlow": 350000}
        for i in range(5)
    ]}
    client = _FakeClient(payload)
    src = BizBuySellApiSource(client=client, cache=False)
    out = src.fetch(BuyBox(state="TX", min_cash_flow=300_000), limit=3)
    assert len(out) == 3
    _url, params = client.calls[0]
    assert params["pageSize"] == 3
    assert params["state"] == "TX"
    assert params["cashFlowMin"] == 300_000


def test_is_a_dealsource():
    assert isinstance(BizBuySellApiSource(client=_FakeClient({"results": []})), DealSource)
