"""Gradio Web Demo for the multi-omics breeding agent."""

from __future__ import annotations

import csv
import json
import os
import traceback
from pathlib import Path
from typing import Any

import gradio as gr

from breeding_agent.integration.flavonoid_marker_package_importer import (
    create_evidence_from_package,
)
from breeding_agent.workflows.flavonoid_marker_aggregation import (
    FlavonoidMarkerAggregationConfig,
    run_flavonoid_marker_aggregation_task,
)
from breeding_agent.workflows.genomics_region import (
    GenomicsRegionConfig,
    run_genomics_region_task,
)
from breeding_agent.workflows.metabolomics_evidence import (
    MetabolomicsEvidenceConfig,
    run_metabolomics_evidence_task,
)
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
FLAVONOID_DEFAULT_DATASET_DIR = "data/private/flavonoid_marker_mini_5genes_50kb"
FLAVONOID_DEFAULT_EVIDENCE_DIR = "outputs/flavonoid_marker_from_package/evidence"
FLAVONOID_DEFAULT_OUTDIR = "outputs/flavonoid_marker_from_package"
METABOLOMICS_DEFAULT_OUTDIR = "outputs/gradio_metabolomics_run"
GENOMICS_DEFAULT_OUTDIR = "outputs/gradio_genomics_run"
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


def load_demo_metabolomics() -> tuple[str, str]:
    return FLAVONOID_DEFAULT_DATASET_DIR, METABOLOMICS_DEFAULT_OUTDIR


def load_demo_genomics() -> tuple[str, str]:
    return FLAVONOID_DEFAULT_DATASET_DIR, GENOMICS_DEFAULT_OUTDIR


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


def run_metabolomics_evidence_analysis(
    dataset_dir: str,
    outdir: str,
) -> tuple[
    str,
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    str,
    str,
]:
    warning_lines = []
    outdir_path = Path(outdir).expanduser()
    try:
        result = run_metabolomics_evidence_task(
            MetabolomicsEvidenceConfig(
                dataset_dir=Path(dataset_dir).expanduser(),
                outdir=outdir_path,
            )
        )
        warning_lines.extend(str(warning) for warning in result.get("warnings", []))
        status = (
            "Metabolomics evidence analysis succeeded. "
            f"Output: {outdir_path / 'metabolomics'}"
        )
    except Exception as exc:
        status = f"Metabolomics evidence analysis failed: {exc}"
        warning_lines.append(traceback.format_exc())
    return _build_metabolomics_outputs(
        outdir=outdir_path,
        status=status,
        warning_lines=warning_lines,
    )


def run_genomics_region_analysis_ui(
    dataset_dir: str,
    outdir: str,
) -> tuple[
    str,
    list[list[str]],
    list[list[str]],
    list[list[str]],
    str,
    str,
]:
    warning_lines = []
    outdir_path = Path(outdir).expanduser()
    try:
        result = run_genomics_region_task(
            GenomicsRegionConfig(
                dataset_dir=Path(dataset_dir).expanduser(),
                outdir=outdir_path,
            )
        )
        warning_lines.extend(str(warning) for warning in result.get("warnings", []))
        status = (
            "Genomics region analysis succeeded. "
            f"Output: {outdir_path / 'genomics'}"
        )
    except Exception as exc:
        status = f"Genomics region analysis failed: {exc}"
        warning_lines.append(traceback.format_exc())
    return _build_genomics_outputs(
        outdir=outdir_path,
        status=status,
        warning_lines=warning_lines,
    )



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


def generate_flavonoid_evidence(
    dataset_dir: str,
    evidence_dir: str,
    outdir: str,
) -> tuple[str, str, str, list[list[str]], str, str, str]:
    warning_lines = []
    try:
        result = create_evidence_from_package(
            dataset_dir=Path(dataset_dir).expanduser(),
            outdir=Path(evidence_dir).expanduser(),
        )
        written_files = result.get("written_files", [])
        warning_lines.extend(
            f"Optional file missing: {path}"
            for path in result.get("optional_missing", [])
        )
        status = "evidence 生成成功。\n" + "\n".join(
            f"- {name}: {path} ({row_count} rows)"
            for name, path, row_count in written_files
        )
        missing_targets = result.get("missing_targets", [])
        if missing_targets:
            warning_lines.append(
                "缺少固定重点基因: " + ", ".join(str(gene) for gene in missing_targets)
            )
    except Exception as exc:
        status = f"evidence 生成失败: {exc}"
        warning_lines.append(traceback.format_exc())
    return _build_flavonoid_outputs(
        outdir=Path(outdir).expanduser(),
        status=status,
        warning_lines=warning_lines,
    )


def run_flavonoid_marker_recommendation(
    dataset_dir: str,
    evidence_dir: str,
    outdir: str,
) -> tuple[str, str, str, list[list[str]], str, str, str]:
    del dataset_dir
    warning_lines = []
    try:
        report_file = run_flavonoid_marker_aggregation_task(
            FlavonoidMarkerAggregationConfig(
                evidence_dir=Path(evidence_dir).expanduser(),
                outdir=Path(outdir).expanduser(),
            )
        )
        status = f"标记推荐运行成功。报告: {report_file}"
    except Exception as exc:
        status = f"标记推荐运行失败: {exc}"
        warning_lines.append(traceback.format_exc())
    return _build_flavonoid_outputs(
        outdir=Path(outdir).expanduser(),
        status=status,
        warning_lines=warning_lines,
    )


def run_flavonoid_full_pipeline(
    dataset_dir: str,
    evidence_dir: str,
    outdir: str,
) -> tuple[str, str, str, list[list[str]], str, str, str]:
    warning_lines = []
    try:
        evidence_result = create_evidence_from_package(
            dataset_dir=Path(dataset_dir).expanduser(),
            outdir=Path(evidence_dir).expanduser(),
        )
        warning_lines.extend(
            f"Optional file missing: {path}"
            for path in evidence_result.get("optional_missing", [])
        )
        report_file = run_flavonoid_marker_aggregation_task(
            FlavonoidMarkerAggregationConfig(
                evidence_dir=Path(evidence_dir).expanduser(),
                outdir=Path(outdir).expanduser(),
            )
        )
        status = f"完整流程运行成功。报告: {report_file}"
    except Exception as exc:
        status = f"完整流程运行失败: {exc}"
        warning_lines.append(traceback.format_exc())
    return _build_flavonoid_outputs(
        outdir=Path(outdir).expanduser(),
        status=status,
        warning_lines=warning_lines,
    )


def refresh_flavonoid_outputs(
    outdir: str,
) -> tuple[str, str, str, list[list[str]], str, str, str]:
    return _build_flavonoid_outputs(
        outdir=Path(outdir).expanduser(),
        status="已刷新当前输出文件。",
        warning_lines=[],
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Agri Multi-omics Breeding Agent Demo") as demo:
        gr.Markdown("# Agri Multi-omics Breeding Agent Demo")
        gr.Markdown(
            "Multi-omics breeding agent demo with a working transcriptomics DEG "
            "module, package-derived metabolomics evidence analysis, genomics "
            "region analysis, and flavonoid marker recommendation."
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
            with gr.Row():
                with gr.Column():
                    metabolomics_dataset_dir = gr.Textbox(
                        label="dataset_dir",
                        value=FLAVONOID_DEFAULT_DATASET_DIR,
                    )
                    metabolomics_outdir = gr.Textbox(
                        label="outdir",
                        value=METABOLOMICS_DEFAULT_OUTDIR,
                    )
                    with gr.Row():
                        load_metabolomics_demo = gr.Button("Load Demo Metabolomics")
                        metabolomics_button = gr.Button(
                            "Run Metabolomics Evidence Analysis",
                            variant="primary",
                        )
                with gr.Column():
                    metabolomics_status = gr.Textbox(label="status", lines=8)

            gr.Markdown("### candidate_metabolites.tsv")
            metabolomics_candidate_metabolites = gr.DataFrame(
                label="candidate_metabolites.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### flavonoid_related_significant_metabolites.tsv")
            metabolomics_significant_metabolites = gr.DataFrame(
                label="flavonoid_related_significant_metabolites.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### target_gene_metabolite_network_edges.tsv")
            metabolomics_network_edges = gr.DataFrame(
                label="target_gene_metabolite_network_edges.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### target_gene_spls_coefficients.tsv")
            metabolomics_spls_coefficients = gr.DataFrame(
                label="target_gene_spls_coefficients.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### metabolomics_report.md")
            metabolomics_report = gr.Markdown()
            metabolomics_manifest = gr.Textbox(label="manifest.json", lines=16)

        with gr.Tab("Genomics / GWAS Module"):
            with gr.Row():
                with gr.Column():
                    genomics_dataset_dir = gr.Textbox(
                        label="dataset_dir",
                        value=FLAVONOID_DEFAULT_DATASET_DIR,
                    )
                    genomics_outdir = gr.Textbox(
                        label="outdir",
                        value=GENOMICS_DEFAULT_OUTDIR,
                    )
                    with gr.Row():
                        load_genomics_demo = gr.Button("Load Demo Genomics")
                        genomics_button = gr.Button(
                            "Run Genomics Region Analysis",
                            variant="primary",
                        )
                with gr.Column():
                    genomics_status = gr.Textbox(label="status", lines=8)

            gr.Markdown("### target_gene_regions.tsv")
            genomics_target_regions = gr.DataFrame(
                label="target_gene_regions.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### annotation_summary.tsv")
            genomics_annotation_summary = gr.DataFrame(
                label="annotation_summary.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### marker_readiness.tsv")
            genomics_marker_readiness = gr.DataFrame(
                label="marker_readiness.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### genomics_report.md")
            genomics_report = gr.Markdown()
            genomics_manifest = gr.Textbox(label="manifest.json", lines=16)

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
        load_metabolomics_demo.click(
            fn=load_demo_metabolomics,
            outputs=[metabolomics_dataset_dir, metabolomics_outdir],
        )
        metabolomics_button.click(
            fn=run_metabolomics_evidence_analysis,
            inputs=[metabolomics_dataset_dir, metabolomics_outdir],
            outputs=[
                metabolomics_status,
                metabolomics_candidate_metabolites,
                metabolomics_significant_metabolites,
                metabolomics_network_edges,
                metabolomics_spls_coefficients,
                metabolomics_report,
                metabolomics_manifest,
            ],
        )
        load_genomics_demo.click(
            fn=load_demo_genomics,
            outputs=[genomics_dataset_dir, genomics_outdir],
        )
        genomics_button.click(
            fn=run_genomics_region_analysis_ui,
            inputs=[genomics_dataset_dir, genomics_outdir],
            outputs=[
                genomics_status,
                genomics_target_regions,
                genomics_annotation_summary,
                genomics_marker_readiness,
                genomics_report,
                genomics_manifest,
            ],
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

        with gr.Tab("谷子黄酮候选标记推荐"):
            gr.Markdown(
                "本页面只接收服务器本地路径，不上传 BAM/FASTA 大文件；用于生成 "
                "evidence、运行候选标记推荐，并查看报告、QA 和候选表。"
            )
            with gr.Row():
                with gr.Column():
                    flavonoid_dataset_dir = gr.Textbox(
                        label="dataset_dir",
                        value=FLAVONOID_DEFAULT_DATASET_DIR,
                    )
                    flavonoid_evidence_dir = gr.Textbox(
                        label="evidence_dir",
                        value=FLAVONOID_DEFAULT_EVIDENCE_DIR,
                    )
                    flavonoid_outdir = gr.Textbox(
                        label="outdir",
                        value=FLAVONOID_DEFAULT_OUTDIR,
                    )
                    with gr.Row():
                        generate_evidence_button = gr.Button("生成 evidence")
                        run_marker_button = gr.Button(
                            "运行标记推荐",
                            variant="primary",
                        )
                    full_pipeline_button = gr.Button("一键运行完整流程", variant="primary")
                    refresh_flavonoid_button = gr.Button("刷新当前结果")
                with gr.Column():
                    flavonoid_status = gr.Textbox(label="运行状态", lines=8)
                    flavonoid_qa_status = gr.Textbox(label="QA 状态", lines=2)
                    flavonoid_warnings = gr.Textbox(
                        label="warning / error 信息",
                        lines=10,
                    )

            gr.Markdown("### Markdown 报告")
            flavonoid_report = gr.Markdown()
            gr.Markdown("### 候选标记表")
            flavonoid_candidate_table = gr.DataFrame(
                label="flavonoid_marker_candidates.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            with gr.Row():
                flavonoid_qa_json = gr.Textbox(label="qa_check.json", lines=18)
                flavonoid_manifest_json = gr.Textbox(label="manifest.json", lines=18)

        flavonoid_button_inputs = [
            flavonoid_dataset_dir,
            flavonoid_evidence_dir,
            flavonoid_outdir,
        ]
        flavonoid_outputs = [
            flavonoid_status,
            flavonoid_qa_status,
            flavonoid_report,
            flavonoid_candidate_table,
            flavonoid_qa_json,
            flavonoid_manifest_json,
            flavonoid_warnings,
        ]
        generate_evidence_button.click(
            fn=generate_flavonoid_evidence,
            inputs=flavonoid_button_inputs,
            outputs=flavonoid_outputs,
        )
        run_marker_button.click(
            fn=run_flavonoid_marker_recommendation,
            inputs=flavonoid_button_inputs,
            outputs=flavonoid_outputs,
        )
        full_pipeline_button.click(
            fn=run_flavonoid_full_pipeline,
            inputs=flavonoid_button_inputs,
            outputs=flavonoid_outputs,
        )
        refresh_flavonoid_button.click(
            fn=refresh_flavonoid_outputs,
            inputs=[flavonoid_outdir],
            outputs=flavonoid_outputs,
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


def _build_metabolomics_outputs(
    *,
    outdir: Path,
    status: str,
    warning_lines: list[str],
) -> tuple[
    str,
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    str,
    str,
]:
    output_dir = outdir / "metabolomics"
    candidate_path = output_dir / "candidate_metabolites.tsv"
    significant_path = output_dir / "flavonoid_related_significant_metabolites.tsv"
    network_path = output_dir / "target_gene_metabolite_network_edges.tsv"
    spls_path = output_dir / "target_gene_spls_coefficients.tsv"
    report_path = output_dir / "metabolomics_report.md"
    manifest_path = output_dir / "manifest.json"

    missing_outputs = [
        str(path)
        for path in [
            candidate_path,
            significant_path,
            network_path,
            spls_path,
            report_path,
            manifest_path,
        ]
        if not path.exists()
    ]
    if missing_outputs:
        warning_lines.extend(
            "输出文件不存在，可能需要先运行代谢组 evidence analysis: " + path
            for path in missing_outputs
        )
    if warning_lines:
        status = status + "\n\nWarnings:\n" + "\n".join(warning_lines)

    return (
        status,
        _read_tsv_for_dataframe(candidate_path),
        _read_tsv_for_dataframe(significant_path),
        _read_tsv_for_dataframe(network_path),
        _read_tsv_for_dataframe(spls_path),
        _read_text(report_path),
        _read_json_text(manifest_path),
    )


def _build_genomics_outputs(
    *,
    outdir: Path,
    status: str,
    warning_lines: list[str],
) -> tuple[str, list[list[str]], list[list[str]], list[list[str]], str, str]:
    output_dir = outdir / "genomics"
    regions_path = output_dir / "target_gene_regions.tsv"
    annotation_path = output_dir / "annotation_summary.tsv"
    marker_path = output_dir / "marker_readiness.tsv"
    report_path = output_dir / "genomics_report.md"
    manifest_path = output_dir / "manifest.json"

    missing_outputs = [
        str(path)
        for path in [
            regions_path,
            annotation_path,
            marker_path,
            report_path,
            manifest_path,
        ]
        if not path.exists()
    ]
    if missing_outputs:
        warning_lines.extend(
            "输出文件不存在，可能需要先运行基因组 region analysis: " + path
            for path in missing_outputs
        )
    if warning_lines:
        status = status + "\n\nWarnings:\n" + "\n".join(warning_lines)

    return (
        status,
        _read_tsv_for_dataframe(regions_path),
        _read_tsv_for_dataframe(annotation_path),
        _read_tsv_for_dataframe(marker_path),
        _read_text(report_path),
        _read_json_text(manifest_path),
    )


def _build_flavonoid_outputs(
    *,
    outdir: Path,
    status: str,
    warning_lines: list[str],
) -> tuple[str, str, str, list[list[str]], str, str, str]:
    report_path = outdir / "reports" / "flavonoid_marker_report.md"
    candidate_path = outdir / "integration" / "flavonoid_marker_candidates.tsv"
    qa_path = outdir / "logs" / "qa_check.json"
    manifest_path = outdir / "manifest.json"

    report_text = _read_text(report_path)
    candidate_table = _read_tsv_for_dataframe(candidate_path)
    qa_json_text = _read_json_text(qa_path)
    manifest_json_text = _read_json_text(manifest_path)
    qa_status = _flavonoid_qa_status(qa_path)

    missing_outputs = [
        str(path)
        for path in [report_path, candidate_path, qa_path, manifest_path]
        if not path.exists()
    ]
    if missing_outputs:
        warning_lines.extend(
            "输出文件不存在，可能需要先运行完整流程: " + path
            for path in missing_outputs
        )

    return (
        status,
        qa_status,
        report_text,
        candidate_table,
        qa_json_text,
        manifest_json_text,
        "\n".join(warning_lines) if warning_lines else "无 warning / error。",
    )


def _flavonoid_qa_status(qa_path: Path) -> str:
    if not qa_path.exists():
        return f"QA 状态未知：文件不存在 {qa_path}"
    try:
        qa_result = json.loads(qa_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return f"QA 状态未知：无法解析 {qa_path}"
    passed = qa_result.get("passed")
    missing_items = qa_result.get("missing_items", [])
    if passed is True:
        return "passed=true"
    return f"passed={passed}; missing_items={missing_items}"


demo = build_app()


if __name__ == "__main__":
    demo.launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
    )
