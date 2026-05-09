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
from breeding_agent.modules.genomics.variant_calling import MissingToolError
from breeding_agent.workflows.flavonoid_marker_aggregation import (
    FlavonoidMarkerAggregationConfig,
    run_flavonoid_marker_aggregation_task,
)
from breeding_agent.workflows.flavonoid_marker_langgraph import (
    DEFAULT_LANGGRAPH_OUTDIR,
    FlavonoidMarkerLangGraphConfig,
    run_flavonoid_marker_langgraph_task,
)
from breeding_agent.workflows.genomics_region import (
    GenomicsRegionConfig,
    run_genomics_region_task,
)
from breeding_agent.workflows.genomics_variant_calling import (
    DEFAULT_OUTDIR as GENOMICS_VARIANT_DEFAULT_OUTDIR,
    GenomicsVariantCallingConfig,
    run_genomics_variant_calling_task,
)
from breeding_agent.workflows.lobster_external_agent_benchmark import (
    DEFAULT_LOBSTER_BENCHMARK_OUTDIR,
    LobsterExternalAgentBenchmarkConfig,
    run_lobster_external_agent_benchmark_task,
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
FLAVONOID_LANGGRAPH_DEFAULT_OUTDIR = DEFAULT_LANGGRAPH_OUTDIR
FLAVONOID_LLM_CONFIG_DEFAULT = "configs/llm.local.yaml"
FLAVONOID_INTERNAL_AGENT_DEFAULT_OUTDIR = "outputs/flavonoid_marker_langgraph_llm_real"
FLAVONOID_LOBSTER_BENCHMARK_DEFAULT_OUTDIR = DEFAULT_LOBSTER_BENCHMARK_OUTDIR
METABOLOMICS_DEFAULT_OUTDIR = "outputs/gradio_metabolomics_run"
GENOMICS_DEFAULT_OUTDIR = "outputs/gradio_genomics_run"
GENOMICS_VARIANT_DEFAULT_DATASET_DIR = FLAVONOID_DEFAULT_DATASET_DIR
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


def load_demo_variant_calling() -> tuple[str, str]:
    return GENOMICS_VARIANT_DEFAULT_DATASET_DIR, GENOMICS_VARIANT_DEFAULT_OUTDIR


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


def run_genomics_variant_calling_ui(
    dataset_dir: str,
    outdir: str,
) -> tuple[
    str,
    str,
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    str,
    str,
    str,
]:
    warning_lines = []
    outdir_path = Path(outdir).expanduser()
    try:
        result = run_genomics_variant_calling_task(
            GenomicsVariantCallingConfig(
                dataset_dir=Path(dataset_dir).expanduser(),
                outdir=outdir_path,
            )
        )
        warning_lines.extend(str(warning) for warning in result.get("warnings", []))
        status = (
            "Candidate variant calling succeeded. "
            f"Output: {outdir_path}"
        )
    except MissingToolError as exc:
        status = (
            "Candidate variant calling failed: samtools/bcftools is not available.\n"
            f"{exc}"
        )
    except Exception as exc:
        status = f"Candidate variant calling failed: {exc}"
        warning_lines.append(traceback.format_exc())

    return load_variant_calling_outputs(
        outdir=outdir_path,
        status=status,
        warning_lines=warning_lines,
    )


def refresh_variant_calling_outputs(
    outdir: str,
) -> tuple[
    str,
    str,
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    str,
    str,
    str,
]:
    return load_variant_calling_outputs(
        outdir=Path(outdir).expanduser(),
        status="已刷新 candidate variant calling 输出文件。",
        warning_lines=[],
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
    variant_calling_dir: str,
) -> tuple[str, str, str, list[list[str]], str, str, str]:
    del dataset_dir
    warning_lines = []
    try:
        variant_dir = _optional_existing_dir(variant_calling_dir)
        if variant_calling_dir and variant_dir is None:
            warning_lines.append(
                "variant_calling_dir 不存在或留空，保持原有黄酮推荐流程: "
                f"{variant_calling_dir}"
            )
        report_file = run_flavonoid_marker_aggregation_task(
            FlavonoidMarkerAggregationConfig(
                evidence_dir=Path(evidence_dir).expanduser(),
                outdir=Path(outdir).expanduser(),
                variant_calling_dir=variant_dir,
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
    variant_calling_dir: str,
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
        variant_dir = _optional_existing_dir(variant_calling_dir)
        if variant_calling_dir and variant_dir is None:
            warning_lines.append(
                "variant_calling_dir 不存在或留空，保持原有黄酮推荐流程: "
                f"{variant_calling_dir}"
            )
        report_file = run_flavonoid_marker_aggregation_task(
            FlavonoidMarkerAggregationConfig(
                evidence_dir=Path(evidence_dir).expanduser(),
                outdir=Path(outdir).expanduser(),
                variant_calling_dir=variant_dir,
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


def run_langgraph_workflow_ui(
    evidence_dir: str,
    outdir: str,
    variant_calling_dir: str,
    use_llm_reviewer: bool,
    llm_config_path: str,
) -> tuple[str, str, str, str, list[list[str]], str, str, str, str, str]:
    warning_lines = []
    outdir_path = Path(outdir).expanduser()
    variant_dir = _optional_existing_dir(variant_calling_dir)
    if variant_calling_dir and variant_dir is None:
        warning_lines.append(
            "variant_calling_dir 不存在或留空，LangGraph workflow 将不接入 variant evidence: "
            f"{variant_calling_dir}"
        )
    try:
        result = run_flavonoid_marker_langgraph_task(
            FlavonoidMarkerLangGraphConfig(
                evidence_dir=Path(evidence_dir).expanduser(),
                outdir=outdir_path,
                variant_calling_dir=variant_dir,
                use_llm_reviewer=bool(use_llm_reviewer),
                llm_config=(
                    Path(llm_config_path).expanduser()
                    if use_llm_reviewer and llm_config_path
                    else None
                ),
            )
        )
        outputs = result.get("outputs", {})
        status = "LangGraph workflow 运行成功。"
        if use_llm_reviewer:
            status += f"\nLLM Reviewer requested with config path: {llm_config_path}"
        if isinstance(outputs, dict):
            status += (
                f"\ngraph_trace: {outputs.get('graph_trace')}"
                f"\nlanggraph_summary: {outputs.get('langgraph_summary')}"
                f"\nreport: {outputs.get('report')}"
            )
    except RuntimeError as exc:
        if "LangGraph is not installed" in str(exc):
            status = "LangGraph is not installed. Install with: pip install langgraph"
        else:
            status = f"LangGraph workflow 运行失败: {exc}"
            warning_lines.append(traceback.format_exc())
    except Exception as exc:
        status = f"LangGraph workflow 运行失败: {exc}"
        warning_lines.append(traceback.format_exc())

    return load_langgraph_outputs(
        outdir=outdir_path,
        status=status,
        warning_lines=warning_lines,
    )


def refresh_langgraph_outputs(
    outdir: str,
) -> tuple[str, str, str, str, list[list[str]], str, str, str, str, str]:
    return load_langgraph_outputs(
        outdir=Path(outdir).expanduser(),
        status="已刷新 LangGraph workflow 输出文件。",
        warning_lines=[],
    )


def run_lobster_benchmark_ui(
    evidence_dir: str,
    variant_calling_dir: str,
    internal_agent_outdir: str,
    outdir: str,
) -> tuple[str, str, str, list[list[str]], str, str]:
    warning_lines = []
    outdir_path = Path(outdir).expanduser()
    variant_dir = _optional_existing_dir(variant_calling_dir)
    if variant_calling_dir and variant_dir is None:
        warning_lines.append(
            "variant_calling_dir 不存在或留空，Lobster-style benchmark 将不接入 variant evidence: "
            f"{variant_calling_dir}"
        )
    internal_outdir_path = Path(internal_agent_outdir).expanduser()
    if not internal_outdir_path.exists():
        warning_lines.append(
            "internal_agent_outdir 不存在，comparison 中内部 LangGraph 输出维度可能显示 false: "
            f"{internal_agent_outdir}"
        )
    try:
        result = run_lobster_external_agent_benchmark_task(
            LobsterExternalAgentBenchmarkConfig(
                evidence_dir=Path(evidence_dir).expanduser(),
                variant_calling_dir=variant_dir,
                internal_agent_outdir=internal_outdir_path,
                outdir=outdir_path,
            )
        )
        outputs = result.get("outputs", {})
        status = "Lobster-style benchmark 运行成功。"
        if isinstance(outputs, dict):
            status += (
                f"\nlobster_style_agent_report: {outputs.get('lobster_style_agent_report')}"
                f"\ncomparison_matrix: {outputs.get('comparison_matrix')}"
                f"\nlobster_vs_internal_comparison: {outputs.get('lobster_vs_internal_comparison')}"
            )
    except Exception as exc:
        status = f"Lobster-style benchmark 运行失败: {exc}"
        warning_lines.append(traceback.format_exc())

    return load_lobster_benchmark_outputs(
        outdir=outdir_path,
        status=status,
        warning_lines=warning_lines,
    )


def refresh_lobster_benchmark_outputs(
    outdir: str,
) -> tuple[str, str, str, list[list[str]], str, str]:
    return load_lobster_benchmark_outputs(
        outdir=Path(outdir).expanduser(),
        status="已刷新 Lobster-style benchmark 输出文件。",
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

            gr.Markdown("## Candidate Variant Calling（候选区域变异检测）")
            gr.Markdown(
                "PASS variants can be prioritized for downstream marker review"
                "（PASS 位点可优先进入后续标记开发复核）。\n\n"
                "LowQual variants are retained for traceability but should not be "
                "directly prioritized（LowQual 位点仅作为可追溯候选记录保留，不应直接优先用于标记开发）。\n\n"
                "This result does not replace WGS/GBS population variant calling"
                "（当前结果不能替代 WGS/GBS 群体变异检测）。"
            )
            with gr.Row():
                with gr.Column():
                    variant_dataset_dir = gr.Textbox(
                        label="dataset_dir",
                        value=GENOMICS_VARIANT_DEFAULT_DATASET_DIR,
                    )
                    variant_calling_outdir = gr.Textbox(
                        label="variant_calling_outdir",
                        value=GENOMICS_VARIANT_DEFAULT_OUTDIR,
                    )
                    with gr.Row():
                        load_variant_demo = gr.Button("Load Demo Variant Calling")
                        run_variant_button = gr.Button(
                            "Run Variant Calling",
                            variant="primary",
                        )
                        refresh_variant_button = gr.Button("Refresh Variant Results")
                with gr.Column():
                    variant_status = gr.Textbox(label="Run Status", lines=8)
                    variant_quality_summary = gr.Markdown(
                        label="Variant Quality Summary"
                    )

            gr.Markdown("### candidate_variants.tsv")
            variant_candidate_table = gr.DataFrame(
                label="candidate_variants.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### snp_candidates.tsv")
            variant_snp_table = gr.DataFrame(
                label="snp_candidates.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### indel_candidates.tsv")
            variant_indel_table = gr.DataFrame(
                label="indel_candidates.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### kasp_candidate_sites.tsv")
            variant_kasp_table = gr.DataFrame(
                label="kasp_candidate_sites.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### caps_candidate_sites.tsv")
            variant_caps_table = gr.DataFrame(
                label="caps_candidate_sites.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### genomics_variant_calling_report.md")
            variant_report = gr.Markdown()
            variant_manifest = gr.Textbox(label="manifest.json", lines=16)
            variant_run_log = gr.Textbox(label="run.log", lines=18)

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
        load_variant_demo.click(
            fn=load_demo_variant_calling,
            outputs=[variant_dataset_dir, variant_calling_outdir],
        )
        variant_outputs = [
            variant_status,
            variant_quality_summary,
            variant_candidate_table,
            variant_snp_table,
            variant_indel_table,
            variant_kasp_table,
            variant_caps_table,
            variant_report,
            variant_manifest,
            variant_run_log,
        ]
        run_variant_button.click(
            fn=run_genomics_variant_calling_ui,
            inputs=[variant_dataset_dir, variant_calling_outdir],
            outputs=variant_outputs,
        )
        refresh_variant_button.click(
            fn=refresh_variant_calling_outputs,
            inputs=[variant_calling_outdir],
            outputs=variant_outputs,
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
                    flavonoid_variant_calling_dir = gr.Textbox(
                        label="variant_calling_dir",
                        value=GENOMICS_VARIANT_DEFAULT_OUTDIR,
                        placeholder=(
                            "Optional. Leave empty or point to a missing dir to run "
                            "without variant calling evidence."
                        ),
                    )
                    gr.Markdown(
                        "`variant_calling_dir` 为可选输入。目录存在时读取 "
                        "`candidate_variants.tsv`、`kasp_candidate_sites.tsv`、"
                        "`caps_candidate_sites.tsv` 并接入报告；留空或不存在时保持原流程。"
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

            gr.Markdown("## LangGraph Multi-agent Workflow（LangGraph 多智能体聚合流程）")
            gr.Markdown(
                "当前 LangGraph workflow 默认使用现有规则化 agents；勾选本地 LLM Reviewer "
                "时，仅增强 ReviewerAgent。"
                "LangGraph 用于编排 LiteratureAgent、MarkerRecommendationAgent、"
                "ValidationAgent、ReviewerAgent、FinalQAAgent。\n\n"
                "`graph_trace.json` 和 `node_decision_table.tsv` 用于追踪每个节点的"
                "输入、输出、证据、警告和限制。本地 LLM 只做审阅增强，不直接生成 "
                "SNP/InDel/KASP/CAPS 结论；输出仍经过 output_guard 和 FinalQAAgent，"
                "不通过会 fallback 到规则版 ReviewerAgent。当前结果仍不能替代 WGS/GBS "
                "群体变异检测；KASP/CAPS 表仍是 preliminary screening，不是最终引物或酶切方案。"
            )
            with gr.Row():
                with gr.Column():
                    langgraph_outdir = gr.Textbox(
                        label="langgraph_outdir",
                        value=FLAVONOID_LANGGRAPH_DEFAULT_OUTDIR,
                    )
                    langgraph_use_llm_reviewer = gr.Checkbox(
                        label="Use LLM Reviewer",
                        value=False,
                    )
                    langgraph_llm_config_path = gr.Textbox(
                        label="LLM Config Path",
                        value=FLAVONOID_LLM_CONFIG_DEFAULT,
                    )
                    with gr.Row():
                        run_langgraph_button = gr.Button(
                            "Run LangGraph Workflow",
                            variant="primary",
                        )
                        refresh_langgraph_button = gr.Button(
                            "Refresh LangGraph Results"
                        )
                with gr.Column():
                    langgraph_status = gr.Textbox(
                        label="LangGraph Run Status（运行状态）",
                        lines=8,
                    )
                    langgraph_qa_status = gr.Textbox(
                        label="LangGraph QA Status（QA 状态）",
                        lines=2,
                    )
                    langgraph_llm_status = gr.Textbox(
                        label="LLM Reviewer Status",
                        lines=7,
                    )

            gr.Markdown("### LangGraph Summary（LangGraph 摘要）")
            langgraph_summary = gr.Markdown()
            gr.Markdown("### Node Decision Table（节点决策表）")
            langgraph_node_decision_table = gr.DataFrame(
                label="node_decision_table.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### Final Report（最终报告）")
            langgraph_final_report = gr.Markdown()
            with gr.Accordion("Details", open=False):
                langgraph_graph_trace = gr.Textbox(
                    label="graph_trace.json",
                    lines=18,
                )
                langgraph_graph_state = gr.Textbox(
                    label="graph_state_final.json",
                    lines=18,
                )
                langgraph_qa_json = gr.Textbox(label="qa_check.json", lines=18)
                langgraph_manifest_json = gr.Textbox(label="manifest.json", lines=18)

            gr.Markdown("## Lobster-style External Omics Agent Benchmark")
            gr.Markdown(
                "当前不是 Lobster AI 真实运行结果，而是 Lobster-style reference benchmark "
                "/ mock_reference。它用于对比开源多组学 Agent 风格输出和本项目内部育种业务 "
                "Agent 输出，不替代当前 LangGraph 主流程，也不安装或调用 Lobster。"
            )
            with gr.Row():
                with gr.Column():
                    lobster_evidence_dir = gr.Textbox(
                        label="Evidence Dir",
                        value=FLAVONOID_DEFAULT_EVIDENCE_DIR,
                    )
                    lobster_variant_calling_dir = gr.Textbox(
                        label="Variant Calling Dir",
                        value=GENOMICS_VARIANT_DEFAULT_OUTDIR,
                    )
                    lobster_internal_agent_outdir = gr.Textbox(
                        label="Internal Agent Outdir",
                        value=FLAVONOID_INTERNAL_AGENT_DEFAULT_OUTDIR,
                    )
                    lobster_benchmark_outdir = gr.Textbox(
                        label="Lobster Benchmark Outdir",
                        value=FLAVONOID_LOBSTER_BENCHMARK_DEFAULT_OUTDIR,
                    )
                    with gr.Row():
                        run_lobster_benchmark_button = gr.Button(
                            "Run Lobster-style Benchmark",
                            variant="primary",
                        )
                        refresh_lobster_benchmark_button = gr.Button(
                            "Refresh Lobster Benchmark Results"
                        )
                with gr.Column():
                    lobster_benchmark_status = gr.Textbox(
                        label="benchmark status",
                        lines=8,
                    )
                    lobster_backend_metadata = gr.Textbox(
                        label="backend_name / backend_mode / real_lobster_run",
                        lines=6,
                    )

            gr.Markdown("### lobster_style_agent_report.md")
            lobster_style_report = gr.Markdown()
            gr.Markdown("### comparison_matrix.tsv")
            lobster_comparison_matrix = gr.DataFrame(
                label="comparison_matrix.tsv",
                headers=None,
                datatype="str",
                interactive=False,
                wrap=True,
            )
            gr.Markdown("### lobster_vs_internal_comparison.md")
            lobster_vs_internal_comparison = gr.Markdown()
            lobster_benchmark_manifest = gr.Textbox(
                label="benchmark_manifest.json",
                lines=18,
            )

        flavonoid_button_inputs = [
            flavonoid_dataset_dir,
            flavonoid_evidence_dir,
            flavonoid_outdir,
        ]
        flavonoid_recommendation_inputs = [
            flavonoid_dataset_dir,
            flavonoid_evidence_dir,
            flavonoid_outdir,
            flavonoid_variant_calling_dir,
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
            inputs=flavonoid_recommendation_inputs,
            outputs=flavonoid_outputs,
        )
        full_pipeline_button.click(
            fn=run_flavonoid_full_pipeline,
            inputs=flavonoid_recommendation_inputs,
            outputs=flavonoid_outputs,
        )
        refresh_flavonoid_button.click(
            fn=refresh_flavonoid_outputs,
            inputs=[flavonoid_outdir],
            outputs=flavonoid_outputs,
        )
        langgraph_outputs = [
            langgraph_status,
            langgraph_qa_status,
            langgraph_llm_status,
            langgraph_summary,
            langgraph_node_decision_table,
            langgraph_graph_trace,
            langgraph_graph_state,
            langgraph_final_report,
            langgraph_qa_json,
            langgraph_manifest_json,
        ]
        run_langgraph_button.click(
            fn=run_langgraph_workflow_ui,
            inputs=[
                flavonoid_evidence_dir,
                langgraph_outdir,
                flavonoid_variant_calling_dir,
                langgraph_use_llm_reviewer,
                langgraph_llm_config_path,
            ],
            outputs=langgraph_outputs,
        )
        refresh_langgraph_button.click(
            fn=refresh_langgraph_outputs,
            inputs=[langgraph_outdir],
            outputs=langgraph_outputs,
        )
        lobster_outputs = [
            lobster_benchmark_status,
            lobster_backend_metadata,
            lobster_style_report,
            lobster_comparison_matrix,
            lobster_vs_internal_comparison,
            lobster_benchmark_manifest,
        ]
        run_lobster_benchmark_button.click(
            fn=run_lobster_benchmark_ui,
            inputs=[
                lobster_evidence_dir,
                lobster_variant_calling_dir,
                lobster_internal_agent_outdir,
                lobster_benchmark_outdir,
            ],
            outputs=lobster_outputs,
        )
        refresh_lobster_benchmark_button.click(
            fn=refresh_lobster_benchmark_outputs,
            inputs=[lobster_benchmark_outdir],
            outputs=lobster_outputs,
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


def read_tsv_for_display(path: Path) -> list[list[str]]:
    """Read a small output TSV for Gradio display."""

    return _read_tsv_for_dataframe(path)


def read_text_file(path: Path) -> str:
    """Read a small output text file for Gradio display."""

    return _read_text(path)


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


def load_variant_calling_outputs(
    *,
    outdir: Path,
    status: str,
    warning_lines: list[str],
) -> tuple[
    str,
    str,
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    list[list[str]],
    str,
    str,
    str,
]:
    tables_dir = outdir / "tables"
    candidate_path = tables_dir / "candidate_variants.tsv"
    snp_path = tables_dir / "snp_candidates.tsv"
    indel_path = tables_dir / "indel_candidates.tsv"
    kasp_path = tables_dir / "kasp_candidate_sites.tsv"
    caps_path = tables_dir / "caps_candidate_sites.tsv"
    report_path = outdir / "reports" / "genomics_variant_calling_report.md"
    manifest_path = outdir / "manifest.json"
    run_log_path = outdir / "logs" / "run.log"

    required_outputs = [
        candidate_path,
        snp_path,
        indel_path,
        kasp_path,
        caps_path,
        report_path,
        manifest_path,
        run_log_path,
    ]
    missing_outputs = [path for path in required_outputs if not path.exists()]
    if missing_outputs:
        warning_lines.append(
            "尚未生成 candidate variant calling 结果，请先运行 Run Variant Calling。"
        )
        warning_lines.extend(f"Missing output: {path}" for path in missing_outputs)

    candidate_table = read_tsv_for_display(candidate_path)
    snp_table = read_tsv_for_display(snp_path)
    indel_table = read_tsv_for_display(indel_path)
    kasp_table = read_tsv_for_display(kasp_path)
    caps_table = read_tsv_for_display(caps_path)

    summary = summarize_variant_quality(
        manifest_path=manifest_path,
        candidate_table=candidate_table,
        snp_table=snp_table,
        indel_table=indel_table,
        kasp_table=kasp_table,
        caps_table=caps_table,
    )
    if warning_lines:
        status = status + "\n\nWarnings:\n" + "\n".join(warning_lines)

    return (
        status,
        summary,
        candidate_table,
        snp_table,
        indel_table,
        kasp_table,
        caps_table,
        read_text_file(report_path),
        _read_json_text(manifest_path),
        read_text_file(run_log_path),
    )


def load_langgraph_outputs(
    *,
    outdir: Path,
    status: str,
    warning_lines: list[str],
) -> tuple[str, str, str, str, list[list[str]], str, str, str, str, str]:
    graph_dir = outdir / "graph"
    summary_path = graph_dir / "langgraph_summary.md"
    decision_path = graph_dir / "node_decision_table.tsv"
    trace_path = graph_dir / "graph_trace.json"
    state_path = graph_dir / "graph_state_final.json"
    report_path = outdir / "reports" / "flavonoid_marker_report.md"
    qa_path = outdir / "logs" / "qa_check.json"
    manifest_path = outdir / "manifest.json"

    required_outputs = [
        summary_path,
        decision_path,
        trace_path,
        state_path,
        report_path,
        qa_path,
        manifest_path,
    ]
    missing_outputs = [path for path in required_outputs if not path.exists()]
    if missing_outputs:
        warning_lines.append(
            "尚未生成 LangGraph workflow 结果，请先点击 Run LangGraph Workflow。"
        )
        warning_lines.extend(f"Missing output: {path}" for path in missing_outputs)

    if warning_lines:
        status = status + "\n\nWarnings:\n" + "\n".join(warning_lines)

    return (
        status,
        _flavonoid_qa_status(qa_path),
        _format_llm_reviewer_status(
            trace_path=trace_path,
            state_path=state_path,
            manifest_path=manifest_path,
        ),
        read_text_file(summary_path),
        read_tsv_for_display(decision_path),
        _read_json_text(trace_path),
        _read_json_text(state_path),
        read_text_file(report_path),
        _read_json_text(qa_path),
        _read_json_text(manifest_path),
    )


def load_lobster_benchmark_outputs(
    *,
    outdir: Path,
    status: str,
    warning_lines: list[str],
) -> tuple[str, str, str, list[list[str]], str, str]:
    reference_dir = outdir / "lobster_reference"
    comparison_dir = outdir / "comparison"
    report_path = reference_dir / "lobster_style_agent_report.md"
    matrix_path = comparison_dir / "comparison_matrix.tsv"
    comparison_path = comparison_dir / "lobster_vs_internal_comparison.md"
    manifest_path = outdir / "logs" / "benchmark_manifest.json"

    required_outputs = [
        report_path,
        matrix_path,
        comparison_path,
        manifest_path,
    ]
    missing_outputs = [path for path in required_outputs if not path.exists()]
    if missing_outputs:
        warning_lines.append(
            "尚未生成 Lobster-style benchmark 结果，请先点击 Run Lobster-style Benchmark。"
        )
        warning_lines.extend(f"Missing output: {path}" for path in missing_outputs)

    if warning_lines:
        status = status + "\n\nWarnings:\n" + "\n".join(warning_lines)

    return (
        status,
        _format_lobster_backend_metadata(manifest_path),
        read_text_file(report_path),
        read_tsv_for_display(matrix_path),
        read_text_file(comparison_path),
        _read_json_text(manifest_path),
    )


def _format_lobster_backend_metadata(manifest_path: Path) -> str:
    manifest = _read_json_object(manifest_path)
    if not isinstance(manifest, dict):
        return (
            "backend_name: unknown\n"
            "backend_mode: unknown\n"
            "real_lobster_run: unknown\n"
            f"manifest: {manifest_path}"
        )
    ordered_keys = [
        "reference_project_name",
        "reference_project_url",
        "backend_name",
        "backend_mode",
        "real_lobster_run",
    ]
    lines = [f"{key}: {manifest.get(key, '')}" for key in ordered_keys]
    lines.append("Note: current result is Lobster-style reference benchmark, not a real Lobster AI run.")
    return "\n".join(lines)


def _format_llm_reviewer_status(
    *,
    trace_path: Path,
    state_path: Path,
    manifest_path: Path,
) -> str:
    metadata = _load_llm_reviewer_metadata(
        trace_path=trace_path,
        state_path=state_path,
        manifest_path=manifest_path,
    )
    if not metadata or not bool(metadata.get("llm_reviewer_enabled", False)):
        return "LLM Reviewer not enabled / 未启用本地大模型审阅"
    ordered_keys = [
        "llm_reviewer_enabled",
        "llm_used",
        "fallback_used",
        "model",
        "guard_passed",
        "fallback_reason",
    ]
    lines = [
        "LLM Reviewer enabled / 已启用本地大模型审阅",
        "Only ReviewerAgent is enhanced; SNP/InDel/KASP/CAPS conclusions are not generated by LLM.",
    ]
    lines.extend(f"{key}: {metadata.get(key, '')}" for key in ordered_keys)
    return "\n".join(lines)


def _load_llm_reviewer_metadata(
    *,
    trace_path: Path,
    state_path: Path,
    manifest_path: Path,
) -> dict[str, object]:
    trace = _read_json_object(trace_path)
    if isinstance(trace, list):
        for row in trace:
            if isinstance(row, dict) and row.get("node_name") == "reviewer_agent_node":
                metadata = _llm_metadata_from_mapping(row)
                if metadata:
                    return metadata

    state = _read_json_object(state_path)
    if isinstance(state, dict):
        metadata = _llm_metadata_from_mapping(state.get("llm_reviewer_metadata"))
        if metadata:
            return metadata
        agent_context = state.get("agent_context")
        if isinstance(agent_context, dict):
            metadata = _llm_metadata_from_mapping(
                agent_context.get("_llm_reviewer_metadata")
            )
            if metadata:
                return metadata

    manifest = _read_json_object(manifest_path)
    if isinstance(manifest, dict):
        metadata = _llm_metadata_from_mapping(manifest.get("llm_reviewer"))
        if metadata:
            return metadata
    return {}


def _llm_metadata_from_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    keys = [
        "llm_reviewer_enabled",
        "llm_used",
        "fallback_used",
        "model",
        "guard_passed",
        "fallback_reason",
    ]
    return {key: value.get(key) for key in keys if key in value}


def _read_json_object(path: Path) -> object:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def summarize_variant_quality(
    *,
    manifest_path: Path,
    candidate_table: list[list[str]],
    snp_table: list[list[str]],
    indel_table: list[list[str]],
    kasp_table: list[list[str]],
    caps_table: list[list[str]],
) -> str:
    counts = _variant_counts_from_manifest(manifest_path)
    if not counts:
        counts = _variant_counts_from_tables(
            candidate_table=candidate_table,
            snp_table=snp_table,
            indel_table=indel_table,
            kasp_table=kasp_table,
            caps_table=caps_table,
        )

    ordered_keys = [
        "candidate_variants",
        "snps",
        "indels",
        "pass_variants",
        "lowqual_variants",
        "pass_snps",
        "lowqual_snps",
        "pass_indels",
        "lowqual_indels",
        "kasp_preliminary_pass",
        "kasp_low_quality_review_required",
        "caps_pass_variant_requires_enzyme_screening",
        "caps_low_quality_variant_requires_review",
    ]
    lines = ["### Variant Quality Summary"]
    lines.extend(f"- `{key}`: {counts.get(key, 0)}" for key in ordered_keys)
    lines.extend(
        [
            "",
            "PASS variants can be prioritized for downstream marker review（PASS 位点可优先进入后续标记开发复核）。",
            "LowQual variants are retained for traceability but should not be directly prioritized（LowQual 位点仅作为可追溯候选记录保留，不应直接优先用于标记开发）。",
            "This result does not replace WGS/GBS population variant calling（当前结果不能替代 WGS/GBS 群体变异检测）。",
        ]
    )
    return "\n".join(lines)


def _variant_counts_from_manifest(manifest_path: Path) -> dict[str, int]:
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    counts = manifest.get("counts", {})
    if not isinstance(counts, dict):
        return {}
    return {
        str(key): int(value)
        for key, value in counts.items()
        if isinstance(value, int | float | str) and str(value).isdigit()
    }


def _variant_counts_from_tables(
    *,
    candidate_table: list[list[str]],
    snp_table: list[list[str]],
    indel_table: list[list[str]],
    kasp_table: list[list[str]],
    caps_table: list[list[str]],
) -> dict[str, int]:
    candidate_rows = _table_body(candidate_table)
    snp_rows = _table_body(snp_table)
    indel_rows = _table_body(indel_table)
    return {
        "candidate_variants": len(candidate_rows),
        "snps": len(snp_rows),
        "indels": len(indel_rows),
        "pass_variants": _count_table_value(candidate_table, "filter", "PASS"),
        "lowqual_variants": len(candidate_rows)
        - _count_table_value(candidate_table, "filter", "PASS"),
        "pass_snps": _count_table_value(snp_table, "filter", "PASS"),
        "lowqual_snps": len(snp_rows) - _count_table_value(snp_table, "filter", "PASS"),
        "pass_indels": _count_table_value(indel_table, "filter", "PASS"),
        "lowqual_indels": len(indel_rows)
        - _count_table_value(indel_table, "filter", "PASS"),
        "kasp_preliminary_pass": _count_table_value(
            kasp_table,
            "kasp_readiness",
            "preliminary_pass",
        ),
        "kasp_low_quality_review_required": _count_table_value(
            kasp_table,
            "kasp_readiness",
            "low_quality_review_required",
        ),
        "caps_pass_variant_requires_enzyme_screening": _count_table_value(
            caps_table,
            "caps_status",
            "pass_variant_requires_enzyme_screening",
        ),
        "caps_low_quality_variant_requires_review": _count_table_value(
            caps_table,
            "caps_status",
            "low_quality_variant_requires_review",
        ),
    }


def _table_body(table: list[list[str]]) -> list[list[str]]:
    if len(table) <= 1:
        return []
    return table[1:]


def _count_table_value(table: list[list[str]], column: str, value: str) -> int:
    if not table:
        return 0
    header = table[0]
    if column not in header:
        return 0
    index = header.index(column)
    return sum(1 for row in table[1:] if index < len(row) and row[index] == value)


def _optional_existing_dir(path_text: str) -> Path | None:
    if not path_text or not path_text.strip():
        return None
    path = Path(path_text).expanduser()
    if not path.exists() or not path.is_dir():
        return None
    return path


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
