"""Deal chat: prompt assembly, history mapping, output cleaning. No network."""

import types

from merjack.analysis.scoring import score_deal
from merjack.chat import answer
from merjack.models import BuyBox, Listing, Proficiency, Profile


def _deal():
    listing = Listing(url="c/1", title="Reliable Home Inspection", state="NY", industry="home inspection",
                      asking_price=1_800_000, cash_flow_sde=617_000, year_established=1994)
    buybox = BuyBox(state="NY", max_asking_price=2_000_000, min_cash_flow=300_000, max_multiple=3.0)
    return score_deal(listing, buybox)


class _FakeModel:
    def __init__(self, text):
        self.text = text
        self.captured = None

    def invoke(self, messages):
        self.captured = messages
        return types.SimpleNamespace(content=self.text)


def test_answer_carries_facts_history_and_question():
    fake = _FakeModel("The 2.92x multiple is healthy for a stable service business.")
    history = [("user", "Is it cheap?"), ("assistant", "Relatively, yes.")]
    out = answer(_deal(), Profile(proficiency=Proficiency.novice), history, "Why is the multiple good?", model=fake)

    assert out == "The 2.92x multiple is healthy for a stable service business."
    msgs = fake.captured
    assert msgs[0][0] == "system" and "Home Inspection" in msgs[0][1]
    assert ("human", "Is it cheap?") in msgs        # user mapped to human
    assert ("ai", "Relatively, yes.") in msgs       # assistant mapped to ai
    assert msgs[-1] == ("human", "Why is the multiple good?")


def test_answer_cleans_em_dashes():
    fake = _FakeModel("Strong deal — about 2.9x, solid cash flow.")
    out = answer(_deal(), Profile(proficiency=Proficiency.expert), [], "thoughts?", model=fake)
    assert "—" not in out and "-" in out


def test_answer_level_instruction_changes_with_profile():
    fake = _FakeModel("ok")
    answer(_deal(), Profile(proficiency=Proficiency.novice), [], "q", model=fake)
    novice_system = fake.captured[0][1]
    answer(_deal(), Profile(proficiency=Proficiency.expert), [], "q", model=fake)
    expert_system = fake.captured[0][1]
    assert novice_system != expert_system
    assert "new to buying businesses" in novice_system
