"""Web search providers. SearXNG is the default; a hosted API can swap in behind the
same ``SearchProvider`` interface (see docs/DESIGN.md §8)."""

from .base import SearchProvider, SearchResult
from .searxng import SearxngSearch

__all__ = ["SearchProvider", "SearchResult", "SearxngSearch"]
