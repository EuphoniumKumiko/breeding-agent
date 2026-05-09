"""Rule-based reviewer for flavonoid marker aggregation outputs."""

from __future__ import annotations

import re

from breeding_agent.agents.base import AgentOutput, LLMReadyAgentMixin, RuleBasedAgent
from breeding_agent.agents.prompt_templates import reviewer_agent_prompt


REQUIRED_STAT_COLUMNS = ["baseMean", "log2FC", "pvalue", "padj"]
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s|)]+", re.IGNORECASE)
POSITION_RE = re.compile(
    r"(?i)(?:chr\w+|scaffold\w+|contig\w+|si\d+\w*)[:：]\d+|\bposition=\d+"
)


class FlavonoidReviewerAgent(LLMReadyAgentMixin, RuleBasedAgent):
    """Check for common over-claiming and evidence omissions."""

    agent_name = "reviewer_agent"
    prompt_template = reviewer_agent_prompt

    def run(
        self,
        *,
        candidate_rows: list[dict[str, str]],
        literature_review_text: str,
        marker_recommendation_text: str,
        validation_plan_text: str,
        report_text: str,
    ) -> dict[str, object]:
        result = self._run_rule(
            candidate_rows=candidate_rows,
            literature_review_text=literature_review_text,
            marker_recommendation_text=marker_recommendation_text,
            validation_plan_text=validation_plan_text,
            report_text=report_text,
        )
        return {
            **result,
            "agent_output": self._agent_output(result).to_dict(),
        }

    def run_with_context(self, context: dict[str, object]) -> AgentOutput:
        result = self._run_rule(
            candidate_rows=_as_rows(context.get("candidate_rows", [])),
            literature_review_text=str(context.get("literature_review_text", "")),
            marker_recommendation_text=str(
                context.get("marker_recommendation_text", "")
            ),
            validation_plan_text=str(context.get("validation_plan_text", "")),
            report_text=str(context.get("report_text", "")),
        )
        return self._agent_output(result)

    def add_llm_review(
        self,
        output: AgentOutput,
        *,
        llm_review_text: str,
        llm_metadata: dict[str, object],
    ) -> AgentOutput:
        """Attach guarded LLM reviewer notes while preserving rule output."""

        payload = dict(output.structured_payload)
        rule_notes = str(payload.get("reviewer_notes", ""))
        payload["rule_reviewer_notes"] = rule_notes
        payload["llm_reviewer"] = dict(llm_metadata)
        if llm_review_text.strip():
            payload["reviewer_notes"] = (
                f"{rule_notes}\n\n"
                "LLM Reviewer 审阅增强（仅作审阅提示，不生成新的 SNP/InDel/KASP/CAPS 结论）：\n"
                f"{llm_review_text.strip()}"
            )
        return self._agent_output(payload)

    def _run_rule(
        self,
        *,
        candidate_rows: list[dict[str, str]],
        literature_review_text: str,
        marker_recommendation_text: str,
        validation_plan_text: str,
        report_text: str,
    ) -> dict[str, object]:
        issues = []
        issues.extend(self._missing_statistics(candidate_rows))

        if DOI_RE.search(literature_review_text) is None:
            issues.append("缺失 DOI：文献查阅文本没有可识别 DOI。")
        if "Sanger" not in validation_plan_text:
            issues.append("缺失验证方案：未包含 Sanger 验证。")
        if "qRT-PCR" not in validation_plan_text:
            issues.append("缺失验证方案：未包含 qRT-PCR。")
        if "LC-MS/MS" not in validation_plan_text:
            issues.append("缺失验证方案：未包含 LC-MS/MS。")
        if not all(term in marker_recommendation_text for term in ["SNP", "InDel", "KASP", "CAPS"]):
            issues.append("缺失标记类型：未完整包含 SNP/InDel/KASP/CAPS。")
        if self._has_fabricated_variant_position(candidate_rows, report_text):
            issues.append("疑似伪造变异位点：variant_status=not_called 时出现具体坐标。")
        if "最终育种验证" in report_text and "不等同于最终育种验证" not in report_text:
            issues.append("过度推断风险：报告可能把 mini evidence 写成最终育种验证。")
        issues.extend(self._variant_evidence_overclaim_issues(candidate_rows, report_text))

        reviewer_notes = (
            "ReviewerAgent 规则审阅通过：未发现缺失统计值、缺失 DOI、缺失验证方案、"
            "伪造 variant 位点或明显过度推断。"
            if not issues
            else "ReviewerAgent 规则审阅发现问题：\n- " + "\n- ".join(issues)
        )
        return {
            "passed": not issues,
            "issues": issues,
            "reviewer_notes": reviewer_notes,
        }

    def _agent_output(self, result: dict[str, object]) -> AgentOutput:
        issues = result.get("issues", [])
        issue_count = len(issues) if isinstance(issues, list) else 0
        return AgentOutput(
            agent_name=self.agent_name,
            summary=f"Reviewed report draft; issue_count={issue_count}.",
            evidence_used=[
                "candidate_rows",
                "literature_review_text",
                "marker_recommendation_text",
                "validation_plan_text",
                "draft_report_text",
            ],
            warnings=[str(issue) for issue in issues] if isinstance(issues, list) else [],
            limitations=[
                "Reviewer uses deterministic checks and does not replace human review.",
            ],
            structured_payload=result,
        )

    def _missing_statistics(
        self,
        candidate_rows: list[dict[str, str]],
    ) -> list[str]:
        issues = []
        for row in candidate_rows:
            gene_id = row.get("gene_id", "unknown")
            missing = [
                column
                for column in REQUIRED_STAT_COLUMNS
                if not row.get(column, "").strip()
            ]
            if missing:
                issues.append(f"{gene_id} 缺失统计值: {', '.join(missing)}。")
        return issues

    def _has_fabricated_variant_position(
        self,
        candidate_rows: list[dict[str, str]],
        report_text: str,
    ) -> bool:
        has_not_called = any(
            row.get("variant_status", "not_called") == "not_called"
            for row in candidate_rows
        )
        return has_not_called and POSITION_RE.search(report_text) is not None

    def _variant_evidence_overclaim_issues(
        self,
        candidate_rows: list[dict[str, str]],
        report_text: str,
    ) -> list[str]:
        issues = []
        if "LowQual" in report_text and not (
            "不应直接优先" in report_text or "不应优先" in report_text
        ):
            issues.append("LowQual 解释不足：未明确说明 LowQual 不应优先推荐。")
        if "preliminary" in report_text and not (
            "不是最终标记" in report_text or "不是最终引物" in report_text
        ):
            issues.append("preliminary KASP/CAPS 解释不足：未明确说明不是最终标记。")
        if "RNA-seq BAM" in report_text and (
            "WGS/GBS 群体变异检测" in report_text
            or "WGS 群体变异检测" in report_text
        ) and not ("不能替代 WGS/GBS" in report_text or "不能替代 WGS" in report_text):
            issues.append("variant calling 限制不足：可能把 RNA-seq BAM calling 写成 WGS/GBS。")

        no_variant_genes = {
            row.get("gene_id", "")
            for row in candidate_rows
            if row.get("variant_evidence_status", "")
            in {
                "no_called_variant_in_current_mini_calling",
                "variant_calling_output_missing",
            }
        }
        for line in report_text.splitlines():
            for gene_id in no_variant_genes:
                if gene_id and gene_id in line and "preliminary_pass_variants_detected" in line:
                    issues.append(
                        f"{gene_id} 描述错误：当前无 called variant 却写成已有 PASS variant。"
                    )
        return issues


def _as_rows(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]
