"""Execution helpers for optional local LLM reviewer enhancement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from breeding_agent.llm.adapter_base import LLMConfig, LLMRequest
from breeding_agent.llm.openai_compatible_adapter import OpenAICompatibleAdapter
from breeding_agent.llm.output_guard import GuardResult, guard_reviewer_output


@dataclass(frozen=True)
class LLMReviewerResult:
    """Outcome of the optional ReviewerAgent LLM pass."""

    llm_reviewer_enabled: bool
    llm_used: bool
    fallback_used: bool
    model: str
    guard_passed: bool
    fallback_reason: str
    content: str = ""
    guard_reasons: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "llm_reviewer_enabled": self.llm_reviewer_enabled,
            "llm_used": self.llm_used,
            "fallback_used": self.fallback_used,
            "model": self.model,
            "guard_passed": self.guard_passed,
            "fallback_reason": self.fallback_reason,
            "guard_reasons": list(self.guard_reasons or []),
        }


def load_llm_config(path: str | Path) -> LLMConfig:
    """Load a small YAML-like local LLM config without adding dependencies."""

    config_path = Path(path).expanduser()
    data = _parse_simple_yaml(config_path.read_text(encoding="utf-8"))
    max_tokens = data.get("max_tokens", data.get("max_output_tokens", 1200))
    return LLMConfig(
        enabled=bool(data.get("enabled", False)),
        provider=str(data.get("provider", "openai_compatible")),
        base_url=str(data.get("base_url", "")),
        model=str(data.get("model", "")),
        temperature=float(data.get("temperature", 0.0)),
        max_tokens=int(max_tokens),
        timeout_seconds=int(data.get("timeout_seconds", 60)),
        chat_template_kwargs=_as_dict(data.get("chat_template_kwargs", {})),
        enabled_agents=[str(item) for item in _as_list(data.get("enabled_agents", []))],
    )


def run_llm_reviewer(
    *,
    context: dict[str, object],
    llm_config_path: str | Path | None,
    rule_reviewer_notes: str,
    enabled: bool,
) -> LLMReviewerResult:
    """Run the optional local LLM reviewer and guard its output.

    The LLM is advisory only. Any request failure, empty content, or guard
    failure falls back to the deterministic ReviewerAgent output.
    """

    if not enabled:
        return LLMReviewerResult(
            llm_reviewer_enabled=False,
            llm_used=False,
            fallback_used=True,
            model="",
            guard_passed=False,
            fallback_reason="llm_reviewer_disabled",
        )
    if not llm_config_path:
        return _fallback("missing_llm_config", model="", enabled=True)

    try:
        config = load_llm_config(llm_config_path)
    except Exception as exc:  # noqa: BLE001 - config errors must not break workflow
        return _fallback(f"llm_config_error: {exc}", model="", enabled=True)

    if not config.enabled:
        return _fallback("llm_config_disabled", model=config.model, enabled=True)
    if config.provider != "openai_compatible":
        return _fallback(
            f"unsupported_provider: {config.provider}",
            model=config.model,
            enabled=True,
        )
    if "reviewer_agent" not in config.enabled_agents:
        return _fallback(
            "reviewer_agent_not_enabled_in_config",
            model=config.model,
            enabled=True,
        )
    if not config.base_url or not config.model:
        return _fallback("missing_base_url_or_model", model=config.model, enabled=True)

    chat_template_kwargs = dict(config.chat_template_kwargs)
    chat_template_kwargs.setdefault("enable_thinking", False)
    request = LLMRequest(
        messages=_build_reviewer_messages(context, rule_reviewer_notes),
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        chat_template_kwargs=chat_template_kwargs,
    )
    try:
        response = OpenAICompatibleAdapter(config).complete(request)
    except Exception as exc:  # noqa: BLE001 - local model outages must fallback
        return _fallback(f"llm_request_failed: {exc}", model=config.model, enabled=True)

    content = response.content.strip()
    guard = guard_reviewer_output(content=content, context=context)
    if not content:
        return _fallback("empty_final_content", model=config.model, enabled=True, guard=guard)
    if not guard.passed:
        return _fallback(
            "guard_failed: " + "; ".join(guard.reasons),
            model=config.model,
            enabled=True,
            guard=guard,
        )
    return LLMReviewerResult(
        llm_reviewer_enabled=True,
        llm_used=True,
        fallback_used=False,
        model=config.model,
        guard_passed=True,
        fallback_reason="",
        content=content,
        guard_reasons=[],
    )


def _fallback(
    reason: str,
    *,
    model: str,
    enabled: bool,
    guard: GuardResult | None = None,
) -> LLMReviewerResult:
    return LLMReviewerResult(
        llm_reviewer_enabled=enabled,
        llm_used=False,
        fallback_used=True,
        model=model,
        guard_passed=bool(guard.passed) if guard else False,
        fallback_reason=reason,
        guard_reasons=list(guard.reasons) if guard else [],
    )


def _build_reviewer_messages(
    context: dict[str, object],
    rule_reviewer_notes: str,
) -> list[dict[str, str]]:
    report_text = str(context.get("report_text", ""))
    candidate_rows = context.get("candidate_rows", [])
    literature_text = str(context.get("literature_review_text", ""))
    marker_text = str(context.get("marker_recommendation_text", ""))
    validation_text = str(context.get("validation_plan_text", ""))
    system = (
        "You are a reviewer for a foxtail millet flavonoid marker recommendation "
        "workflow. Only review and improve cautionary notes. Do not create new "
        "SNP/InDel/KASP/CAPS conclusions, do not fabricate DOI values, and do "
        "not fabricate variant coordinates. LowQual variants must not be "
        "prioritized. Preliminary KASP/CAPS screening is not a final marker, "
        "primer, or enzyme-cutting plan. You must preserve that current RNA-seq "
        "candidate-region calling does not replace WGS/GBS population variant "
        "calling. Return concise reviewer notes in Chinese."
    )
    user = (
        "Rule-based ReviewerAgent notes:\n"
        f"{rule_reviewer_notes}\n\n"
        "Candidate rows:\n"
        f"{candidate_rows}\n\n"
        "Literature review text:\n"
        f"{literature_text}\n\n"
        "Marker recommendation text:\n"
        f"{marker_text}\n\n"
        "Validation plan text:\n"
        f"{validation_text}\n\n"
        "Draft report:\n"
        f"{report_text}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _parse_simple_yaml(text: str) -> dict[str, object]:
    data: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")) and current_key:
            stripped = raw_line.strip()
            if stripped.startswith("- "):
                current = data.get(current_key)
                if not isinstance(current, list):
                    current = []
                    data[current_key] = current
                current.append(_parse_scalar(stripped[2:].strip()))
                continue
            if ":" in stripped:
                current = data.setdefault(current_key, {})
                if isinstance(current, dict):
                    key, value = stripped.split(":", 1)
                    current[key.strip()] = _parse_scalar(value.strip())
                continue
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        current_key = key.strip()
        if value.strip():
            data[current_key] = _parse_scalar(value.strip())
        else:
            data[current_key] = {}
    return data


def _parse_scalar(value: str) -> object:
    text = value.strip().strip("\"'")
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", ""}:
        return None
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []
