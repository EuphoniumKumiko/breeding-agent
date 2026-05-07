"""Gradio Web Demo for the multi-omics breeding agent."""

from __future__ import annotations

import csv
import json
import traceback
from pathlib import Path
from typing import Any

import gradio as gr

from breeding_agent.workflows.rnaseq_deg import RnaSeqDegConfig, run_rnaseq_deg_task


DEMO_BAM_DIR = (
    "~/projects/TG5_101_mini_deg_50kb_reproduction_package/mini_deg_pipeline/bam"
)
DEMO_GFF = (
    "~/projects/TG5_101_mini_deg_50kb_reproduction_package/mini_deg_pipeline/"
    "genome.original_coords.gff"
)
DEMO_CONTRAST = "JM-LM"
DEMO_PREFIX = "JM_vs_LM.mini"
DEMO_THREADS = 4
DEMO_OUTDIR = "outputs/gradio_demo_run"
TRAIT_CHOICES = [
    "高产",
    "抗旱",
    "耐盐碱",
    "抗病",
    "生物胁迫",
    "非生物胁迫",
]
STANDARDIZED_EVIDENCE_DISPLAY_COLUMNS = [
    "entity_id",
    "omics_type",
    "trait",
    "comparison",
    "direction",
    "effect_size",
    "adj_p_value",
    "evidence_score",
    "source_module",
]
RECOMMENDATION_REPORT_NOTICE = (
    "注意：当前 trait 来自用户输入的分析目标，尚未接入独立表型数据；"
    "因此本报告不能直接证明候选基因与该性状存在因果关系。"
)


def load_demo_benchmark() -> tuple[str, str, int]:
    return (
        DEMO_BAM_DIR,
        DEMO_GFF,
        DEMO_THREADS,
    )


def run_deg_analysis(
    trait_selection: str,
    bam_dir: str,
    gff: str,
    optional_file: str,
    threads: float | int,
    prefix: str = DEMO_PREFIX,
    outdir: str = DEMO_OUTDIR,
    contrast: str = DEMO_CONTRAST,
) -> tuple[str, list[list[str]], str, str, str, str]:
    outdir_path = Path(outdir).expanduser()
    manifest_path = outdir_path / "manifest.json"
    run_log_path = outdir_path / "logs" / "run.log"
    report_path = outdir_path / "reports" / "report.md"
    recommendation_report_path = outdir_path / "integration" / "recommendation_report.md"
    significant_genes_path = outdir_path / "mini_de" / f"{prefix}.significant_genes.tsv"

    try:
        config = RnaSeqDegConfig(
            bam_dir=Path(bam_dir).expanduser(),
            gff=Path(gff).expanduser(),
            contrast=contrast,
            prefix=prefix,
            trait=trait_selection or "unknown",
            threads=int(threads),
            outdir=outdir_path,
        )
        significant_genes = run_rnaseq_deg_task(config)
        status = (
            f"Success. Trait: {trait_selection}. "
            f"Optional file: {optional_file or 'not provided'}. "
            f"Significant genes: {significant_genes}"
        )
    except Exception as exc:
        status = f"Failed: {exc}\n\n{traceback.format_exc()}"

    report_text = _read_first_existing_text(recommendation_report_path, report_path)
    return (
        status,
        _read_tsv_for_dataframe(significant_genes_path),
        report_text,
        report_text,
        _read_json_text(manifest_path),
        _read_text(run_log_path),
    )


def run_placeholder_analysis(*_: str) -> str:
    return "Coming soon."


def build_integration_recommendation() -> tuple[
    str,
    list[list[str]],
    str,
    list[list[str]],
    str,
    str,
    str,
]:
    outdir_path = Path(DEMO_OUTDIR).expanduser()
    manifest_path = outdir_path / "manifest.json"
    run_log_path = outdir_path / "logs" / "run.log"
    evidence_path = outdir_path / "integration" / "standardized_evidence.tsv"
    candidate_gene_table_path = (
        outdir_path / "integration" / "candidate_gene_table.tsv"
    )
    recommendation_report_path = (
        outdir_path / "integration" / "recommendation_report.md"
    )
    transcriptomics_report_path = outdir_path / "reports" / "report.md"
    commands_sh_path = outdir_path / "provenance" / "commands.sh"
    checksums_sha256_path = outdir_path / "provenance" / "checksums.sha256"

    if evidence_path.exists():
        evidence_status = ""
        evidence_table = _read_tsv_for_dataframe(
            evidence_path,
            display_columns=STANDARDIZED_EVIDENCE_DISPLAY_COLUMNS,
        )
    else:
        evidence_status = "请先运行 Transcriptomics DEG Module 生成 standardized evidence。"
        evidence_table = []

    if candidate_gene_table_path.exists():
        candidate_status = ""
        candidate_table = _read_tsv_for_dataframe(candidate_gene_table_path)
    else:
        candidate_status = "请先运行 Transcriptomics DEG Module 生成 candidate gene table。"
        candidate_table = []

    transcriptomics_report = _read_text(transcriptomics_report_path)
    if recommendation_report_path.exists():
        recommendation_report = _read_text(recommendation_report_path)
    elif transcriptomics_report_path.exists():
        recommendation_report = (
            "当前仅找到 transcriptomics report，尚未生成 recommendation_report.md。\n\n"
            f"{transcriptomics_report}"
        )
    else:
        recommendation_report = (
            "No recommendation report or transcriptomics report is available yet.\n\n"
            "Current version only uses transcriptomics evidence. Future versions can "
            "integrate metabolomics and genomics evidence."
        )

    return (
        evidence_status,
        evidence_table,
        candidate_status,
        candidate_table,
        recommendation_report,
        transcriptomics_report,
        _build_provenance_summary(
            manifest_path=manifest_path,
            run_log_path=run_log_path,
            commands_sh_path=commands_sh_path,
            checksums_sha256_path=checksums_sha256_path,
        ),
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Agri Multi-omics Breeding Agent Demo") as demo:
        gr.Markdown("# Agri Multi-omics Breeding Agent Demo")
        gr.Markdown(
            "Multi-omics breeding agent demo with a working transcriptomics DEG "
            "module and first-version placeholders for metabolomics, genomics, "
            "and evidence integration."
        )

        with gr.Tab("Transcriptomics DEG Module"):
            with gr.Row():
                with gr.Column():
                    trait_selection = gr.Dropdown(
                        label="trait_selection",
                        choices=TRAIT_CHOICES,
                        value=TRAIT_CHOICES[0],
                    )
                    bam_dir = gr.Textbox(label="BAM directory")
                    gff = gr.Textbox(label="GFF annotation")
                    optional_file = gr.Textbox(
                        label="optional_file",
                        placeholder="Optional supporting file path",
                    )
                    threads = gr.Number(label="threads", value=DEMO_THREADS, precision=0)
                    gr.Markdown(
                        f"Advanced defaults: contrast `{DEMO_CONTRAST}`, prefix "
                        f"`{DEMO_PREFIX}`, outdir `{DEMO_OUTDIR}`."
                    )

                    with gr.Row():
                        load_demo = gr.Button("Load Demo Benchmark")
                        run_button = gr.Button(
                            "Run Transcriptomics Analysis", variant="primary"
                        )

                with gr.Column():
                    status = gr.Textbox(label="status", lines=6)

            significant_genes = gr.DataFrame(
                label="significant_genes",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            report = gr.Markdown(label="recommendation_report.md / report.md")
            report_state = gr.Textbox(visible=False)
            manifest = gr.Textbox(label="manifest.json", lines=16)
            run_log = gr.Textbox(label="run.log", lines=18)

        with gr.Tab("Metabolomics Module"):
            metabolomics_table = gr.Textbox(label="metabolomics_table")
            sample_metadata = gr.Textbox(label="sample_metadata")
            metabolomics_button = gr.Button("Run Metabolomics Analysis")
            metabolomics_status = gr.Textbox(label="status", lines=3)

        with gr.Tab("Genomics / GWAS Module"):
            genotype_or_vcf = gr.Textbox(label="genotype_or_vcf")
            phenotype_table = gr.Textbox(label="phenotype_table")
            genomics_button = gr.Button("Run Genomics Analysis")
            genomics_status = gr.Textbox(label="status", lines=3)

        with gr.Tab("Integration & Recommendation"):
            integration_button = gr.Button("Generate Recommendation", variant="primary")
            gr.Markdown("### Standardized Evidence Table")
            evidence_status = gr.Markdown()
            standardized_evidence = gr.DataFrame(
                label="standardized_evidence.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### Candidate Gene Table")
            candidate_status = gr.Markdown()
            candidate_gene_table = gr.DataFrame(
                label="candidate_gene_table.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### Recommendation Report")
            gr.Markdown(RECOMMENDATION_REPORT_NOTICE)
            integration_output = gr.Markdown()
            with gr.Accordion("Current Transcriptomics Report", open=False):
                current_transcriptomics_report = gr.Markdown()
            gr.Markdown("### Provenance / Reproducibility")
            provenance_summary = gr.Markdown()

        load_demo.click(
            fn=load_demo_benchmark,
            outputs=[bam_dir, gff, threads],
        )
        run_button.click(
            fn=run_deg_analysis,
            inputs=[trait_selection, bam_dir, gff, optional_file, threads],
            outputs=[status, significant_genes, report, report_state, manifest, run_log],
        )
        metabolomics_button.click(
            fn=run_placeholder_analysis,
            inputs=[metabolomics_table, sample_metadata],
            outputs=metabolomics_status,
        )
        genomics_button.click(
            fn=run_placeholder_analysis,
            inputs=[genotype_or_vcf, phenotype_table],
            outputs=genomics_status,
        )
        integration_button.click(
            fn=build_integration_recommendation,
            inputs=[],
            outputs=[
                evidence_status,
                standardized_evidence,
                candidate_status,
                candidate_gene_table,
                integration_output,
                current_transcriptomics_report,
                provenance_summary,
            ],
        )

    return demo


def _read_tsv_for_dataframe(
    path: Path,
    display_columns: list[str] | None = None,
) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.reader(handle, delimiter="\t")]
    if not display_columns or not rows:
        return rows

    header = rows[0]
    column_indices = [
        header.index(column) for column in display_columns if column in header
    ]
    if not column_indices:
        return rows
    return [
        [row[index] if index < len(row) else "" for index in column_indices]
        for row in rows
    ]


def _read_text(path: Path) -> str:
    if not path.exists():
        return f"File not found: {path}"
    return path.read_text(encoding="utf-8", errors="replace")


def _read_first_existing_text(*paths: Path) -> str:
    for path in paths:
        if path.exists():
            return _read_text(path)
    return f"File not found: {paths[0]}"


def _build_provenance_summary(
    *,
    manifest_path: Path,
    run_log_path: Path,
    commands_sh_path: Path,
    checksums_sha256_path: Path,
) -> str:
    provenance_files = [
        (manifest_path, "Workflow manifest with inputs, outputs, and run metadata."),
        (run_log_path, "Execution log for validation and external commands."),
        (commands_sh_path, "Reproducibility script with featureCounts and Rscript commands."),
        (checksums_sha256_path, "SHA-256 checksums for key inputs and generated outputs."),
    ]
    if not all(path.exists() for path, _ in provenance_files):
        return "请先运行 Transcriptomics DEG Module 生成 provenance / reproducibility 文件。"

    lines = []
    for path, description in provenance_files:
        lines.append(f"- `{path}`: {description}")
    return "\n".join(lines)


def _read_json_text(path: Path) -> str:
    if not path.exists():
        return f"File not found: {path}"
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    return json.dumps(data, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860)
