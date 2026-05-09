"""Rule-based downstream validation plan agent."""

from __future__ import annotations

from breeding_agent.agents.base import AgentOutput, LLMReadyAgentMixin, RuleBasedAgent
from breeding_agent.agents.prompt_templates import validation_agent_prompt


class FlavonoidValidationAgent(LLMReadyAgentMixin, RuleBasedAgent):
    """Create a validation plan for flavonoid marker candidates."""

    agent_name = "validation_agent"
    prompt_template = validation_agent_prompt

    def run(self, candidate_rows: list[dict[str, str]]) -> dict[str, object]:
        result = self._run_rule(candidate_rows)
        return {
            **result,
            "agent_output": self._agent_output(result).to_dict(),
        }

    def run_with_context(self, context: dict[str, object]) -> AgentOutput:
        candidate_rows = _as_rows(context.get("candidate_rows", []))
        result = self._run_rule(candidate_rows)
        return self._agent_output(result)

    def _run_rule(self, candidate_rows: list[dict[str, str]]) -> dict[str, object]:
        target_genes = [
            row.get("gene_id", "unknown")
            for row in candidate_rows
            if row.get("gene_id")
        ]
        return {
            "validation_plan_text": self._render_validation_plan(target_genes),
            "target_genes": target_genes,
        }

    def _agent_output(self, result: dict[str, object]) -> AgentOutput:
        target_genes = result.get("target_genes", [])
        n_genes = len(target_genes) if isinstance(target_genes, list) else 0
        return AgentOutput(
            agent_name=self.agent_name,
            summary=f"Generated validation plan for {n_genes} genes.",
            evidence_used=["candidate gene list", "marker recommendations"],
            warnings=[],
            limitations=[
                "Validation plan is a recommended workflow, not completed breeding validation.",
                "Population association remains required.",
            ],
            structured_payload=result,
        )

    def _render_validation_plan(self, target_genes: list[str]) -> str:
        gene_text = "、".join(target_genes) if target_genes else "候选基因"
        return "\n".join(
            [
                f"- 对 {gene_text} 及上下游候选区域进行 SNP/InDel calling，明确真实多态位点。",
                "- 对候选 SNP/InDel 进行 Sanger 验证，确认测序与 calling 结果一致。",
                "- 将高置信 SNP/InDel 转化为 KASP 标记，并在更大群体中开展 KASP 分型验证。",
                "- 当变异改变或可设计限制性内切酶识别位点时，开展 CAPS/dCAPS 条件验证。",
                "- 在更大群体中同步采集基因型和黄酮含量数据，进行标记-性状关联分析。",
                "- 对重点基因进行 qRT-PCR，验证表达差异方向与转录组统计结果一致。",
                "- 使用 LC-MS/MS 复核关键黄酮代谢物含量，连接基因型、表达和代谢表型。",
            ]
        )


def _as_rows(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]
