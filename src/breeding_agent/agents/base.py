"""Shared interfaces for lightweight and future LLM-ready agents.

本文件定义 agents 层的统一接口，不负责具体业务逻辑。

核心作用：
1. AgentInput：统一描述 agent 的输入，包括 agent_name、context、prompt_template 和 parameters。
2. AgentOutput：统一描述 agent 的输出，包括 summary、evidence_used、warnings、limitations 和 structured_payload。
3. AgentResult：为未来 LLM 接入保留完整执行记录，包括输入、输出、fallback 状态和 raw_response。
4. BaseAgent：所有本地 agent 的抽象基类，要求子类实现 run_with_context()。
5. RuleBasedAgent：当前生产 fallback 使用的确定性规则 agent，明确 uses_llm=False、uses_external_api=False。
6. LLMReadyAgentMixin：只提供 prompt 构造接口，不调用任何 LLM SDK。

当前边界：这些接口使 agent 层具备 LLM-ready 形态，但当前业务流程仍以规则 agent 为主，不默认调用外部模型或外部 API。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentInput:
    """传给 agent 的标准结构化输入。

    context 通常来自 context_builder.py，里面包含 evidence、候选基因、文献结果、硬性约束和 warnings。
    prompt_template 与 parameters 主要为未来 LLM adapter 预留。
    """

    agent_name: str
    context: dict[str, Any]
    prompt_template: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentOutput:
    """所有规则 agent 和未来 LLM agent 共用的标准输出结构。

    CentralHost、LangGraph trace、manifest 和报告生成器都可以统一读取这些字段。
    limitations 用来写清楚当前输出不能越界，例如不能声称完成最终 KASP/CAPS。
    """

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
    """一次 agent 执行的完整记录。

    当前规则版 agent 多数直接返回 AgentOutput；该结构主要为未来记录 LLM 原始响应、fallback 状态和完整 provenance 预留。
    """

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
    """所有本地 agent 的抽象基类。

    子类必须实现 run_with_context(context)，即基于结构化上下文返回 AgentOutput。
    """

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
    """当前生产 fallback 使用的确定性规则 agent 标记类。

    通过 uses_llm=False 和 uses_external_api=False 明确项目边界。
    """

    uses_llm = False
    uses_external_api = False


class LLMReadyAgentMixin:
    """未来 LLM 接入预留的 prompt 构建 mixin。

    当前不会导入或调用 LLM SDK。

    Prompt-building hooks for future LLM integration.

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
