"""Base dataclasses for local LLM adapters."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    provider: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 1200
    timeout_seconds: int = 60
    chat_template_kwargs: dict[str, object] = field(default_factory=dict)
    enabled_agents: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LLMRequest:
    messages: list[dict[str, str]]
    model: str
    temperature: float
    max_tokens: int
    chat_template_kwargs: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    raw_response: dict[str, object]
