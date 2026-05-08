"""Markdown report generation for genomics region analysis."""

from __future__ import annotations

from pathlib import Path


def generate_genomics_report(
    *,
    output_dir: Path,
    analysis_result: dict[str, object],
) -> Path:
    """Write a Markdown genomics report and return its path."""

    report_path = output_dir / "genomics_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _render_report(analysis_result),
        encoding="utf-8",
    )
    return report_path


def _render_report(result: dict[str, object]) -> str:
    lines = [
        "# 基因组 Region / Annotation Analysis 报告",
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
            "## 目标基因候选区域",
            _table_from_records(
                result.get("target_regions", []),
                [
                    "gene_id",
                    "chrom",
                    "start",
                    "end",
                    "strand",
                    "region_name",
                    "region_samtools",
                ],
            ),
            "",
            "## 功能注释摘要",
            _table_from_records(
                result.get("annotation_summary", []),
                [
                    "gene_id",
                    "Description",
                    "Preferred_name",
                    "KEGG_ko",
                    "KEGG_Pathway",
                    "PFAMs",
                ],
            ),
            "",
            "## Marker Readiness",
            _table_from_records(
                result.get("marker_readiness", []),
                [
                    "gene_id",
                    "variant_status",
                    "candidate_marker_types",
                    "readiness_summary",
                    "required_next_step",
                ],
            ),
            "",
            "## 当前限制",
            (
                "当前 mini 数据包未提供最终 SNP/InDel 位点；第一版只进行"
                "候选区域和功能注释 evidence analysis，不输出具体 SNP/InDel 坐标。"
            ),
            (
                "后续需要基于 BAM、genome.fa/genome.gff 或 "
                "genome.bam_compatible.fa.gz 与 genome.original_coords.gff "
                "进行候选区域 SNP/InDel calling，再筛选 KASP/CAPS 可转化位点。"
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
