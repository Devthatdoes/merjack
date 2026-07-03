"""API-key management: persistence + prompt-only-when-missing. No network."""

import pytest

from merjack import keys


def test_provider_for_model():
    assert keys.provider_for_model("openrouter:anthropic/claude-3.5-sonnet") == "openrouter"
    assert keys.provider_for_model("anthropic:claude-opus-4-8") == "anthropic"


def test_env_var_for_known_and_unknown():
    assert keys.env_var_for("openrouter") == "OPENROUTER_API_KEY"
    with pytest.raises(ValueError):
        keys.env_var_for("nope")


def test_save_and_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env = tmp_path / ".env"
    keys.save_api_key("openrouter", "sk-or-test-123", env_path=env)
    assert env.exists()
    # Lives in the process env immediately...
    assert keys.get_api_key("openrouter", env_path=env) == "sk-or-test-123"
    # ...and persists in the file once the process env is cleared.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert keys.get_api_key("openrouter", env_path=env) == "sk-or-test-123"


def test_ensure_prompts_only_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = tmp_path / ".env"
    calls = []

    def prompt(provider):
        calls.append(provider)
        return "  sk-ant-xyz  "  # surrounding whitespace should be stripped

    key = keys.ensure_api_key("anthropic", prompt_func=prompt, env_path=env)
    assert key == "sk-ant-xyz"
    assert calls == ["anthropic"]

    # Now that it's saved, a second call must NOT prompt.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # force file-read path

    def boom(provider):
        raise AssertionError("should not prompt when key already exists")

    assert keys.ensure_api_key("anthropic", prompt_func=boom, env_path=env) == "sk-ant-xyz"


def test_ensure_rejects_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env = tmp_path / ".env"
    with pytest.raises(ValueError):
        keys.ensure_api_key("openai", prompt_func=lambda p: "   ", env_path=env)


def test_ensure_keys_for_models_skips_untracked(tmp_path, monkeypatch):
    # A native provider we don't manage (e.g. "ollama") should be left alone.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env = tmp_path / ".env"
    keys.ensure_keys_for_models(
        ["openrouter:anthropic/claude-3.5-haiku", "ollama:llama3"],
        prompt_func=lambda p: "sk-or-test",
        env_path=env,
    )
    assert keys.get_api_key("openrouter", env_path=env) == "sk-or-test"
