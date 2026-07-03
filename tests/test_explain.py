"""Tailored deal explanations: deterministic summary + LLM plumbing. No network."""

import types

from merjack.analysis.explain import _deal_facts, explain_deal, summarize_deal
from merjack.analysis.scoring import score_deal
from merjack.models import BuyBox, Listing, Proficiency, Profile, QualScore


def _deal(qual=None):
    listing = Listing(url="e/1", title="Reliable Home Inspection", state="NY", industry="home inspection",
                      asking_price=1_800_000, cash_flow_sde=617_000, year_established=1994)
    buybox = BuyBox(state="NY", max_asking_price=2_000_000, min_cash_flow=300_000, max_multiple=3.0)
    return score_deal(listing, buybox, qual)


def test_summary_levels_differ_and_scale_with_verbosity():
    deal = _deal()
    nov = summarize_deal(deal, Profile(proficiency=Proficiency.novice))
    inter = summarize_deal(deal, Profile(proficiency=Proficiency.intermediate))
    exp = summarize_deal(deal, Profile(proficiency=Proficiency.expert))
    assert nov != inter and inter != exp
    assert len(nov) > len(exp)               # novice is more explanatory than expert
    assert "out of 100" in nov               # composite, spelled out for novices
    for s in (nov, inter, exp):
        assert "2.9" in s                    # the ~2.92x multiple appears at every level


def test_summary_flags_risk_state():
    exp = summarize_deal(_deal(), Profile(proficiency=Proficiency.expert))
    assert "risk" in exp.lower()


def test_deal_facts_carries_numbers_and_financing():
    facts = _deal_facts(_deal())
    assert "Asking price: $1,800,000" in facts
    assert "Cash flow (SDE): $617,000" in facts
    # Financing details so the model reasons about the right loan structure, not a guess.
    assert "Financing (estimated): 10% down" in facts
    assert "debt service" in facts


class _FakeModel:
    def __init__(self, text):
        self.text = text
        self.captured = None

    def invoke(self, messages):
        self.captured = messages
        return types.SimpleNamespace(content=self.text)


def test_explain_uses_model_with_level_and_facts():
    fake = _FakeModel("Solid deal at under 3x with healthy cash flow.")
    out = explain_deal(_deal(), Profile(proficiency=Proficiency.novice), model=fake)
    assert out == "Solid deal at under 3x with healthy cash flow."
    system_role, human_role = fake.captured
    assert system_role[0] == "system" and "new to buying businesses" in system_role[1]
    assert "Home Inspection" in human_role[1]


def test_explain_strips_em_dashes_and_curly_quotes():
    fake = _FakeModel("Strong deal — really solid, 3.7–4.6x range, “great” cash flow.")
    out = explain_deal(_deal(), Profile(proficiency=Proficiency.expert), model=fake)
    assert "—" not in out and "–" not in out
    assert "“" not in out and "”" not in out
    assert "-" in out and '"great"' in out


def test_explain_falls_back_to_summary_on_error():
    class _Boom:
        def invoke(self, messages):
            raise RuntimeError("model down")

    deal = _deal()
    profile = Profile(proficiency=Proficiency.expert)
    assert explain_deal(deal, profile, model=_Boom()) == summarize_deal(deal, profile)
