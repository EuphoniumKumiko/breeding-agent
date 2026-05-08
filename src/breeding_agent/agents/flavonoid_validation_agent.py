"""Rule-based downstream validation plan agent."""

from __future__ import annotations


class FlavonoidValidationAgent:
    """Create a validation plan for flavonoid marker candidates."""

    def run(self, candidate_rows: list[dict[str, str]]) -> dict[str, object]:
        target_genes = [
            row.get("gene_id", "unknown")
            for row in candidate_rows
            if row.get("gene_id")
        ]
        return {
            "validation_plan_text": self._render_validation_plan(target_genes),
            "target_genes": target_genes,
        }

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
