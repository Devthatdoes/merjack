"""Model-id routing (OpenRouter vs native). Pure — no SDK import, no network."""

import pytest

from merjack.llm import OPENROUTER_BASE_URL, resolve_spec


def test_resolve_openrouter():
    spec = resolve_spec("openrouter:anthropic/claude-3.5-sonnet")
    assert spec.kind == "openrouter"
    assert spec.model == "anthropic/claude-3.5-sonnet"  # slug only, prefix stripped
    assert spec.provider == "openrouter"
    assert spec.base_url == OPENROUTER_BASE_URL
    assert spec.api_key_env == "OPENROUTER_API_KEY"


def test_resolve_native():
    spec = resolve_spec("anthropic:claude-opus-4-8")
    assert spec.kind == "native"
    assert spec.model == "anthropic:claude-opus-4-8"  # full id handed to init_chat_model
    assert spec.provider == "anthropic"
    assert spec.base_url is None


def test_resolve_requires_provider_prefix():
    with pytest.raises(ValueError):
        resolve_spec("bare-model-name")
