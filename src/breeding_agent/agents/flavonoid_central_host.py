"""DeepRare-like lightweight central host for flavonoid marker aggregation.

本文件实现规则版 FlavonoidCentralHost，是非 LangGraph 版的 agent 调度中心。

它按固定顺序执行：evidence 聚合 → agent_context 构建 → LiteratureAgent → MarkerRecommendationAgent → ValidationAgent → ReviewerAgent → FinalQAAgent → 报告文本组装。

边界：不直接做 RNA-seq/代谢组/variant calling，不调用 LLM，不调用外部 API，不生成最终 KASP/CAPS 设计。"""

from __future__ import annotations

from pathlib import Path

from breeding_agent.agents.context_builder import build_flavonoid_agent_context
from breeding_agent.agents.flavonoid_final_qa_agent import FlavonoidFinalQAAgent
from breeding_agent.agents.flavonoid_literature_agent import (
    FlavonoidLiteratureAgent,
)
from breeding_agent.agents.flavonoid_marker_recommendation_agent import (
    FlavonoidMarkerRecommendationAgent,
)
from breeding_agent.agents.flavonoid_reviewer_agent import FlavonoidReviewerAgent
from breeding_agent.agents.flavonoid_validation_agent import (
    FlavonoidValidationAgent,
)
from breeding_agent.integration.flavonoid_marker_aggregator import (
    REQUIRED_GENE_IDS,
    aggregate_flavonoid_marker_candidates,
)
from breeding_agent.reports.flavonoid_marker_report import (
    render_flavonoid_marker_report,
)


# CentralHost 是传统串行调度器：负责协调多个规则 agent。
class FlavonoidCentralHost:
    """Coordinate rule-based flavonoid marker agents without external calls."""

    def __init__(
        self,
        *,
        evidence_dir: Path,
        outdir: Path,
        target_genes: list[str] | None = None,
        variant_calling_dir: Path | None = None,
    ) -> None:
        self.evidence_dir = evidence_dir
        self.outdir = outdir
        self.target_genes = target_genes or list(REQUIRED_GENE_IDS)
        self.variant_calling_dir = variant_calling_dir

    def run(self) -> dict[str, object]:
        """顺序执行规则版黄酮候选标记推荐流程，并返回完整 agent_result。"""
        # 1. 聚合多组学 evidence，生成 candidate_rows 和 candidate_file。
        aggregation_result = aggregate_flavonoid_marker_candidates(
            evidence_dir=self.evidence_dir,
            outdir=self.outdir,
            variant_calling_dir=self.variant_calling_dir,
        )
        candidate_rows = aggregation_result.candidate_rows
        warnings = list(aggregation_result.warnings)
        # 2. 构建所有 agent 共用的结构化上下文。
        agent_context = build_flavonoid_agent_context(
            evidence_dir=self.evidence_dir,
            candidate_rows=candidate_rows,
            variant_calling_dir=aggregation_result.variant_calling_dir,
            variant_evidence_rows=aggregation_result.variant_evidence_rows,
            warnings=warnings,
        )

        if self.target_genes != REQUIRED_GENE_IDS:
            warnings.append(
                "CentralHost received non-default target_genes; current aggregator "
                "keeps the fixed high-priority gene set."
            )
            agent_context["warnings"] = warnings

        literature_agent = FlavonoidLiteratureAgent(self.evidence_dir)
        marker_agent = FlavonoidMarkerRecommendationAgent()
        validation_agent = FlavonoidValidationAgent()
        reviewer_agent = FlavonoidReviewerAgent()
        final_qa_agent = FlavonoidFinalQAAgent()

        # 3. 文献分析：生成 DOI 受控的文献综述和 query plan。
        literature_output = literature_agent.run_with_context(agent_context)
        literature_result = literature_output.structured_payload
        # 4. 标记推荐：生成 SNP/InDel/KASP/CAPS 候选开发建议。
        marker_output = marker_agent.run_with_context(agent_context)
        marker_result = marker_output.structured_payload
        # 5. 验证方案：生成 Sanger、KASP、CAPS、qRT-PCR、LC-MS/MS 和群体验证建议。
        validation_output = validation_agent.run_with_context(agent_context)
        validation_result = validation_output.structured_payload
        warnings.extend(literature_result.get("warnings", []))

        base_report_text = render_flavonoid_marker_report(
            evidence_dir=self.evidence_dir,
            candidate_rows=candidate_rows,
            literature_rows=literature_result["literature_rows"],
            literature_analysis=literature_result.get("literature_analysis", {}),
            warnings=warnings,
            literature_review_text=str(literature_result["literature_review_text"]),
            marker_recommendation_text=str(
                marker_result["marker_recommendation_text"]
            ),
            validation_plan_text=str(validation_result["validation_plan_text"]),
            variant_calling_dir=aggregation_result.variant_calling_dir,
        )
        reviewer_context = {
            **agent_context,
            "literature_review_text": str(literature_result["literature_review_text"]),
            "literature_analysis": literature_result.get("literature_analysis", {}),
            "allowed_report_dois": literature_result.get("allowed_report_dois", []),
            "marker_recommendation_text": str(
                marker_result["marker_recommendation_text"]
            ),
            "validation_plan_text": str(validation_result["validation_plan_text"]),
            "report_text": base_report_text,
        }
        # 6. 审阅报告草稿，检查缺失项和过度声称。
        reviewer_output = reviewer_agent.run_with_context(reviewer_context)
        reviewer_result = reviewer_output.structured_payload
        agent_outputs = [
            literature_output.to_dict(),
            marker_output.to_dict(),
            validation_output.to_dict(),
            reviewer_output.to_dict(),
        ]
        agent_context.update(
            {
                "literature_review_text": str(
                    literature_result["literature_review_text"]
                ),
                "literature_analysis": literature_result.get("literature_analysis", {}),
                "allowed_report_dois": literature_result.get("allowed_report_dois", []),
                "marker_recommendation_text": str(
                    marker_result["marker_recommendation_text"]
                ),
                "validation_plan_text": str(validation_result["validation_plan_text"]),
                "reviewer_notes": str(reviewer_result["reviewer_notes"]),
            }
        )
        report_text_without_qa = render_flavonoid_marker_report(
            evidence_dir=self.evidence_dir,
            candidate_rows=candidate_rows,
            literature_rows=literature_result["literature_rows"],
            literature_analysis=literature_result.get("literature_analysis", {}),
            warnings=warnings,
            literature_review_text=str(literature_result["literature_review_text"]),
            marker_recommendation_text=str(
                marker_result["marker_recommendation_text"]
            ),
            validation_plan_text=str(validation_result["validation_plan_text"]),
            reviewer_notes=str(reviewer_result["reviewer_notes"]),
            variant_calling_dir=aggregation_result.variant_calling_dir,
        )
        # 7. 对不含 QA section 的报告先做一次最终 QA。
        qa_output = final_qa_agent.run_with_context(
            {**agent_context, "report_text": report_text_without_qa}
        )
        qa_result = qa_output.structured_payload
        final_report_text = render_flavonoid_marker_report(
            evidence_dir=self.evidence_dir,
            candidate_rows=candidate_rows,
            literature_rows=literature_result["literature_rows"],
            literature_analysis=literature_result.get("literature_analysis", {}),
            warnings=warnings,
            literature_review_text=str(literature_result["literature_review_text"]),
            marker_recommendation_text=str(
                marker_result["marker_recommendation_text"]
            ),
            validation_plan_text=str(validation_result["validation_plan_text"]),
            reviewer_notes=str(reviewer_result["reviewer_notes"]),
            qa_result=qa_result,
            variant_calling_dir=aggregation_result.variant_calling_dir,
        )
        final_qa_output = final_qa_agent.run_with_context(
            {**agent_context, "report_text": final_report_text}
        )
        qa_result = final_qa_output.structured_payload
        agent_outputs.extend([qa_output.to_dict(), final_qa_output.to_dict()])

        return {
            "candidate_file": aggregation_result.candidate_file,
            "candidate_rows": candidate_rows,
            "literature_rows": literature_result["literature_rows"],
            "literature_review_text": literature_result["literature_review_text"],
            "literature_analysis": literature_result.get("literature_analysis", {}),
            "marker_recommendations": marker_result["recommendations_by_gene"],
            "marker_recommendation_text": marker_result[
                "marker_recommendation_text"
            ],
            "validation_plan_text": validation_result["validation_plan_text"],
            "reviewer_notes": reviewer_result["reviewer_notes"],
            "reviewer_result": reviewer_result,
            "qa_result": qa_result,
            "report_text": final_report_text,
            "warnings": warnings,
            "agent_context": agent_context,
            "agent_outputs": agent_outputs,
            "variant_calling_dir": (
                str(aggregation_result.variant_calling_dir)
                if aggregation_result.variant_calling_dir
                else None
            ),
            "agent_layer": {
                "mode": "rule_based_deeprare_like_lightweight",
                "interface": "llm_ready_rule_based_fallback",
                "uses_llm": False,
                "uses_external_api": False,
                "uses_langgraph": False,
                "uses_deep_agents": False,
                "prompt_templates_available": True,
                "context_builder": "build_flavonoid_agent_context",
                "target_genes": self.target_genes,
            },
        }
