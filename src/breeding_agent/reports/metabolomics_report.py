"""Markdown report generation for metabolomics evidence analysis."""

from __future__ import annotations

from pathlib import Path


def generate_metabolomics_report(
    *,
    output_dir: Path,
    analysis_result: dict[str, object],
) -> Path:
    """Write a Markdown metabolomics report and return its path."""

    report_path = output_dir / "metabolomics_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _render_report(analysis_result),
        encoding="utf-8",
    )
    return report_path


def _render_report(result: dict[str, object]) -> str:
    lines = [
        "# 代谢组 Evidence Analysis 报告",
        "",
        "## 输入文件",
    ]
    inputs = result.get("inputs", {})
    if isinstance(inputs, dict):
        for name, info in inputs.items():
            if isinstance(info, dict):
                status = "present" if info.get("exists") else "missing"
                lines.append(f"- {name}: `{info.get('path')}` ({status})")

    warnings = result.get("warnings", [])
    lines.extend(["", "## Warning"])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- 无。")

    lines.extend(
        [
            "",
            "## 候选黄酮代谢物",
            _table_from_records(
                result.get("candidate_preview", []),
                [
                    "Index",
                    "Compounds",
                    "Class I",
                    "Class II",
                    "VIP",
                    "FDR",
                    "Log2FC",
                    "Direction",
                    "Candidate_score",
                ],
            ),
            "",
            "## 显著黄酮相关代谢物",
            _table_from_records(
                result.get("significant_preview", []),
                [
                    "Index",
                    "Compounds",
                    "Class I",
                    "Class II",
                    "VIP",
                    "FDR",
                    "Log2FC",
                    "Direction",
                ],
            ),
            "",
            "## 目标基因-代谢物相关网络",
            _table_from_records(
                result.get("top_network_edges", []),
                [
                    "Gene",
                    "Metabolite_name",
                    "Metabolite_subclass",
                    "Pearson_r",
                    "Pearson_FDR",
                    "edge_sign",
                    "edge_weight",
                ],
            ),
            "",
            "## sPLS 证据",
            _table_from_records(
                result.get("top_spls_coefficients", []),
                [
                    "Gene",
                    "Metabolite_name",
                    "Coefficient",
                    "abs_coefficient",
                ],
            ),
            "",
            "## 三个重点基因关系",
            _table_from_records(
                result.get("target_gene_summary", []),
                [
                    "gene_id",
                    "description",
                    "direction",
                    "n_network_edges",
                    "max_abs_pearson",
                    "top_correlated_metabolite",
                    "top_pearson_r",
                    "n_spls_coefficients",
                    "max_abs_spls_coefficient",
                    "top_spls_metabolite",
                ],
            ),
            "",
            "## 当前限制",
            (
                "这是基于学长数据包已有代谢组结果表的 evidence analysis，"
                "不是从原始质谱峰表重新做完整代谢组统计流程。"
            ),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _table_from_records(records_obj: object, columns: list[str]) -> str:
    if not isinstance(records_obj, list) or not records_obj:
        return "无可展示记录。"

    records = [row for row in records_obj if isinstance(row, dict)]
    if not records:
        return "无可展示记录。"

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in records:
        values = [_escape_markdown_table(str(row.get(column, ""))) for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _escape_markdown_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
