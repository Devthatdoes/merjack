"""Tests for composite scoring/ranking and the qualitative LLM plumbing.

The qualitative test injects a *fake* model, so it verifies wiring + prompt
assembly with no API key and no network.
"""

from merjack.analysis import qualitative
from merjack.analysis.scoring import (
    buybox_fit,
    composite,
    finance_score,
    qualitative_overall,
    rank_deals,
    red_flags,
    score_deal,
)
from merjack.analysis.finance import build_finance_result
from merjack.models import BuyBox, FinanceResult, Listing, QualScore

STRONG = Listing(
    url="http://x/strong",
    title="Strong Print Co",
    state="NY",
    industry="printing",
    asking_price=600_000,
    cash_flow_sde=310_000,  # ~1.94x
)
WEAK = Listing(
    url="http://x/weak",
    title="Pricey Boutique",
    state="CA",
    industry="retail",
    asking_price=2_000_000,
    cash_flow_sde=300_000,  # ~6.67x
)
NO_FIN = Listing(url="http://x/nofin", title="Mystery Co", partial=True)

BUYBOX = BuyBox(state="NY", max_asking_price=1_000_000, min_cash_flow=300_000, max_multiple=3.0)


def test_finance_score_rewards_better_deal():
    s = finance_score(build_finance_result(600_000, 310_000))
    w = finance_score(build_finance_result(2_000_000, 300_000))
    assert s > w
    assert 0 <= w <= 100 and 0 <= s <= 100


def test_buybox_fit():
    assert buybox_fit(STRONG, BUYBOX) == 100.0       # state, price, cash flow, multiple all pass
    assert buybox_fit(WEAK, BUYBOX) == 25.0          # only min_cash_flow passes (1 of 4)
    assert buybox_fit(STRONG, BuyBox()) == 100.0     # no constraints -> fits


def test_red_flags():
    weak_fin = build_finance_result(2_000_000, 300_000)
    flags = red_flags(WEAK, weak_fin)
    assert any("High multiple" in f for f in flags)
    assert any("DSCR" in f for f in flags)

    nofin_flags = red_flags(NO_FIN, FinanceResult())
    assert any("Missing core financials" in f for f in nofin_flags)


def test_composite_redistributes_without_qual():
    # With qual absent, weight shifts onto finance + fit; still in range.
    c = composite(finance_s=80, qual_overall=None, fit=100)
    assert 0 <= c <= 100
    # Adding a strong qual should not throw and stays in range.
    c2 = composite(finance_s=80, qual_overall=90, fit=100)
    assert 0 <= c2 <= 100


def test_qualitative_overall_mean():
    q = QualScore(
        recession_resistance=80,
        recurring_revenue=70,
        owner_independence=60,
        stability=75,
        business_not_job=65,
    )
    assert qualitative_overall(q) == (80 + 70 + 60 + 75 + 65) / 5
    assert qualitative_overall(None) is None


def test_rank_orders_best_first():
    ranked = rank_deals([WEAK, STRONG, NO_FIN], BUYBOX)
    assert [d.listing.url for d in ranked][0] == "http://x/strong"
    assert ranked[0].composite >= ranked[-1].composite
    # The no-financials listing should carry its red flag and sink.
    nofin = next(d for d in ranked if d.listing.url == "http://x/nofin")
    assert any("Missing core financials" in f for f in nofin.red_flags)


def test_score_deal_includes_finance_and_flips():
    deal = score_deal(STRONG, BUYBOX)
    assert deal.finance.multiple is not None
    assert len(deal.finance.flips) == 2
    assert deal.composite > 0


# --------------------------------------------------------------------------- #
# Qualitative plumbing with an injected fake model (no API key / network)
# --------------------------------------------------------------------------- #
class _FakeStructured:
    def __init__(self, payload, captured):
        self._payload = payload
        self._captured = captured

    def invoke(self, messages):
        self._captured.append(messages)
        return self._payload


class FakeModel:
    def __init__(self, payload):
        self.payload = payload
        self.captured: list = []
        self.schema = None

    def with_structured_output(self, schema):
        self.schema = schema
        return _FakeStructured(self.payload, self.captured)


def test_qualitative_scoring_plumbing():
    payload = QualScore(
        recession_resistance=85,
        recurring_revenue=60,
        owner_independence=70,
        stability=80,
        business_not_job=75,
        rationale="Essential service with repeat customers.",
        red_flags=["Owner does some sales"],
    )
    fake = FakeModel(payload)
    result = qualitative.score_listing(STRONG, model=fake)

    assert result is payload
    assert fake.schema is QualScore
    # The human prompt should carry the listing's key facts.
    system_role, human_role = fake.captured[0]
    assert system_role[0] == "system"
    assert human_role[0] == "human"
    assert "Strong Print Co" in human_role[1]
    assert "$600,000" in human_role[1]


def test_qualitative_score_many_skips_failures():
    class Boom(FakeModel):
        def with_structured_output(self, schema):
            class _S:
                def invoke(self, messages):
                    raise RuntimeError("model down")
            return _S()

    out = qualitative.score_many([STRONG, WEAK], model=Boom(None))
    assert out == {}  # failures skipped, no crash
