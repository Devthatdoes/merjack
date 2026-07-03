"""The ``SearchProvider`` contract.

Like ``DealSource`` and ``llm``, search is behind an interface so the default
(self-hosted SearXNG) can be swapped for a hosted API without touching callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@runtime_checkable
class SearchProvider(Protocol):
    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Return up to ``limit`` results for ``query``."""
        ...
