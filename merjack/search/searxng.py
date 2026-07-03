"""SearXNG search client.

Queries a self-hosted SearXNG instance's JSON API (run one with Docker; set
``MERJACK_SEARXNG_URL``, default ``http://localhost:8080``). Free, private, no API key.
A hosted search API could implement the same ``SearchProvider`` interface instead.
"""

from __future__ import annotations

import os

import httpx

from .base import SearchResult

DEFAULT_BASE_URL = os.getenv("MERJACK_SEARXNG_URL", "http://localhost:8080")


class SearxngSearch:
    name = "searxng"

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        resp = httpx.get(
            f"{self.base_url}/search",
            params={"q": query, "format": "json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])[:limit]
        return [
            SearchResult(
                title=str(r.get("title", "")).strip(),
                url=str(r.get("url", "")).strip(),
                snippet=str(r.get("content", "")).strip(),
            )
            for r in results
        ]
