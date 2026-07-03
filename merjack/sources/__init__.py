"""Deal sources — anything that turns a BuyBox into a list of normalized Listings.

Both the manual importer (M3) and the live browser agent (M5) implement the same
``DealSource`` protocol, so the downstream pipeline never cares which one ran.
"""

from .base import DealSource
from .bizbuysell_api import BizBuySellApiSource
from .manual_source import ManualSource

__all__ = ["DealSource", "ManualSource", "BizBuySellApiSource"]
