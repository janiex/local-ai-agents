"""Provider-agnostic LLM interface.

Every backend (local Ollama, external Claude API, ...) implements `stream`.
`complete` is derived from it so callers get both streaming and blocking use
for free. This abstraction is what lets the user pick "local LLM" or
"external LLM by API" at runtime.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterator, List

# A chat message: {"role": "user" | "assistant", "content": "..."}.
Message = Dict[str, str]


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
        """Yield response text incrementally."""
        raise NotImplementedError

    def complete(self, system: str, messages: List[Message]) -> str:
        """Blocking variant — collect the full streamed response."""
        return "".join(self.stream(system, messages))

    def health_check(self) -> str:
        """Return a human-readable status string ('' on success raises)."""
        return "ok"
