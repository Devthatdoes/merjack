"""Context-grounded Q&A about a single deal, tailored to the user's experience level.

The model gets the deal's full facts plus the running conversation, and answers questions
about that one deal. Reuses the deal-facts serializer, the level instructions, and the
dash/quote sanitizer from merjack.analysis.explain.
"""

from __future__ import annotations

from typing import Optional

from .analysis.explain import _LEVEL, _deal_facts, _text_of
from .models import DealScore, Profile

_SYSTEM = (
    "You are a business-acquisition analyst answering questions about ONE specific deal. "
    "Use the deal facts below plus general acquisition knowledge. Be honest about what the "
    "data does not tell you, and do not invent numbers. Write in plain professional English. "
    "Do not use em dashes."
)

# Map Streamlit chat roles to LangChain message roles.
_ROLE = {"user": "human", "assistant": "ai"}


def answer(
    deal: DealScore,
    profile: Profile,
    history: list[tuple[str, str]],
    question: str,
    model=None,
) -> str:
    """Answer ``question`` about ``deal``. ``history`` is prior ``(role, content)`` turns
    with role in {"user", "assistant"}."""
    system = f"{_SYSTEM}\n\n{_LEVEL[profile.proficiency]}\n\nDeal facts:\n{_deal_facts(deal)}"
    messages = [("system", system)]
    for role, content in history:
        messages.append((_ROLE.get(role, "human"), content))
    messages.append(("human", question))

    if model is None:
        from .llm import get_model

        model = get_model("explain")
    return _text_of(model.invoke(messages))
