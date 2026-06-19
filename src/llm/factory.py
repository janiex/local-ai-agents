"""Build an LLMProvider from settings or an explicit choice."""
from __future__ import annotations

from typing import List, Optional

from ..config import settings
from .base import LLMProvider

AVAILABLE = ["ollama", "anthropic"]


def available_providers() -> List[str]:
    return list(AVAILABLE)


def get_provider(
    provider: Optional[str] = None,
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMProvider:
    name = (provider or settings.llm_provider).strip().lower()

    if name == "ollama":
        from .ollama_provider import OllamaProvider

        return OllamaProvider(settings.ollama_host, model or settings.ollama_model)

    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        # Precedence: explicit arg (e.g. typed into the UI) > .env value.
        return AnthropicProvider(
            api_key or settings.anthropic_api_key,
            model or settings.anthropic_model,
        )

    raise ValueError(f"Unknown LLM provider: {name!r}. Choose one of {AVAILABLE}.")
