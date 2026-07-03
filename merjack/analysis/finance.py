"""Deterministic deal finance — the heart of the rating system.

Pure functions, stdlib only (no Pydantic/LangChain at import time), so this module
and its tests run with zero setup and are locked to known-good numbers from the
deal rubric:

    $1.8M ask, $617K SDE, 10% down, 10yr SBA @ ~10.5%
      -> multiple ~2.9x, annual debt service ~$262K, net ~$355K

    Quick flip:  4.0 x $350K SDE = $1.40M  -> profit $0.50M on a $900K buy
    Scale flip:  4.5 x $620K SDE = $2.79M  -> profit $0.99M on a $1.80M buy

The ``build_finance_result`` adapter (which maps into the Pydantic models) imports
Pydantic lazily so the core math stays dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import SBA, QUICK_FLIP_MULTIPLE, SCALE_FLIP_MULTIPLE


# --------------------------------------------------------------------------- #
# Core primitives
# --------------------------------------------------------------------------- #
def compute_multiple(asking_price: float, sde: float) -> float:
    """Acquisition multiple = asking price ÷ annual cash flow (SDE)."""
    if sde <= 0:
        raise ValueError("SDE must be positive to compute a multiple")
    return asking_price / sde


def amortized_payment(principal: float, annual_rate: float, term_years: int) -> float:
    """Standard fixed-rate amortized **monthly** payment."""
    n = term_years * 12
    r = annual_rate / 12.0
    if r == 0:
        return principal / n
    factor = (1 + r) ** n
    return principal * r * factor / (factor - 1)


@dataclass(frozen=True)
class DebtService:
    asking_price: float
    down_payment: float
    loan_amount: float
    monthly_payment: float
    annual_payment: float


def sba_debt_service(
    asking_price: float,
    annual_rate: float = SBA.annual_rate,
    term_years: int = SBA.term_years,
    down_pct: float = SBA.down_pct,
) -> DebtService:
    """Model an SBA-financed purchase: ``down_pct`` down, the rest amortized."""
    down = asking_price * down_pct
    loan = asking_price - down
    monthly = amortized_payment(loan, annual_rate, term_years)
    return DebtService(
        asking_price=asking_price,
        down_payment=down,
        loan_amount=loan,
        monthly_payment=monthly,
        annual_payment=monthly * 12,
    )


def net_cash_flow_after_debt(sde: float, annual_debt_service: float) -> float:
    """Owner's annual take-home after servicing the acquisition loan."""
    return sde - annual_debt_service


# --------------------------------------------------------------------------- #
# Flip / scale projections
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Flip:
    name: str
    target_multiple: float
    sde_adjustment: float
    projected_sale_price: float
    projected_profit: float


def flip_projection(
    asking_price: float,
    sde: float,
    target_multiple: float,
    name: str,
    sde_adjustment: float = 0.0,
) -> Flip:
    """Resale projection. ``sde_adjustment`` shifts the SDE the buyer would value
    (e.g. negative to subtract an added management-layer cost)."""
    effective_sde = sde + sde_adjustment
    sale_price = target_multiple * effective_sde
    return Flip(
        name=name,
        target_multiple=target_multiple,
        sde_adjustment=sde_adjustment,
        projected_sale_price=sale_price,
        projected_profit=sale_price - asking_price,
    )


def default_flip_scenarios(asking_price: float, sde: float, mgmt_cost: float = 0.0) -> list[Flip]:
    """The two canonical strategies from the rubric.

    - quick flip: resell as-is / with existing management at ``QUICK_FLIP_MULTIPLE``.
    - scale flip: add a management layer, scale, resell at ``SCALE_FLIP_MULTIPLE``
      (``mgmt_cost`` subtracted from SDE for a conservative view; default 0 assumes
      added capacity offsets the new hires).
    """
    return [
        flip_projection(asking_price, sde, QUICK_FLIP_MULTIPLE, "quick_flip"),
        flip_projection(asking_price, sde, SCALE_FLIP_MULTIPLE, "scale_flip", sde_adjustment=-mgmt_cost),
    ]


# --------------------------------------------------------------------------- #
# Adapter -> Pydantic FinanceResult (lazy import keeps the core dependency-free)
# --------------------------------------------------------------------------- #
def build_finance_result(
    asking_price: float,
    sde: float,
    *,
    annual_rate: float = SBA.annual_rate,
    term_years: int = SBA.term_years,
    down_pct: float = SBA.down_pct,
    mgmt_cost: float = 0.0,
    flips=None,
):
    """Compute the full finance picture and return a ``models.FinanceResult``.

    ``flips`` may be pre-built ``FlipScenario``s from the resale valuation model
    (``merjack.valuation.flip_scenarios``); if omitted, falls back to the legacy flat
    4.0/4.5x constants so this stays usable standalone."""
    from ..models import FinanceResult, FlipScenario

    debt = sba_debt_service(asking_price, annual_rate, term_years, down_pct)
    net = net_cash_flow_after_debt(sde, debt.annual_payment)
    if flips is None:
        flips = [
            FlipScenario(
                name=f.name,
                target_multiple=f.target_multiple,
                sde_adjustment=f.sde_adjustment,
                projected_sale_price=f.projected_sale_price,
                projected_profit=f.projected_profit,
            )
            for f in default_flip_scenarios(asking_price, sde, mgmt_cost=mgmt_cost)
        ]
    return FinanceResult(
        multiple=compute_multiple(asking_price, sde),
        down_payment=debt.down_payment,
        loan_amount=debt.loan_amount,
        monthly_debt_service=debt.monthly_payment,
        annual_debt_service=debt.annual_payment,
        net_cash_flow_after_debt=net,
        monthly_owner_income=net / 12.0,
        flips=flips,
    )
