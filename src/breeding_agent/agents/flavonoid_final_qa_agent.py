"""Final QA agent wrapping the existing flavonoid report QA rules.

本文件实现最终 QA agent。它不重新实现 QA 规则，而是包装 integration/flavonoid_marker_qa.py 中的 check_flavonoid_marker_report()。

职责：检查最终报告是否满足硬性要求，包括固定目标基因、统计值、DOI、SNP/InDel/KASP/CAPS、群体验证语言，以及是否避免伪造 DOI/变异位点和过度声称最终标记开发。

边界：该 agent 是规则版 QA，不调用 LLM，不重新推导 evidence。"""

from __future__ import annotations

from breeding_agent.agents.base import AgentOutput, LLMReadyAgentMixin, RuleBasedAgent
from breeding_agent.agents.prompt_templates import final_qa_agent_prompt
from breeding_agent.integration.flavonoid_marker_qa import (
    check_flavonoid_marker_report,
)


class FlavonoidFinalQAAgent(LLMReadyAgentMixin, RuleBasedAgent):
    """运行统一的规则 QA，并返回标准 AgentOutput。

    复用 check_flavonoid_marker_report()，避免 CentralHost、LangGraph 和旧流程各自维护一套 QA 逻辑。
    """

    agent_name = "final_qa_agent"
    prompt_template = final_qa_agent_prompt

    def run(self, report_text: str) -> dict[str, object]:
        """兼容旧调用方式：直接传入报告文本并返回 QA dict。"""
        result = check_flavonoid_marker_report(report_text)
        return {
            **result,
            "agent_output": self._agent_output(result).to_dict(),
        }

    def run_with_context(self, context: dict[str, object]) -> AgentOutput:
        """从 context 读取 report_text、allowed_report_dois 和 literature_analysis 后执行 QA。"""
        # Final QA works from the rendered report text and the allowed DOI set;
        # it does not re-derive the evidence or call an LLM.
        allowed_dois = context.get("allowed_report_dois")
        result = check_flavonoid_marker_report(
            str(context.get("report_text", "")),
            allowed_dois=(
                [str(item) for item in allowed_dois]
                if isinstance(allowed_dois, list)
                else None
            ),
            literature_analysis=(
                context.get("literature_analysis")
                if isinstance(context.get("literature_analysis"), dict)
                else None
            ),
        )
        return self._agent_output(result)

    def _agent_output(self, result: dict[str, object]) -> AgentOutput:
        """把 QA 结果包装为标准 AgentOutput，便于 trace、manifest 和 UI 展示。"""
        missing_items = result.get("missing_items", [])
        return AgentOutput(
            agent_name=self.agent_name,
            summary=f"Final QA passed={result.get('passed')}.",
            evidence_used=["final_report_text"],
            warnings=[
                str(item) for item in missing_items
            ] if isinstance(missing_items, list) else [],
            limitations=[
                "QA uses deterministic text checks and does not call an LLM.",
            ],
            structured_payload=result,
        )
