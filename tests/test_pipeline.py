"""End-to-end LangGraph pipeline on manual-source fixtures. No network."""

from merjack.graph import run_pipeline
from merjack.models import BuyBox, DealScore, QualScore
from merjack.sources import ManualSource

FIXTURES = [
    {"title": "Reliable Home Inspection", "url": "b/1", "state": "NY",
     "industry": "home inspection", "price": "1800000", "cash_flow": "617000", "established": "1994"},
    {"title": "Printing & Promo Center", "url": "b/2", "state": "NY",
     "industry": "printing", "price": "600000", "cash_flow": "310000", "established": "2006"},
    {"title": "Trendy Boutique", "url": "b/3", "state": "CA",
     "industry": "retail", "price": "2000000", "cash_flow": "300000", "established": "2024"},
]

BUYBOX = BuyBox(state="NY", max_asking_price=2_000_000, min_cash_flow=300_000, max_multiple=3.0)


def test_pipeline_ranks_without_llm():
    ranked = run_pipeline(ManualSource.from_rows(FIXTURES), BUYBOX, use_qualitative=False)
    assert len(ranked) == 3
    assert all(isinstance(d, DealScore) for d in ranked)
    # Strong service businesses on top, overpriced young retail at the bottom.
    assert ranked[0].listing.url in {"b/1", "b/2"}
    assert ranked[-1].listing.url == "b/3"
    assert ranked[0].composite >= ranked[-1].composite
    assert ranked[-1].qualitative is None  # qualitative skipped


def test_pipeline_runs_qualitative_node_with_fake_model():
    class _FakeStructured:
        def __init__(self, payload):
            self._payload = payload

        def invoke(self, messages):
            return self._payload

    class FakeModel:
        def __init__(self, payload):
            self.payload = payload

        def with_structured_output(self, schema):
            return _FakeStructured(self.payload)

    payload = QualScore(
        recession_resistance=80, recurring_revenue=70, owner_independence=65,
        stability=75, business_not_job=70, rationale="ok",
    )
    ranked = run_pipeline(
        ManualSource.from_rows(FIXTURES), BUYBOX, use_qualitative=True, model=FakeModel(payload)
    )
    assert all(d.qualitative is not None for d in ranked)
    assert ranked[0].qualitative.recession_resistance == 80
