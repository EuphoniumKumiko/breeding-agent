"""OpenAI-compatible local chat completion adapter."""

from __future__ import annotations

import json
from urllib import request

from breeding_agent.llm.adapter_base import LLMConfig, LLMRequest, LLMResponse


class OpenAICompatibleAdapter:
    """Minimal OpenAI-compatible adapter using the Python standard library."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def complete(self, llm_request: LLMRequest) -> LLMResponse:
        payload = {
            "model": llm_request.model,
            "messages": llm_request.messages,
            "temperature": llm_request.temperature,
            "max_tokens": llm_request.max_tokens,
            "chat_template_kwargs": llm_request.chat_template_kwargs,
        }
        data = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            _chat_completions_url(self.config.base_url),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(  # nosec B310 - local, user-configured endpoint.
            http_request,
            timeout=self.config.timeout_seconds,
        ) as response:
            raw = json.loads(response.read().decode("utf-8"))
        content = _extract_content(raw)
        return LLMResponse(
            content=content,
            model=str(raw.get("model") or llm_request.model),
            raw_response=raw,
        )


def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _extract_content(raw: object) -> str:
    if not isinstance(raw, dict):
        return ""
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return str(content or "").strip()
