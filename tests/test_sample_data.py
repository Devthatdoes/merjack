"""Random listing generator: deterministic, parseable, and varied."""

from merjack.models import BuyBox
from merjack.sample_data import generate_listings
from merjack.sources import ManualSource


def test_deterministic_with_seed():
    assert generate_listings(10, seed=7) == generate_listings(10, seed=7)
    assert generate_listings(10, seed=7) != generate_listings(10, seed=8)


def test_count_and_parseable():
    rows = generate_listings(15, seed=3)
    assert len(rows) == 15
    listings = ManualSource.from_rows(rows).fetch(BuyBox())
    assert len(listings) == 15
    assert all(l.has_core_financials() for l in listings)
    assert all(not l.partial for l in listings)  # complete rows -> not partial


def test_variety_spans_good_and_bad():
    listings = ManualSource.from_rows(generate_listings(40, seed=1)).fetch(BuyBox())
    multiples = [l.asking_price / l.cash_flow_sde for l in listings]
    assert max(multiples) - min(multiples) > 1.0       # a real spread of deal quality
    assert min(multiples) < 3.0 and max(multiples) > 3.5
    assert len({l.industry for l in listings}) >= 6     # varied industries
