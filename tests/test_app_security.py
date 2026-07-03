"""User-controlled listing fields must be escaped before going into raw HTML."""

from app import deal_list_card
from merjack.analysis.scoring import score_deal
from merjack.models import BuyBox, Listing


def test_deal_card_escapes_user_html():
    listing = Listing(
        url="x/1", title="<script>alert(1)</script>", state="NY",
        industry="<b>hvac</b>", asking_price=900_000, cash_flow_sde=350_000,
    )
    out = deal_list_card(score_deal(listing, BuyBox()), BuyBox())
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "<b>hvac</b>" not in out
