"""Geo/market qualifier: clamping, sources, neutral fallback, caching. No network."""

import types

from merjack.analysis.market import assess_market
from merjack.models import Listing
from merjack.search.base import SearchResult


class _FakeSearch:
    def __init__(self, results):
        self.results = results
        self.queries = []

    def search(self, query, limit=5):
        self.queries.append(query)
        return self.results[:limit]


class _FakeModel:
    def __init__(self, text):
        self.text = text

    def invoke(self, messages):
        return types.SimpleNamespace(content=self.text)


def _listing(industry="snow removal", state="MN", location=None):
    return Listing(url="m/1", title="Co", industry=industry, state=state, location=location,
                   asking_price=900_000, cash_flow_sde=300_000)


def test_builds_clamped_assessment_with_sources():
    search = _FakeSearch([
        SearchResult("MN snow demand high", "http://a", "50+ inches/yr"),
        SearchResult("multiples", "http://b", "2.5-3.5x SDE"),
    ])
    model = _FakeModel('{"geo_market_factor": 1.5, "market_env_factor": -0.3, '
                       '"rationale": "Strong Minnesota demand.", "confidence": 0.8}')
    ma = assess_market(_listing(), search=search, model=model, use_cache=False)

    assert ma.geo_market_factor == 1.0          # clamped down from 1.5
    assert ma.market_env_factor == -0.3
    assert ma.sources[0] == "http://a"
    assert ma.rationale.startswith("Strong")
    assert len(search.queries) == 2             # demand + multiple queries


def test_neutral_when_industry_or_location_missing():
    ma = assess_market(Listing(url="m/2", title="X"), use_cache=False)
    assert ma.geo_market_factor == 0.0 and ma.market_env_factor == 0.0 and ma.sources == []


def test_falls_back_to_neutral_on_search_error():
    class _Boom:
        def search(self, query, limit=5):
            raise RuntimeError("searxng down")

    ma = assess_market(_listing(), search=_Boom(), model=_FakeModel("{}"), use_cache=False)
    assert ma.geo_market_factor == 0.0 and ma.market_env_factor == 0.0


def test_uses_cache_on_second_call(monkeypatch):
    cache = {}
    monkeypatch.setattr("merjack.analysis.market.storage.get_market", lambda key, **k: cache.get(key))
    monkeypatch.setattr("merjack.analysis.market.storage.save_market",
                        lambda key, ma, **k: cache.__setitem__(key, ma))
    search = _FakeSearch([SearchResult("t", "http://a", "s")])
    model = _FakeModel('{"geo_market_factor":0.5,"market_env_factor":0.0,"rationale":"x","confidence":0.7}')

    a1 = assess_market(_listing(), search=search, model=model)
    assert len(search.queries) == 2 and a1.geo_market_factor == 0.5
    a2 = assess_market(_listing(), search=search, model=model)
    assert len(search.queries) == 2   # cache hit -> no new searches
    assert a2.geo_market_factor == 0.5
