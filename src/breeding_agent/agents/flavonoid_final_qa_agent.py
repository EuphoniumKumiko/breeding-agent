"""Final QA agent wrapping the existing flavonoid report QA rules."""

from __future__ import annotations

from breeding_agent.agents.base import AgentOutput, LLMReadyAgentMixin, RuleBasedAgent
from breeding_agent.agents.prompt_templates import final_qa_agent_prompt
from breeding_agent.integration.flavonoid_marker_qa import (
    check_flavonoid_marker_report,
)


class FlavonoidFinalQAAgent(LLMReadyAgentMixin, RuleBasedAgent):
    """Run the canonical rule-based QA without duplicating QA logic."""

    agent_name = "final_qa_agent"
    prompt_template = final_qa_agent_prompt

    def run(self, report_text: str) -> dict[str, object]:
        result = check_flavonoid_marker_report(report_text)
        return {
            **result,
            "agent_output": self._agent_output(result).to_dict(),
        }

    def run_with_context(self, context: dict[str, object]) -> AgentOutput:
        result = check_flavonoid_marker_report(str(context.get("report_text", "")))
        return self._agent_output(result)

    def _agent_output(self, result: dict[str, object]) -> AgentOutput:
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
