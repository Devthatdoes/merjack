"""Lock the deterministic finance engine to the deal rubric's known-good numbers.

If these pass, the entire rating system rests on math we trust. No network, no LLM.
"""

import math

from merjack.analysis.finance import (
    amortized_payment,
    compute_multiple,
    default_flip_scenarios,
    flip_projection,
    net_cash_flow_after_debt,
    sba_debt_service,
)

# The video's home-inspection deal.
ASK = 1_800_000
SDE = 617_000


def test_multiple_under_3x():
    m = compute_multiple(ASK, SDE)
    assert math.isclose(m, 2.92, abs_tol=0.02)
    assert m < 3.0  # fits the buy-box


def test_sba_debt_service_matches_video():
    # 10% down -> $1.62M financed over 10 yrs at ~10.5%.
    debt = sba_debt_service(ASK, annual_rate=0.105, term_years=10, down_pct=0.10)
    assert debt.down_payment == 180_000
    assert debt.loan_amount == 1_620_000
    # Video/ChatGPT quoted ~$260K/yr; we get ~$262K. Assert a tight but tolerant band.
    assert 255_000 <= debt.annual_payment <= 270_000
    assert math.isclose(debt.monthly_payment, debt.annual_payment / 12)


def test_net_cash_flow_matches_video():
    debt = sba_debt_service(ASK, annual_rate=0.105, term_years=10, down_pct=0.10)
    net = net_cash_flow_after_debt(SDE, debt.annual_payment)
    # Video said ~$357K net; ~$355K here. Band covers rate sensitivity.
    assert 347_000 <= net <= 362_000


def test_amortization_zero_rate():
    # Degenerate case: no interest -> principal split evenly across the term.
    assert amortized_payment(120_000, 0.0, 10) == 120_000 / 120


def test_quick_flip_profit_500k():
    # $900K buy, $350K SDE, resell at 4.0x -> $1.4M -> $500K profit.
    flip = flip_projection(900_000, 350_000, 4.0, "quick_flip")
    assert flip.projected_sale_price == 1_400_000
    assert flip.projected_profit == 500_000


def test_scale_flip_profit_990k():
    # $1.8M buy, $620K SDE, resell at 4.5x -> $2.79M -> $990K profit.
    flip = flip_projection(1_800_000, 620_000, 4.5, "scale_flip")
    assert flip.projected_sale_price == 2_790_000
    assert flip.projected_profit == 990_000


def test_default_scenarios_shape():
    scenarios = default_flip_scenarios(ASK, SDE)
    assert [s.name for s in scenarios] == ["quick_flip", "scale_flip"]
    assert scenarios[0].target_multiple == 4.0
    assert scenarios[1].target_multiple == 4.5
