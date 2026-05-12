"""Rule-based downstream validation plan agent.

本文件实现验证方案 agent。它不执行实验验证，而是根据 candidate_rows 生成“后续应该如何验证”的路线。

验证建议覆盖：候选区域 SNP/InDel calling、Sanger 验证、KASP 分型、CAPS/dCAPS 条件验证、更大群体基因型-黄酮含量关联、qRT-PCR 和 LC-MS/MS。

边界：这里输出的是 recommended workflow，不是已完成的群体验证、湿实验验证或最终育种验证。"""

from __future__ import annotations

from breeding_agent.agents.base import AgentOutput, LLMReadyAgentMixin, RuleBasedAgent
from breeding_agent.agents.prompt_templates import validation_agent_prompt


class FlavonoidValidationAgent(LLMReadyAgentMixin, RuleBasedAgent):
    """为黄酮候选标记生成下游验证方案的规则 agent。"""

    agent_name = "validation_agent"
    prompt_template = validation_agent_prompt

    def run(self, candidate_rows: list[dict[str, str]]) -> dict[str, object]:
        """兼容旧调用方式：直接接收候选行并返回 dict。"""
        result = self._run_rule(candidate_rows)
        return {
            **result,
            "agent_output": self._agent_output(result).to_dict(),
        }

    def run_with_context(self, context: dict[str, object]) -> AgentOutput:
        """从 context 中读取 candidate_rows 并生成验证方案。"""
        candidate_rows = _as_rows(context.get("candidate_rows", []))
        result = self._run_rule(candidate_rows)
        return self._agent_output(result)

    def _run_rule(self, candidate_rows: list[dict[str, str]]) -> dict[str, object]:
        """提取目标基因列表，并生成 validation_plan_text。"""
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
        """渲染 Markdown 风格的验证建议文本。"""
        # The validation plan is downstream guidance only; it summarizes what
        # should happen after candidate calling and before breeding decisions.
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
