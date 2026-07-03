"""The main deal pipeline as a LangGraph graph.

    START -> source -> qualitative -> rank -> END

Each node is a thin wrapper over functions from the deterministic/LLM layers:
  * source      -> DealSource.fetch        (manual import now, live browser in M5)
  * qualitative -> qualitative.score_many  (LLM; skipped when use_qualitative=False)
  * rank        -> scoring.rank_deals       (deterministic finance + composite)

Explanation (M4) and a human-in-the-loop approval gate (M5) slot in as extra nodes
without disturbing this spine.
"""

from __future__ import annotations

from typing import Optional

from langgraph.graph import END, START, StateGraph

from ..analysis.qualitative import score_many
from ..analysis.scoring import rank_deals
from ..models import BuyBox, DealScore, Profile
from ..sources.base import DealSource
from .state import PipelineState


def build_pipeline(source: DealSource, model=None, market_search=None, market_model=None, checkpointer=None):
    """Compile the pipeline graph for a given deal source.

    ``model`` is injected into the qualitative node (a real chat model, or a test
    fake); ``None`` lets the qualitative layer resolve the configured scoring model.
    ``checkpointer`` is optional (used for resumable runs / HITL from M5).
    """

    def source_node(state: PipelineState) -> dict:
        listings = source.fetch(state["buybox"], state.get("limit", 25))
        return {"listings": listings}

    def qualitative_node(state: PipelineState) -> dict:
        if not state.get("use_qualitative", False):
            return {"quals": {}}
        return {"quals": score_many(state["listings"], model=model)}

    def market_node(state: PipelineState) -> dict:
        if not state.get("use_market", False):
            return {"markets": {}}
        from ..analysis.market import assess_market

        markets = {
            l.url: assess_market(l, search=market_search, model=market_model)
            for l in state["listings"]
        }
        return {"markets": markets}

    def rank_node(state: PipelineState) -> dict:
        ranked = rank_deals(
            state["listings"], state["buybox"], state.get("quals", {}), state.get("markets", {})
        )
        return {"ranked": ranked}

    graph = StateGraph(PipelineState)
    graph.add_node("source", source_node)
    graph.add_node("qualitative", qualitative_node)
    graph.add_node("market", market_node)
    graph.add_node("rank", rank_node)
    graph.add_edge(START, "source")
    graph.add_edge("source", "qualitative")
    graph.add_edge("qualitative", "market")
    graph.add_edge("market", "rank")
    graph.add_edge("rank", END)
    return graph.compile(checkpointer=checkpointer)


def run_pipeline(
    source: DealSource,
    buybox: BuyBox,
    profile: Optional[Profile] = None,
    *,
    limit: int = 25,
    use_qualitative: bool = False,
    use_market: bool = False,
    model=None,
    market_search=None,
    market_model=None,
) -> list[DealScore]:
    """Convenience: build + invoke the pipeline, return the ranked deals."""
    app = build_pipeline(source, model=model, market_search=market_search, market_model=market_model)
    result = app.invoke(
        {
            "buybox": buybox,
            "profile": profile or Profile(),
            "limit": limit,
            "use_qualitative": use_qualitative,
            "use_market": use_market,
        }
    )
    return result["ranked"]
