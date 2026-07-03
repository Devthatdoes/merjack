"""Manual import source — the ToS-safe, zero-infra way to feed the pipeline.

You paste/export listings (CSV or JSON) and this normalizes them into ``Listing``
objects. It's the default source on the free tier and the fixture source for
tests, so the whole analyze -> rank -> explain pipeline can run with no network.

Column/key names are matched flexibly (aliases below), and money strings like
``"$1,800,000"`` or ``"617K"`` are coerced to numbers.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from ..models import BuyBox, Listing

# Listing field -> accepted input column/key names (lowercased).
FIELD_ALIASES: dict[str, list[str]] = {
    "url": ["url", "link", "listing_url"],
    "title": ["title", "name", "business_name", "headline"],
    "asking_price": ["asking_price", "price", "asking", "ask"],
    "cash_flow_sde": ["cash_flow_sde", "cash_flow", "cashflow", "sde", "seller_discretionary_earnings"],
    "ebitda": ["ebitda"],
    "revenue": ["revenue", "gross_revenue", "sales"],
    "location": ["location", "city"],
    "state": ["state"],
    "industry": ["industry", "category", "sector"],
    "year_established": ["year_established", "established", "year"],
    "employees": ["employees", "num_employees", "staff"],
    "description": ["description", "desc", "summary"],
    "reason_for_selling": ["reason_for_selling", "reason"],
}

_NUM_FIELDS = {"asking_price", "cash_flow_sde", "ebitda", "revenue"}
_INT_FIELDS = {"year_established", "employees"}


def _num(value: Any) -> Optional[float]:
    """Parse ``"$1,800,000"``, ``"617K"``, ``"1.8M"`` -> float; blanks -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("$", "").replace(",", "").replace("_", "")
    if not s:
        return None
    mult = 1.0
    if s[-1:].lower() == "k":
        mult, s = 1_000.0, s[:-1]
    elif s[-1:].lower() == "m":
        mult, s = 1_000_000.0, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


def _pick(row: dict[str, Any], field: str) -> Any:
    for alias in FIELD_ALIASES[field]:
        if alias in row and str(row[alias]).strip() != "":
            return row[alias]
    return None


def row_to_listing(row: dict[str, Any], index: int = 0) -> Listing:
    """Map one loosely-typed row to a normalized ``Listing``."""
    norm = {k.strip().lower().replace(" ", "_"): v for k, v in row.items()}
    data: dict[str, Any] = {}
    for field in FIELD_ALIASES:
        raw = _pick(norm, field)
        if raw is None:
            continue
        if field in _NUM_FIELDS:
            data[field] = _num(raw)
        elif field in _INT_FIELDS:
            n = _num(raw)
            data[field] = int(n) if n is not None else None
        else:
            data[field] = str(raw).strip()

    synthesized = False
    if not data.get("url"):
        data["url"] = f"manual:{index}"
        synthesized = True
    if not data.get("title"):
        data["title"] = "Untitled listing"
        synthesized = True

    listing = Listing(source="manual", **data)
    # Flag as partial if we had to invent identity or core financials are missing.
    listing.partial = synthesized or not listing.has_core_financials()
    return listing


class ManualSource:
    """A ``DealSource`` backed by in-memory rows, a CSV file, or a JSON file."""

    name = "manual"

    def __init__(self, rows: Optional[Iterable[dict[str, Any]]] = None):
        self._rows: list[dict[str, Any]] = list(rows or [])

    @classmethod
    def from_rows(cls, rows: Iterable[dict[str, Any]]) -> "ManualSource":
        return cls(rows=rows)

    @classmethod
    def from_csv(cls, path: str | Path) -> "ManualSource":
        with open(path, newline="", encoding="utf-8") as fh:
            return cls(rows=list(csv.DictReader(fh)))

    @classmethod
    def from_json(cls, path: str | Path) -> "ManualSource":
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            payload = payload.get("listings", [])
        return cls(rows=list(payload))

    def fetch(self, buybox: BuyBox, limit: int = 25) -> list[Listing]:  # noqa: ARG002 - buybox unused
        """Normalize rows into listings (capped at ``limit``).

        Note: no buy-box filtering here on purpose — ranking handles fit, so the
        user still sees near-misses rather than having them silently dropped.
        """
        return [row_to_listing(r, i) for i, r in enumerate(self._rows)][:limit]
