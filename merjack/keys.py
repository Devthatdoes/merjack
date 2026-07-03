"""API-key management: ask the user for a provider key once, persist it to ``.env``.

Single-user, local-first: the app prompts for whatever key the configured models
need, writes it into ``.env`` (which ``.gitignore`` excludes), and reuses it on
every later run. The prompt function is injectable so the same logic works from a
CLI (``getpass``) or the Streamlit UI (a password field) — see ``ensure_api_key``.

Reuses ``python-dotenv``'s ``set_key``/``get_key`` so we never clobber other vars.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Callable, Iterable, Optional

from dotenv import get_key, set_key

# Logical provider -> the env var that holds its key.
PROVIDER_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

DEFAULT_ENV_PATH = Path(os.getenv("MERJACK_ENV_PATH", ".env"))

PromptFunc = Callable[[str], str]


def env_var_for(provider: str) -> str:
    """The env var name that stores ``provider``'s key."""
    try:
        return PROVIDER_ENV[provider.lower()]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unknown provider {provider!r}; known: {list(PROVIDER_ENV)}") from exc


def provider_for_model(model_id: str) -> str:
    """Logical provider for a ``provider:model`` id (e.g. ``openrouter:...`` -> ``openrouter``)."""
    return model_id.split(":", 1)[0].lower()


def get_api_key(provider: str, env_path: Path = DEFAULT_ENV_PATH) -> Optional[str]:
    """Return the stored key for ``provider`` — process env first, then the ``.env`` file."""
    var = env_var_for(provider)
    val = os.getenv(var)
    if val:
        return val
    if Path(env_path).exists():
        return get_key(str(env_path), var) or None
    return None


def has_api_key(provider: str, env_path: Path = DEFAULT_ENV_PATH) -> bool:
    return bool(get_api_key(provider, env_path))


def save_api_key(provider: str, key: str, env_path: Path = DEFAULT_ENV_PATH) -> None:
    """Persist ``key`` to ``.env`` and make it live in this process immediately."""
    var = env_var_for(provider)
    path = Path(env_path)
    path.touch(exist_ok=True)  # set_key needs the file to exist
    set_key(str(path), var, key)
    os.environ[var] = key


def ensure_api_key(
    provider: str,
    prompt_func: Optional[PromptFunc] = None,
    env_path: Path = DEFAULT_ENV_PATH,
) -> str:
    """Return ``provider``'s key, prompting for and saving it if it isn't set yet.

    ``prompt_func(provider) -> str`` is how the key is collected when missing;
    defaults to a hidden ``getpass`` prompt. The Streamlit UI passes its own.
    """
    existing = get_api_key(provider, env_path)
    if existing:
        os.environ[env_var_for(provider)] = existing  # ensure it's live
        return existing

    if prompt_func is None:
        prompt_func = lambda p: getpass.getpass(f"Enter your {p} API key: ")  # noqa: E731

    key = prompt_func(provider).strip()
    if not key:
        raise ValueError(f"No API key provided for {provider!r}")
    save_api_key(provider, key, env_path)
    return key


def ensure_keys_for_models(
    model_ids: Iterable[str],
    prompt_func: Optional[PromptFunc] = None,
    env_path: Path = DEFAULT_ENV_PATH,
) -> None:
    """Ensure a key exists for every provider referenced by ``model_ids``.

    Native LangChain providers we don't track (anything outside ``PROVIDER_ENV``)
    are left to LangChain's own env handling.
    """
    providers = {provider_for_model(m) for m in model_ids}
    for provider in providers:
        if provider in PROVIDER_ENV:
            ensure_api_key(provider, prompt_func=prompt_func, env_path=env_path)


def _interactive_setup() -> None:
    """`python -m merjack.keys` — prompt for whatever keys the configured models need."""
    from .config import MODELS

    ensure_keys_for_models(MODELS.values())
    print("✅ API keys are set in", DEFAULT_ENV_PATH)


if __name__ == "__main__":  # pragma: no cover
    _interactive_setup()
