from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMRequest:
    prompt: str
    temperature: float = 0.0


@dataclass
class LLMResponse:
    enabled: bool
    raw: dict[str, Any] | None = None


def request_llm_analysis(_: LLMRequest) -> LLMResponse:
    """Placeholder for stage 2. Returns disabled flag."""
    return LLMResponse(enabled=False, raw=None)
