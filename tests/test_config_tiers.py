"""Model-tier resolution: presets, env overrides, live-sourcing flag. Pure, no I/O."""

import pytest

from merjack.config import (
    DEFAULT_TIER,
    TASKS,
    TIERS,
    resolve_live_sourcing,
    resolve_models,
    resolve_tier,
)


def test_default_tier_is_free():
    assert resolve_tier(env={}) == "free"
    assert DEFAULT_TIER == "free"


def test_tier_from_env_and_case_insensitive():
    assert resolve_tier(env={"MERJACK_TIER": "PAID"}) == "paid"
    assert resolve_tier(env={"MERJACK_TIER": " free "}) == "free"


def test_unknown_tier_raises():
    with pytest.raises(ValueError):
        resolve_tier(env={"MERJACK_TIER": "platinum"})


def test_free_tier_uses_gpt_oss_via_openrouter():
    m = resolve_models("free", env={})
    assert set(m) == set(TASKS)
    assert m["scoring"] == "openrouter:openai/gpt-oss-20b:free"
    assert all(v.startswith("openrouter:") for v in m.values())


def test_paid_tier_uses_claude_direct():
    m = resolve_models("paid", env={})
    assert m["scoring"].startswith("anthropic:")
    assert m["explain"] == "anthropic:claude-opus-4-8"


def test_per_task_env_override_wins():
    env = {"MERJACK_MODEL_SCORING": "anthropic:claude-haiku-4-5-20251001"}
    m = resolve_models("free", env=env)
    assert m["scoring"] == "anthropic:claude-haiku-4-5-20251001"   # overridden
    assert m["explain"] == TIERS["free"]["models"]["explain"]       # untouched -> preset


def test_live_sourcing_defaults_per_tier():
    assert resolve_live_sourcing("free", env={}) is False
    assert resolve_live_sourcing("paid", env={}) is True


def test_live_sourcing_env_override():
    assert resolve_live_sourcing("free", env={"MERJACK_LIVE_SOURCING": "true"}) is True
    assert resolve_live_sourcing("paid", env={"MERJACK_LIVE_SOURCING": "0"}) is False
