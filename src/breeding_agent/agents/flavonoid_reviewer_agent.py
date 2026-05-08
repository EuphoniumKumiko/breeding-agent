"""Rule-based reviewer for flavonoid marker aggregation outputs."""

from __future__ import annotations

import re


REQUIRED_STAT_COLUMNS = ["baseMean", "log2FC", "pvalue", "padj"]
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s|)]+", re.IGNORECASE)
POSITION_RE = re.compile(
    r"(?i)(?:chr\w+|scaffold\w+|contig\w+|si\d+\w*)[:：]\d+|\bposition=\d+"
)


class FlavonoidReviewerAgent:
    """Check for common over-claiming and evidence omissions."""

    def run(
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
