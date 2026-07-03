"""Composite deal scoring + ranking — all deterministic (no LLM here).

Combines three signals into a 0–100 composite:

  * finance      — net cash flow after debt + how attractive the multiple is
  * qualitative  — the LLM's rubric sub-scores (optional; weight redistributes if absent)
  * buybox_fit   — how well the listing matches the user's stated filters

Also surfaces red flags an SBA-minded buyer should see (high multiple, negative
cash flow, thin debt coverage, missing/partial data, very young business).
"""

from __future__ import annotations

import datetime as _dt

from ..config import SCORE_WEIGHTS
from ..models import BuyBox, DealScore, FinanceResult, Listing, OwnerInvolvement, QualScore
from .finance import build_finance_result, compute_multiple

# SBA lenders typically want debt-service coverage of at least this.
MIN_DSCR = 1.25


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def finance_score(finance: FinanceResult) -> float:
    """0–100 from net cash flow after debt (60%) and multiple attractiveness (40%)."""
    if finance.net_cash_flow_after_debt is None or finance.multiple is None:
        return 0.0
    # Net component: $0 -> 0, $300K+ -> 100.
    net_component = _clamp(finance.net_cash_flow_after_debt / 3_000)
    # Multiple component: <=2x -> 100, >=4x -> 0, linear between.
    mult_component = _clamp((4.0 - finance.multiple) / (4.0 - 2.0) * 100)
    return 0.6 * net_component + 0.4 * mult_component


def qualitative_overall(qual: QualScore | None) -> float | None:
    if qual is None:
        return None
    subs = [
        qual.recession_resistance,
        qual.recurring_revenue,
        qual.owner_independence,
        qual.stability,
        qual.business_not_job,
    ]
    return sum(subs) / len(subs)


def buybox_fit(listing: Listing, buybox: BuyBox) -> float:
    """Fraction of the *specified* buy-box criteria the listing satisfies, 0–100.
    Criteria the user left blank don't count for or against."""
    checks: list[bool] = []

    if buybox.state:
        checks.append((listing.state or "").upper() == buybox.state.upper())
    if buybox.max_asking_price is not None and listing.asking_price is not None:
        checks.append(listing.asking_price <= buybox.max_asking_price)
    if buybox.min_cash_flow is not None and listing.cash_flow_sde is not None:
        checks.append(listing.cash_flow_sde >= buybox.min_cash_flow)
    if buybox.max_multiple is not None and listing.has_core_financials():
        checks.append(compute_multiple(listing.asking_price, listing.cash_flow_sde) <= buybox.max_multiple)
    if buybox.industries:
        text = f"{listing.industry or ''} {listing.title or ''}".lower()
        checks.append(any(ind.lower() in text for ind in buybox.industries))

    if not checks:
        return 100.0  # no constraints expressed -> everything fits
    return 100.0 * sum(checks) / len(checks)


def red_flags(listing: Listing, finance: FinanceResult) -> list[str]:
    flags: list[str] = []
    if not listing.has_core_financials():
        flags.append("Missing core financials (asking price / cash flow)")
    if listing.partial:
        flags.append("Incomplete listing data")
    if finance.multiple is not None and finance.multiple > 3.5:
        flags.append(f"High multiple ({finance.multiple:.1f}x)")
    if finance.net_cash_flow_after_debt is not None and finance.net_cash_flow_after_debt <= 0:
        flags.append("Negative cash flow after debt service")
    if (
        listing.cash_flow_sde
        and finance.annual_debt_service
        and finance.annual_debt_service > 0
        and (listing.cash_flow_sde / finance.annual_debt_service) < MIN_DSCR
    ):
        flags.append(f"Thin debt-service coverage (DSCR < {MIN_DSCR})")
    if listing.year_established:
        age = _dt.date.today().year - listing.year_established
        if age < 3:
            flags.append("Young business (<3 yrs established)")
    return flags


def composite(finance_s: float, qual_overall: float | None, fit: float) -> float:
    """Weighted blend. If qualitative is absent, its weight is redistributed
    proportionally over finance + buy-box fit."""
    w = dict(SCORE_WEIGHTS)
    if qual_overall is None:
        keep = w["finance"] + w["buybox_fit"]
        return _clamp(finance_s * (w["finance"] / keep) + fit * (w["buybox_fit"] / keep))
    return _clamp(finance_s * w["finance"] + qual_overall * w["qualitative"] + fit * w["buybox_fit"])


def score_deal(
    listing: Listing,
    buybox: BuyBox,
    qual: QualScore | None = None,
    market=None,
    *,
    mgmt_cost: float = 0.0,
) -> DealScore:
    """Produce the full per-listing verdict. ``market`` is an optional
    ``MarketAssessment`` that nudges the resale estimate (geo/market factors)."""
    if listing.has_core_financials():
        from ..valuation import flip_scenarios

        flips = flip_scenarios(listing, qual, market)  # derived resale-multiple ranges
        finance = build_finance_result(
            listing.asking_price, listing.cash_flow_sde, mgmt_cost=mgmt_cost, flips=flips
        )
    else:
        finance = FinanceResult()

    fin_s = finance_score(finance)
    qual_o = qualitative_overall(qual)
    fit = buybox_fit(listing, buybox)
    flags = red_flags(listing, finance) + (qual.red_flags if qual else [])

    return DealScore(
        listing=listing,
        finance=finance,
        qualitative=qual,
        buybox_fit=round(fit, 1),
        composite=round(composite(fin_s, qual_o, fit), 1),
        red_flags=flags,
    )


def rank_deals(
    listings: list[Listing],
    buybox: BuyBox,
    quals: dict[str, QualScore] | None = None,
    markets: dict | None = None,
    *,
    mgmt_cost: float = 0.0,
) -> list[DealScore]:
    """Score every listing and return them sorted best-first by composite.
    ``quals`` and ``markets`` map listing.url -> QualScore / MarketAssessment (optional)."""
    quals = quals or {}
    markets = markets or {}
    scored = [
        score_deal(l, buybox, quals.get(l.url), markets.get(l.url), mgmt_cost=mgmt_cost)
        for l in listings
    ]
    return sorted(scored, key=lambda d: d.composite, reverse=True)
