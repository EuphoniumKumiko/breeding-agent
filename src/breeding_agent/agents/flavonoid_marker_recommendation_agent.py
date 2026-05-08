"""Rule-based SNP/InDel/KASP/CAPS recommendation agent."""

from __future__ import annotations


class FlavonoidMarkerRecommendationAgent:
    """Recommend marker types from candidate evidence and variant status."""

    def run(self, candidate_rows: list[dict[str, str]]) -> dict[str, object]:
        recommendations_by_gene = {
            row.get("gene_id", "unknown"): self._recommend_for_gene(row)
            for row in candidate_rows
        }
        return {
            "recommendations_by_gene": recommendations_by_gene,
            "marker_recommendation_text": self._render_recommendations(
                candidate_rows,
                recommendations_by_gene,
            ),
        }

    def _recommend_for_gene(self, row: dict[str, str]) -> str:
        variant_evidence_status = row.get("variant_evidence_status", "")
        if variant_evidence_status == "preliminary_pass_variants_detected":
            return (
                "该基因候选区域已有真实 VCF PASS variant；可优先复核 PASS SNP "
                "的 KASP 转化潜力。KASP/CAPS 结果只是 preliminary screening，"
                "不是最终标记或酶切方案，仍需 flanking sequence、覆盖度和群体"
                "验证。"
            )
        if variant_evidence_status == "only_low_quality_variants_detected":
            return (
                "该基因候选区域仅检出 LowQual variant，不应优先用于 KASP/CAPS，"
                "需要先人工复核 coverage、quality 和 flanking sequence。"
            )
        if variant_evidence_status == "no_called_variant_in_current_mini_calling":
            return (
                "当前 mini calling 未检出 called variant，不能写成已有候选位点；"
                "建议扩大候选区域、增加样本或使用 WGS/GBS 数据继续检测。"
            )
        if variant_evidence_status == "variant_calling_output_missing":
            return (
                "未读取到 variant calling 输出，沿用 variant_status 结论；不能"
                "补写 SNP/InDel 坐标，需先运行候选区域 variant calling。"
            )

        variant_status = row.get("variant_status", "not_called")
        if variant_status == "not_called":
            return (
                "variant_status=not_called；当前没有最终 SNP/InDel 位点，不能写入"
                "具体位置。建议后续先做候选区域 SNP/InDel calling；获得高置信"
                "多态后，优先开发 SNP/InDel/KASP 标记；若变异改变限制性内切酶"
                "识别位点，再条件推荐 CAPS 或 dCAPS。"
            )

        return (
            "基于已 calling 的 SNP/InDel 候选位点，优先筛选高置信、与黄酮"
            "表型相关的 SNP/InDel 转化为 KASP；若满足酶切识别条件，再补充"
            "开发 CAPS 或 dCAPS。"
        )

    def _render_recommendations(
        self,
        candidate_rows: list[dict[str, str]],
        recommendations_by_gene: dict[str, str],
    ) -> str:
        lines = [
            "优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。",
            "",
            "- SNP: 作为候选基因及邻近调控区单碱基差异的优先标记来源。",
            "- InDel: 作为候选区域插入/缺失多态的补充标记来源。",
            "- KASP: 对高置信 SNP/InDel 优先转化，适合更大群体高通量分型。",
            "- CAPS/dCAPS: 仅当 SNP/InDel 改变或可设计限制性内切酶识别位点时条件开发。",
            "",
            "| gene_id | variant_status | 推荐说明 |",
            "| --- | --- | --- |",
        ]
        for row in candidate_rows:
            gene_id = row.get("gene_id", "unknown")
            lines.append(
            "| {gene_id} | {variant_status} | {recommendation} |".format(
                    gene_id=gene_id,
                    variant_status=row.get("variant_status", "not_called"),
                    recommendation=recommendations_by_gene.get(gene_id, ""),
                )
            )
        return "\n".join(lines)
