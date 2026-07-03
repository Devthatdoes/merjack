"""Resale (exit) multiple estimation — see docs/DESIGN.md §8.

Replaces the hard-coded 4.0/4.5x flip multiples with a derived range:

    multiple = size_base(SDE) × (1 + Σ weightᵢ·factorᵢ)   →  clamp  →  low–high

Factors come from the qualitative sub-scores (owner-independence, recurring revenue,
stability) and — on the paid tier — an injected ``MarketAssessment`` (geo/market fit,
the snow-plow-in-MN signal). Pure and deterministic: the LLM/SearXNG qualifier is just
one optional input. When qualitative is absent, factors are neutral and the range widens.
"""

from __future__ import annotations

from typing import Optional

from .config import (
    PROJECTED_INDEPENDENCE,
    PROJECTED_SDE_GROWTH,
    RESALE_CAP,
    RESALE_FACTOR_WEIGHTS,
    RESALE_FLOOR,
    RESALE_GEO_WEIGHT,
    RESALE_MARKET_WEIGHT,
    RESALE_SPREAD,
    SIZE_BANDS,
)
from .models import FlipScenario, Listing, MarketAssessment, QualScore, ResaleEstimate


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def size_base(sde: float) -> float:
    """Interpolate the size-anchored base multiple from ``SIZE_BANDS`` (bigger SDE → higher)."""
    bands = SIZE_BANDS
    if sde <= bands[0][0]:
        return bands[0][1]
    if sde >= bands[-1][0]:
        return bands[-1][1]
    for (lo_s, lo_m), (hi_s, hi_m) in zip(bands, bands[1:]):
        if lo_s <= sde <= hi_s:
            frac = (sde - lo_s) / (hi_s - lo_s)
            return lo_m + frac * (hi_m - lo_m)
    return bands[-1][1]  # pragma: no cover


def _norm(score: Optional[float]) -> float:
    """Map a 0–100 sub-score to a factor in [-1, 1]; missing -> neutral 0."""
    if score is None:
        return 0.0
    return (_clamp(score, 0, 100) - 50) / 50.0


def _resale_estimate(
    sde: float,
    owner_independence: Optional[float],
    recurring_revenue: Optional[float],
    stability: Optional[float],
    market: Optional[MarketAssessment],
    spread_extra: float,
) -> ResaleEstimate:
    base = size_base(sde)
    breakdown = [f"base {base:.1f}x"]
    total = 0.0

    for label, weight, score in (
        ("owner-independence", RESALE_FACTOR_WEIGHTS["owner_independence"], owner_independence),
        ("recurring rev", RESALE_FACTOR_WEIGHTS["recurring_revenue"], recurring_revenue),
        ("stability", RESALE_FACTOR_WEIGHTS["stability"], stability),
    ):
        c = weight * _norm(score)
        total += c
        if abs(c) >= 0.005:
            breakdown.append(f"{'+' if c >= 0 else ''}{c * 100:.0f}% {label}")

    if market is not None:
        for label, weight, factor in (
            ("geo/industry fit", RESALE_GEO_WEIGHT, market.geo_market_factor),
            ("market climate", RESALE_MARKET_WEIGHT, market.market_env_factor),
        ):
            c = weight * factor
            total += c
            if abs(c) >= 0.005:
                breakdown.append(f"{'+' if c >= 0 else ''}{c * 100:.0f}% {label}")

    point = _clamp(base * (1 + total), RESALE_FLOOR, RESALE_CAP)
    spread = RESALE_SPREAD + spread_extra
    low = _clamp(point * (1 - spread), RESALE_FLOOR, RESALE_CAP)
    high = _clamp(point * (1 + spread), RESALE_FLOOR, RESALE_CAP)
    return ResaleEstimate(point=round(point, 2), low=round(low, 2), high=round(high, 2), breakdown=breakdown)


def _scenario(name: str, sde: float, estimate: ResaleEstimate, asking: float) -> FlipScenario:
    sale = estimate.point * sde
    return FlipScenario(
        name=name,
        target_multiple=estimate.point,
        projected_sale_price=sale,
        projected_profit=sale - asking,
        multiple_low=estimate.low,
        multiple_high=estimate.high,
        breakdown=estimate.breakdown,
    )


def flip_scenarios(
    listing: Listing,
    qual: Optional[QualScore] = None,
    market: Optional[MarketAssessment] = None,
) -> list[FlipScenario]:
    """Two derived scenarios: **quick** (resell as-is) and **scale** (after adding a
    management layer + growing SDE). Both carry a resale-multiple range + factor breakdown."""
    sde = listing.cash_flow_sde
    asking = listing.asking_price
    if not sde or not asking:
        return []

    owner = qual.owner_independence if qual else None
    recurring = qual.recurring_revenue if qual else None
    stability = qual.stability if qual else None

    # Lower confidence -> wider range: no qualitative pass, or a partial listing.
    spread_extra = (0.06 if qual is None else 0.0) + (0.03 if listing.partial else 0.0)

    quick = _resale_estimate(sde, owner, recurring, stability, market, spread_extra)

    # Scale: a management layer lifts owner-independence; scaling grows SDE.
    proj_sde = sde * (1 + PROJECTED_SDE_GROWTH)
    proj_owner = max(owner if owner is not None else 50, PROJECTED_INDEPENDENCE)
    scale = _resale_estimate(proj_sde, proj_owner, recurring, stability, market, spread_extra)

    return [
        _scenario("quick_flip", sde, quick, asking),
        _scenario("scale_flip", proj_sde, scale, asking),
    ]
