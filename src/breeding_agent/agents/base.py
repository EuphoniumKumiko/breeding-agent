"""Shared interfaces for lightweight and future LLM-ready agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentInput:
    """Structured input passed to an agent."""

    agent_name: str
    context: dict[str, Any]
    prompt_template: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentOutput:
    """Structured output shared by rule-based and future LLM agents."""

    agent_name: str
    summary: str
    evidence_used: list[str]
    warnings: list[str]
    limitations: list[str]
    structured_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "summary": self.summary,
            "evidence_used": list(self.evidence_used),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "structured_payload": dict(self.structured_payload),
        }


@dataclass(frozen=True)
class AgentResult:
    """Execution result with input, output, and provenance flags."""

    agent_input: AgentInput
    agent_output: AgentOutput
    used_fallback: bool = True
    llm_enabled: bool = False
    raw_response: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_input": {
                "agent_name": self.agent_input.agent_name,
                "context": self.agent_input.context,
                "prompt_template": self.agent_input.prompt_template,
                "parameters": self.agent_input.parameters,
            },
            "agent_output": self.agent_output.to_dict(),
            "used_fallback": self.used_fallback,
            "llm_enabled": self.llm_enabled,
            "raw_response": self.raw_response,
        }


class BaseAgent(ABC):
    """Base class for all local agents."""

    agent_name = "base_agent"
    prompt_template = ""

    def build_agent_input(
        self,
        context: dict[str, Any],
        *,
        parameters: dict[str, Any] | None = None,
    ) -> AgentInput:
        return AgentInput(
            agent_name=self.agent_name,
            context=context,
            prompt_template=self.prompt_template,
            parameters=parameters or {},
        )

    @abstractmethod
    def run_with_context(self, context: dict[str, Any]) -> AgentOutput:
        """Run the agent against a structured context."""


class RuleBasedAgent(BaseAgent):
    """Marker class for deterministic agents used as the current fallback."""

    uses_llm = False
    uses_external_api = False


class LLMReadyAgentMixin:
    """Prompt-building hooks for future LLM integration.

    This mixin intentionally does not import or call any LLM SDK. Subclasses can
    use `build_prompt()` for inspection and future adapters can implement the
    actual model call outside this repository boundary.
    """

    prompt_template = ""

    def build_prompt(self, agent_input: AgentInput) -> str:
        return self.prompt_template.format(
            context=agent_input.context,
            parameters=agent_input.parameters,
        )

    def invoke_llm(self, agent_input: AgentInput) -> str | None:
        del agent_input
        return None
