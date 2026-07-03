"""Pydantic data models shared across the whole app.

These are framework-agnostic (no LangChain/LangGraph imports) so they can be used
by the deterministic finance/scoring layers, the LLM structured-output layer, the
storage layer, and the UI alike.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# User profile + buy-box (intake)
# --------------------------------------------------------------------------- #
class Proficiency(str, Enum):
    novice = "novice"
    intermediate = "intermediate"
    expert = "expert"


class Strategy(str, Enum):
    hold = "hold"              # buy and keep the cash flow
    quick_flip = "quick_flip"  # buy well, resell as-is / with existing management
    scale_flip = "scale_flip"  # add a management layer, scale, resell higher


class OwnerInvolvement(str, Enum):
    absentee = "absentee"          # owner barely works in it
    semi = "semi"                  # owner does some operational work
    owner_operated = "operated"    # owner is essential day-to-day
    any = "any"


class Profile(BaseModel):
    """Who the user is — drives how much we explain."""

    proficiency: Proficiency = Proficiency.novice


class BuyBox(BaseModel):
    """The user's acquisition filters / preferences."""

    state: Optional[str] = Field(None, description="2-letter US state, or None for anywhere")
    max_asking_price: Optional[float] = None
    min_cash_flow: Optional[float] = Field(None, description="Minimum annual SDE/cash flow")
    max_multiple: Optional[float] = Field(None, description="Max acceptable asking ÷ cash flow")
    industries: list[str] = Field(default_factory=list)
    owner_involvement: OwnerInvolvement = OwnerInvolvement.any
    strategy: Strategy = Strategy.quick_flip


# --------------------------------------------------------------------------- #
# Listing (normalized output of any DealSource)
# --------------------------------------------------------------------------- #
class Listing(BaseModel):
    """A normalized business-for-sale listing. Fields mirror what marketplaces
    expose; anything unknown stays None and the listing is flagged ``partial``."""

    url: str
    title: str
    source: str = "bizbuysell"

    # Financials
    asking_price: Optional[float] = None
    cash_flow_sde: Optional[float] = Field(None, description="Seller's discretionary earnings / cash flow")
    ebitda: Optional[float] = None
    revenue: Optional[float] = None

    # Descriptors
    location: Optional[str] = None
    state: Optional[str] = None
    industry: Optional[str] = None
    year_established: Optional[int] = None
    employees: Optional[int] = None
    description: Optional[str] = None
    reason_for_selling: Optional[str] = None

    # Assets / flags
    real_estate_included: Optional[bool] = None
    real_estate_value: Optional[float] = None
    ffe_value: Optional[float] = Field(None, description="Furniture/fixtures/equipment value")
    home_based: Optional[bool] = None

    # Broker
    broker_name: Optional[str] = None
    broker_firm: Optional[str] = None

    partial: bool = Field(False, description="True if key fields were missing during sourcing")

    def has_core_financials(self) -> bool:
        return self.asking_price is not None and self.cash_flow_sde not in (None, 0)


# --------------------------------------------------------------------------- #
# Analysis outputs
# --------------------------------------------------------------------------- #
class MarketAssessment(BaseModel):
    """Output of the (paid-tier) LLM web-grounded geo/market qualifier. Neutral by default,
    so the deterministic path works without it."""

    geo_market_factor: float = Field(0.0, ge=-1.0, le=1.0, description="Industry × location fit")
    market_env_factor: float = Field(0.0, ge=-1.0, le=1.0, description="Macro M&A climate")
    rationale: str = ""
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class ResaleEstimate(BaseModel):
    """A derived resale-multiple estimate with a low–high range and a factor breakdown."""

    point: float
    low: float
    high: float
    breakdown: list[str] = Field(default_factory=list)


class FlipScenario(BaseModel):
    name: str
    target_multiple: float
    sde_adjustment: float = Field(0.0, description="Applied to SDE before multiplying (e.g. -mgmt cost)")
    projected_sale_price: float
    projected_profit: float
    # Derived resale-multiple range (None on the legacy/flat-constant path).
    multiple_low: Optional[float] = None
    multiple_high: Optional[float] = None
    breakdown: list[str] = Field(default_factory=list)


class FinanceResult(BaseModel):
    multiple: Optional[float] = None
    down_payment: Optional[float] = None
    loan_amount: Optional[float] = None
    monthly_debt_service: Optional[float] = None
    annual_debt_service: Optional[float] = None
    net_cash_flow_after_debt: Optional[float] = None
    monthly_owner_income: Optional[float] = None
    flips: list[FlipScenario] = Field(default_factory=list)


class QualScore(BaseModel):
    """LLM-produced qualitative sub-scores (0–100 each) + rationale."""

    recession_resistance: int = Field(..., ge=0, le=100)
    recurring_revenue: int = Field(..., ge=0, le=100)
    owner_independence: int = Field(..., ge=0, le=100, description="Can it run without the owner?")
    stability: int = Field(..., ge=0, le=100, description="Track record / age / systems in place")
    business_not_job: int = Field(..., ge=0, le=100, description="Is this a business vs. buying a job?")
    rationale: str = ""
    red_flags: list[str] = Field(default_factory=list)


class DealScore(BaseModel):
    """Final per-listing verdict that the UI renders and ranks on."""

    listing: Listing
    finance: FinanceResult
    qualitative: Optional[QualScore] = None
    buybox_fit: float = Field(0.0, ge=0, le=100)
    composite: float = Field(0.0, ge=0, le=100)
    red_flags: list[str] = Field(default_factory=list)
    explanation: Optional[str] = None
