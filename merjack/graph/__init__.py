"""LangGraph orchestration — the only place a framework drives the flow.

The graph wires the plain-Python pieces (source -> qualitative -> rank) together;
the nodes themselves just call functions you've already seen and tested.
"""

from .pipeline import build_pipeline, run_pipeline

__all__ = ["build_pipeline", "run_pipeline"]
