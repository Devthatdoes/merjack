"""Manual import source + query URL builder. No network."""

from merjack.models import BuyBox
from merjack.sources import DealSource, ManualSource
from merjack.sources.manual_source import _num, row_to_listing
from merjack.sources.query import build_search_url, state_slug


# --- number coercion ------------------------------------------------------ #
def test_num_coercion():
    assert _num("$1,800,000") == 1_800_000
    assert _num("617K") == 617_000
    assert _num("1.8M") == 1_800_000
    assert _num(350000) == 350_000
    assert _num("") is None
    assert _num(None) is None
    assert _num("n/a") is None


# --- row normalization + aliases ------------------------------------------ #
def test_row_to_listing_with_aliases():
    row = {
        "Name": "Reliable Home Inspection",
        "Price": "$1,800,000",
        "Cash Flow": "617K",
        "State": "NY",
        "Category": "home inspection",
        "Established": "1994",
        "link": "https://x/1",
    }
    listing = row_to_listing(row)
    assert listing.title == "Reliable Home Inspection"
    assert listing.asking_price == 1_800_000
    assert listing.cash_flow_sde == 617_000
    assert listing.state == "NY"
    assert listing.industry == "home inspection"
    assert listing.year_established == 1994
    assert listing.url == "https://x/1"
    assert listing.has_core_financials()
    assert listing.partial is False


def test_row_missing_identity_is_partial():
    listing = row_to_listing({"price": "500000"}, index=3)
    assert listing.url == "manual:3"
    assert listing.title == "Untitled listing"
    assert listing.partial is True  # synthesized identity


def test_row_missing_financials_is_partial():
    listing = row_to_listing({"url": "https://x/2", "title": "Mystery Co"})
    assert listing.partial is True  # no asking/cash flow


# --- ManualSource ---------------------------------------------------------- #
def test_manual_source_is_a_dealsource():
    src = ManualSource.from_rows([])
    assert isinstance(src, DealSource)  # structural / runtime_checkable
    assert src.name == "manual"


def test_manual_source_fetch_and_limit():
    rows = [{"title": f"Co {i}", "url": f"u/{i}", "price": "900000", "sde": "350000"} for i in range(5)]
    src = ManualSource.from_rows(rows)
    listings = src.fetch(BuyBox(), limit=3)
    assert len(listings) == 3
    assert listings[0].asking_price == 900_000


def test_manual_source_from_csv(tmp_path):
    csv_path = tmp_path / "deals.csv"
    csv_path.write_text(
        "name,price,cash_flow,state\n"
        "Print Co,600000,310000,NY\n"
        "Boutique,2000000,300000,CA\n",
        encoding="utf-8",
    )
    src = ManualSource.from_csv(csv_path)
    listings = src.fetch(BuyBox())
    assert len(listings) == 2
    assert listings[0].title == "Print Co"
    assert listings[0].cash_flow_sde == 310_000


# --- query URL ------------------------------------------------------------- #
def test_state_slug():
    assert state_slug("NY") == "new-york"
    assert state_slug("ca") == "california"
    assert state_slug("Puerto Rico") == "puerto-rico"  # fallback slugify


def test_build_search_url():
    url = build_search_url(BuyBox(state="NY", max_asking_price=1_000_000, min_cash_flow=300_000))
    assert "new-york-businesses-for-sale" in url
    assert "priceMax=1000000" in url
    assert "cashFlowMin=300000" in url


def test_build_search_url_no_state():
    url = build_search_url(BuyBox())
    assert url.endswith("/businesses-for-sale/")
