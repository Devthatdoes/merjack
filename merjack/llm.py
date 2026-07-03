"""Provider-agnostic model access.

The rest of the app never imports a provider SDK directly — it asks for a model by
*task* and gets a LangChain chat model. Swapping Claude for GPT/Gemini/open models
is a one-line change in ``.env`` (``MERJACK_MODEL_*``).

Two routing paths:
  * ``openrouter:<slug>``  -> ChatOpenAI pointed at OpenRouter's OpenAI-compatible API
    (one key, hundreds of models). The ``<slug>`` is an OpenRouter model id, e.g.
    ``openrouter:anthropic/claude-3.5-sonnet``.
  * ``provider:model``     -> LangChain's ``init_chat_model`` (anthropic, openai, ...).

``resolve_spec`` is pure (no SDK import) so the routing logic is unit-testable
without the ``agent`` extra installed. The actual client is built lazily.

Note: scoring uses ``with_structured_output``, so an OpenRouter model must support
tool/function calling (Claude and GPT models do).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from .config import MODELS

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class ModelSpec:
    kind: str                      # "openrouter" | "native"
    model: str                     # slug/id passed to the client
    provider: str                  # logical provider (key lookup)
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None


def resolve_spec(model_id: str) -> ModelSpec:
    """Parse a ``provider:model`` id into a routing spec. Pure / no imports."""
    if ":" not in model_id:
        raise ValueError(f"Model id {model_id!r} must be in 'provider:model' form")
    provider, slug = model_id.split(":", 1)
    provider = provider.lower()
    if provider == "openrouter":
        return ModelSpec(
            kind="openrouter",
            model=slug,
            provider="openrouter",
            base_url=OPENROUTER_BASE_URL,
            api_key_env="OPENROUTER_API_KEY",
        )
    return ModelSpec(kind="native", model=model_id, provider=provider)


@lru_cache(maxsize=None)
def build_model(model_id: str, temperature: float = 0.0):
    """Build a LangChain chat model from an explicit ``provider:model`` id.

    Used directly by the UI's model switcher; ``get_model`` wraps it per task.
    """
    spec = resolve_spec(model_id)

    if spec.kind == "openrouter":
        from langchain_openai import ChatOpenAI  # lazy: requires `agent` extra

        api_key = os.getenv(spec.api_key_env or "OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Run `python -m merjack.keys` or call "
                "merjack.keys.ensure_api_key('openrouter') to enter and save it."
            )
        return ChatOpenAI(
            model=spec.model,
            base_url=spec.base_url,
            api_key=api_key,
            temperature=temperature,
        )

    from langchain.chat_models import init_chat_model  # lazy: requires `agent` extra

    return init_chat_model(model_id, temperature=temperature)


def get_model(task: str = "scoring", temperature: float = 0.0):
    """Return a LangChain chat model for a task (``scoring`` | ``explain`` | ``sourcing``)."""
    model_id = MODELS.get(task)
    if model_id is None:
        raise ValueError(f"Unknown model task {task!r}; expected one of {list(MODELS)}")
    return build_model(model_id, temperature=temperature)
