"""Generate Markdown reports for DEG workflow runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from breeding_agent.reports.deg_result_parser import (
    TARGET_GENE_ID,
    DegResultSummary,
    parse_deg_results,
)


@dataclass(frozen=True)
class DegReportConfig:
    task_name: str
    bam_dir: Path
    gff: Path
    contrast: str
    prefix: str
    outdir: Path
    counts_file: Path
    significant_genes_file: Path
    manifest_file: Path
    run_log_file: Path


def generate_deg_report(config: DegReportConfig) -> Path:
    summary = parse_deg_results(config.outdir, config.prefix)
    report_dir = config.outdir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "report.md"
    report_file.write_text(_render_report(config, summary), encoding="utf-8")
    return report_file


def _render_report(config: DegReportConfig, summary: DegResultSummary) -> str:
    target = summary.target_gene
    direction = _target_direction(config.contrast, target.logfc)
    reproduced = "yes" if target.found else "no"
    target_line = (
        f"{summary.target_gene_id} {direction}"
        if target.found
        else f"{summary.target_gene_id} was not found in significant genes."
    )

    return "\n".join(
        [
            "# RNA-seq DEG Report",
            "",
            f"- Task name: {config.task_name}",
            f"- Input BAM directory: {config.bam_dir}",
            f"- Input GFF file: {config.gff}",
            f"- Contrast: {config.contrast}",
            "",
            "## Output Files",
            "",
            f"- Counts: {config.counts_file}",
            f"- Significant genes: {config.significant_genes_file}",
            f"- Manifest: {config.manifest_file}",
            f"- Run log: {config.run_log_file}",
            "",
            "## DEG Summary",
            "",
            f"- Significant gene count: {summary.significant_gene_count}",
            f"- Target gene {TARGET_GENE_ID} reproduced: {reproduced}",
            f"- logFC: {_format_value(target.logfc)}",
            f"- adj.P.Val: {_format_value(target.adj_p_val)}",
            f"- mean_count_JM: {_format_value(target.mean_count_jm)}",
            f"- mean_count_LM: {_format_value(target.mean_count_lm)}",
            "",
            "## Expression Direction",
            "",
            "- For contrast=JM-LM, logFC > 0 means JM higher expression.",
            "- For contrast=JM-LM, logFC < 0 means LM higher expression.",
            f"- Result: {target_line}",
            "",
            "## Next Steps",
            "",
            "- Review the significant gene table and confirm the DEG thresholds match the analysis plan.",
            "- Inspect the counts and normalized expression for the target gene across all samples.",
            "- Use the generated manifest and run log when archiving or comparing future reruns.",
            "",
        ]
    )


def _target_direction(contrast: str, logfc: float | None) -> str:
    if logfc is None:
        return "has no parseable logFC value."
    if contrast == "JM-LM":
        if logfc > 0:
            return "is significantly higher expressed in JM."
        if logfc < 0:
            return "在 LM 组显著高表达。"
        return "has equal expression direction by logFC=0."
    return f"has logFC={logfc}; expression direction is not defined for contrast={contrast}."


def _format_value(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.6g}"

