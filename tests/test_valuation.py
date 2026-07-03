"""Resale valuation model — anchored to docs/DESIGN.md §8. Pure, no network/LLM."""

from merjack.models import Listing, MarketAssessment, QualScore
from merjack.valuation import flip_scenarios, size_base


def _listing(sde, asking=None, partial=False, **kw):
    return Listing(url="v/1", title="Co", cash_flow_sde=sde,
                   asking_price=asking if asking is not None else sde * 3, partial=partial, **kw)


def _qual(owner, recurring, stability):
    return QualScore(recession_resistance=50, recurring_revenue=recurring,
                     owner_independence=owner, stability=stability, business_not_job=50)


def test_size_base_monotonic():
    sdes = [100_000, 300_000, 600_000, 1_200_000, 4_000_000]
    bases = [size_base(s) for s in sdes]
    assert bases == sorted(bases)            # bigger SDE -> higher base
    assert 2.5 <= bases[0] <= 3.0
    assert bases[-1] == 5.0                  # clamps at the top band


def test_scenarios_shape_and_range():
    flips = flip_scenarios(_listing(617_000, 1_800_000), _qual(55, 65, 75))
    assert [f.name for f in flips] == ["quick_flip", "scale_flip"]
    for f in flips:
        assert f.multiple_low < f.target_multiple < f.multiple_high
        assert f.breakdown and f.breakdown[0].startswith("base")
        # profit = point × SDE − asking, consistent
        assert f.projected_profit == f.projected_sale_price - 1_800_000


def test_home_inspection_reproduces_rubric():
    # ~4x as-is, higher when scaled — matches the video's 4 / 4.5.
    quick, scale = flip_scenarios(_listing(617_000, 1_800_000), _qual(55, 65, 75))
    assert 3.6 <= quick.target_multiple <= 4.2
    assert scale.target_multiple > quick.target_multiple
    assert 4.2 <= scale.target_multiple <= 4.9


def test_small_owner_dependent_discretionary_is_low():
    quick, _ = flip_scenarios(_listing(180_000, 540_000), _qual(owner=20, recurring=15, stability=10))
    assert quick.target_multiple < 3.0


def test_large_absentee_recurring_is_high():
    quick, _ = flip_scenarios(_listing(1_200_000, 3_600_000), _qual(owner=90, recurring=85, stability=85))
    assert quick.target_multiple > 4.6


def test_no_qualitative_is_neutral_and_wider():
    listing = _listing(617_000, 1_800_000)
    with_qual, _ = flip_scenarios(listing, _qual(55, 65, 75))
    no_qual, _ = flip_scenarios(listing, None)
    # Neutral factors -> point near the size base.
    assert abs(no_qual.target_multiple - size_base(617_000)) < 0.05
    # Lower confidence -> wider range.
    assert (no_qual.multiple_high - no_qual.multiple_low) > (with_qual.multiple_high - with_qual.multiple_low)


def test_market_assessment_shifts_estimate():
    listing, qual = _listing(617_000, 1_800_000), _qual(55, 65, 75)
    base = flip_scenarios(listing, qual)[0].target_multiple
    up = flip_scenarios(listing, qual, MarketAssessment(geo_market_factor=1.0))[0].target_multiple
    down = flip_scenarios(listing, qual, MarketAssessment(geo_market_factor=-1.0))[0].target_multiple
    assert down < base < up   # snow-plowing-in-MN (+) vs in-CA (−)


def test_missing_financials_yields_no_scenarios():
    assert flip_scenarios(Listing(url="v/2", title="Mystery")) == []
