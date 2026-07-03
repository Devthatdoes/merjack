"""The ``DealSource`` contract.

A source takes the user's ``BuyBox`` and returns normalized ``Listing`` objects.
It's a ``Protocol`` (structural typing) so a source just needs a ``name`` and a
``fetch`` method — no base class to inherit, and ``isinstance`` still works thanks
to ``runtime_checkable``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import BuyBox, Listing


@runtime_checkable
class DealSource(Protocol):
    name: str

    def fetch(self, buybox: BuyBox, limit: int = 25) -> list[Listing]:
        """Return up to ``limit`` normalized listings for the given buy-box."""
        ...
