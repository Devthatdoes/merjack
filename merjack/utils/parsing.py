"""Utilities for parsing human-formatted financial strings into floats.
Supports formats like '$1.2M', '500k', '1,800,000', and '1.8 million'.
"""

from __future__ import annotations
import re

def parse_money(value: str | float | int | None) -> float | None:
    """Convert a financial string or number into a float.
    Returns None if the value is empty, 'unknown', or unparseable.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    
    # Normalize input
    s = str(value).strip().lower()
    if not s or s in ("unknown", "n/a", "none", "-"):
        return None
    
    # Remove currency symbols and commas
    s = s.replace("$", "").replace(",", "")
    
    # Handle common suffixes
    multiplier = 1.0
    if s.endswith("k"):
        multiplier = 1_000.0
        s = s[:-1]
    elif s.endswith("m") or "million" in s:
        multiplier = 1_000_000.0
        s = s.replace("million", "").strip()
        if s.endswith("m"):
            s = s[:-1]
    elif s.endswith("b") or "billion" in s:
        multiplier = 1_000_000_000.0
        s = s.replace("billion", "").strip()
        if s.endswith("b"):
            s = s[:-1]
    
    try:
        # Extract first valid number pattern (handles "1.2 million" or "Price: 500k")
        match = re.search(r"[-+]?\d*\.?\d+", s)
        if not match:
            return None
        return float(match.group()) * multiplier
    except (ValueError, TypeError):
        return None
