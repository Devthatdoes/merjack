"""SearXNG client: parses results, applies limit, builds the right request. No network."""

from merjack.search import SearchProvider, SearxngSearch


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_searxng_parses_and_limits(monkeypatch):
    payload = {"results": [
        {"title": "HVAC demand up", "url": "http://a", "content": "strong demand"},
        {"title": "Multiples", "url": "http://b", "content": "2.5-3.5x SDE"},
        {"title": "Third", "url": "http://c", "content": "extra"},
    ]}
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"], captured["params"] = url, params
        return _FakeResp(payload)

    monkeypatch.setattr("merjack.search.searxng.httpx.get", fake_get)
    s = SearxngSearch(base_url="http://sx:8080")
    out = s.search("hvac demand", limit=2)

    assert isinstance(s, SearchProvider)
    assert len(out) == 2                       # limit applied
    assert out[0].title == "HVAC demand up" and out[0].url == "http://a"
    assert captured["url"] == "http://sx:8080/search"
    assert captured["params"] == {"q": "hvac demand", "format": "json"}


def test_searxng_tolerates_missing_fields(monkeypatch):
    monkeypatch.setattr("merjack.search.searxng.httpx.get", lambda *a, **k: _FakeResp({"results": [{}]}))
    out = SearxngSearch().search("q")
    assert out[0].title == "" and out[0].url == "" and out[0].snippet == ""
