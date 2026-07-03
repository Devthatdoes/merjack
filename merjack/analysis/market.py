"""Geo/market qualifier for the resale valuation (docs/DESIGN.md §8).

Searches (SearXNG) for current demand and sale-multiple signal in the listing's
industry and metro, then has the model synthesize a bounded ``MarketAssessment``
(geo + market factors, rationale, sources). Cached by (industry, metro, month).
Any failure returns a neutral assessment, so the deterministic valuation still works.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from typing import Optional

from .. import storage
from ..models import Listing, MarketAssessment
from .explain import _text_of

_SYSTEM = (
    "You assess how good a small-business industry is in a specific location, for resale value, "
    "using the search snippets provided. geo_market_factor: -1 means weak or declining demand or "
    "oversaturation in that location, +1 means strong local demand (snow removal in Minnesota is high, "
    "in California is low). market_env_factor: -1 means a poor current climate for buying and selling "
    "small businesses (high rates, few buyers), +1 means a strong climate. Be conservative when the "
    "evidence is thin. Do not invent specifics. Respond with ONLY a JSON object."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _clampf(x, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.0


def _parse(text: str) -> dict:
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError("no JSON object in model output")
    return json.loads(match.group(0))


def _cache_key(industry: str, metro: str) -> str:
    return f"{industry.lower()}|{metro.lower()}|{_dt.date.today():%Y-%m}"


def assess_market(
    listing: Listing,
    search=None,
    model=None,
    use_cache: bool = True,
) -> MarketAssessment:
    """Return a bounded market assessment for ``listing``'s industry x location.
    Neutral (all zeros) when industry/location is unknown or any step fails."""
    industry = (listing.industry or "").strip()
    metro = (listing.location or listing.state or "").strip()
    if not industry or not metro:
        return MarketAssessment()

    key = _cache_key(industry, metro)
    if use_cache:
        cached = storage.get_market(key)
        if cached is not None:
            return cached

    try:
        if search is None:
            from ..search import SearxngSearch

            search = SearxngSearch()
        results = []
        for query in (f"{industry} business demand {metro}", f"{industry} business for sale SDE multiple"):
            results += search.search(query, limit=4)

        snippets = "\n".join(f"- {r.title}: {r.snippet}" for r in results if r.title)
        sources: list[str] = []
        for r in results:
            if r.url and r.url not in sources:
                sources.append(r.url)

        if model is None:
            from ..llm import get_model

            model = get_model("explain")

        human = (
            f"Industry: {industry}\nLocation: {metro}\n\nSearch results:\n{snippets or '(none)'}\n\n"
            'Return ONLY JSON: {"geo_market_factor": <-1..1>, "market_env_factor": <-1..1>, '
            '"rationale": "<2-3 sentences>", "confidence": <0..1>}'
        )
        data = _parse(_text_of(model.invoke([("system", _SYSTEM), ("human", human)])))
        assessment = MarketAssessment(
            geo_market_factor=_clampf(data.get("geo_market_factor", 0), -1.0, 1.0),
            market_env_factor=_clampf(data.get("market_env_factor", 0), -1.0, 1.0),
            rationale=str(data.get("rationale", ""))[:600],
            sources=sources[:5],
            confidence=_clampf(data.get("confidence", 0.5), 0.0, 1.0),
        )
        if use_cache:
            storage.save_market(key, assessment)
        return assessment
    except Exception:  # noqa: BLE001 — never let the market read break scoring
        return MarketAssessment()
