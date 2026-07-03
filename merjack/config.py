"""Central configuration: env-driven SBA defaults, model ids, and scoring weights.

Everything here is plain Python and framework-agnostic. Values come from the
environment (see ``.env.example``) with sensible fallbacks so the deterministic
layers (finance, scoring) work with no setup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _float(key: str, default: float) -> float:
    raw = os.getenv(key)
    return float(raw) if raw not in (None, "") else default


def _int(key: str, default: int) -> int:
    raw = os.getenv(key)
    return int(raw) if raw not in (None, "") else default


@dataclass(frozen=True)
class SBADefaults:
    """Default SBA 7(a) financing terms used to compute debt service."""

    annual_rate: float = _float("MERJACK_SBA_ANNUAL_RATE", 0.105)
    term_years: int = _int("MERJACK_SBA_TERM_YEARS", 10)
    down_pct: float = _float("MERJACK_SBA_DOWN_PCT", 0.10)


SBA = SBADefaults()

# --------------------------------------------------------------------------- #
# Model tiers — the product's "free (base)" vs "paid" switch.
#
#   free : gpt-oss via OpenRouter (one free key) + manual sourcing by default.
#          gpt-oss does tool-calling + structured output well enough for scoring
#          and explanations; its weaker long-horizon agent loops + free rate
#          limits are why live browser sourcing is OFF on this tier.
#   paid : Claude direct (best quality, cheaper than via OpenRouter) + live
#          browser sourcing ON.
#
# Pick with MERJACK_TIER=free|paid. A per-task MERJACK_MODEL_<TASK> env var overrides
# the tier's choice for that one task. Slugs verified against OpenRouter Jun 2026;
# confirm `:free` availability before relying on it in production.
# --------------------------------------------------------------------------- #
TASKS = ("scoring", "explain", "sourcing")

TIERS = {
    "free": {
        "label": "Free — gpt-oss via OpenRouter, manual sourcing",
        "models": {
            "scoring": "openrouter:openai/gpt-oss-20b:free",    # fast, high-volume structured scoring
            "explain": "openrouter:openai/gpt-oss-120b:free",   # better prose for explanations
            "sourcing": "openrouter:openai/gpt-oss-120b:free",  # strongest free tool-caller
        },
        "live_sourcing": False,
    },
    "paid": {
        "label": "Paid — Claude direct, live browser sourcing",
        "models": {
            "scoring": "anthropic:claude-haiku-4-5-20251001",
            "explain": "anthropic:claude-opus-4-8",
            "sourcing": "anthropic:claude-sonnet-4-6",
        },
        "live_sourcing": True,
    },
}

DEFAULT_TIER = "free"


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


def resolve_tier(env: dict | None = None) -> str:
    """The active tier name, from MERJACK_TIER (default ``free``). Pure/testable."""
    env = env if env is not None else os.environ
    tier = (env.get("MERJACK_TIER") or DEFAULT_TIER).strip().lower()
    if tier not in TIERS:
        raise ValueError(f"Unknown MERJACK_TIER {tier!r}; expected one of {list(TIERS)}")
    return tier


def resolve_models(tier: str, env: dict | None = None) -> dict[str, str]:
    """Per-task model ids for ``tier``; a MERJACK_MODEL_<TASK> env var overrides one."""
    env = env if env is not None else os.environ
    presets = TIERS[tier]["models"]
    return {t: (env.get(f"MERJACK_MODEL_{t.upper()}") or presets[t]) for t in TASKS}


def resolve_live_sourcing(tier: str, env: dict | None = None) -> bool:
    """Whether live browser sourcing is on. MERJACK_LIVE_SOURCING overrides the tier."""
    env = env if env is not None else os.environ
    raw = env.get("MERJACK_LIVE_SOURCING")
    if raw not in (None, ""):
        return _truthy(raw)
    return bool(TIERS[tier]["live_sourcing"])


# Resolved once at import from the live environment.
TIER = resolve_tier()
TIER_LABEL = TIERS[TIER]["label"]
MODELS = resolve_models(TIER)           # task -> "provider:model" (resolved lazily in merjack.llm)
LIVE_SOURCING_DEFAULT = resolve_live_sourcing(TIER)

# Composite score weights (must sum to 1.0). Tunable.
SCORE_WEIGHTS = {
    "finance": 0.40,      # net cash flow after debt + multiple attractiveness
    "qualitative": 0.35,  # recession resistance, recurring rev, owner independence, ...
    "buybox_fit": 0.25,   # how well it matches the user's stated filters
}

# Canonical flip targets drawn from the deal rubric (legacy fallback when the
# resale valuation model isn't used).
QUICK_FLIP_MULTIPLE = 4.0   # sell as-is / with existing management
SCALE_FLIP_MULTIPLE = 4.5   # after adding a management layer and scaling

# --------------------------------------------------------------------------- #
# Resale valuation model (docs/DESIGN.md §8). Tunable knobs; calibrate vs sold
# comps later. Multiple = size_base(SDE) × (1 + Σ weight·factor), clamped, ranged.
# --------------------------------------------------------------------------- #
# (annual SDE threshold, base resale multiple) — interpolated; matches broker
# rules of thumb (owner-op service ~2.5–3.5x SDE → larger professionally-run higher).
SIZE_BANDS = [
    (0, 2.5),
    (250_000, 3.0),
    (500_000, 3.5),
    (1_000_000, 4.2),
    (3_000_000, 5.0),
]
# How much a maxed-out factor (∈ [-1, 1]) moves the multiple, as a fraction of base.
RESALE_FACTOR_WEIGHTS = {
    "owner_independence": 0.12,
    "recurring_revenue": 0.08,
    "stability": 0.06,
}
RESALE_GEO_WEIGHT = 0.15      # applied to MarketAssessment.geo_market_factor
RESALE_MARKET_WEIGHT = 0.10   # applied to MarketAssessment.market_env_factor
RESALE_FLOOR, RESALE_CAP = 1.5, 7.0
RESALE_SPREAD = 0.06          # ± fraction of the point; widened when confidence is low
# Scale-flip projection: adding management lifts owner-independence and grows SDE.
PROJECTED_INDEPENDENCE = 90   # owner-independence assumed after a management layer
PROJECTED_SDE_GROWTH = 0.20   # SDE uplift assumed from scaling

# Local SQLite database path (cache + saved profiles/buyboxes/runs).
DB_PATH = os.getenv("MERJACK_DB_PATH", "merjack.db")
