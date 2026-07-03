"""Shared state passed between pipeline nodes.

A ``TypedDict`` with ``total=False`` so nodes can return partial updates that
LangGraph merges into the running state.
"""

from __future__ import annotations

from typing import TypedDict

from ..models import BuyBox, DealScore, Listing, MarketAssessment, Profile, QualScore


class PipelineState(TypedDict, total=False):
    # Inputs
    profile: Profile
    buybox: BuyBox
    limit: int
    use_qualitative: bool
    use_market: bool
    # Intermediate
    listings: list[Listing]
    quals: dict[str, QualScore]            # listing.url -> QualScore
    markets: dict[str, MarketAssessment]   # listing.url -> MarketAssessment
    # Output
    ranked: list[DealScore]
