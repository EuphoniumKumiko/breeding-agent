"""Mini RNA-seq DEG workflow orchestration."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from breeding_agent.core.command_runner import format_command, run_command
from breeding_agent.core.reproducibility import write_reproducibility_bundle
from breeding_agent.integration.candidate_aggregator import generate_candidate_gene_table
from breeding_agent.integration.recommendation_report import generate_recommendation_report
from breeding_agent.integration.transcriptomics_standardizer import (
    standardize_transcriptomics_deg,
)
from breeding_agent.reports.deg_report import DegReportConfig, generate_deg_report
from breeding_agent.validators.bam_validator import validate_bam_dir
from breeding_agent.validators.gff_validator import validate_gff
from breeding_agent.validators.tool_validator import validate_tools
from breeding_agent.validators.validation_result import ValidationResult


DEFAULT_GFF = "genome.original_coords.gff"
DEFAULT_CONTRAST = "JM-LM"
DEFAULT_PREFIX = "JM_vs_LM.mini"
DEFAULT_THREADS = 4
DEFAULT_OUTDIR = "outputs/demo_cli_run"
COUNTS_FILENAME = "gene_counts_mini.txt"


@dataclass(frozen=True)
class RnaSeqDegConfig:
    bam_dir: Path
    gff: Path = Path(DEFAULT_GFF)
    contrast: str = DEFAULT_CONTRAST
    prefix: str = DEFAULT_PREFIX
    trait: str = "unknown"
    threads: int = DEFAULT_THREADS
    outdir: Path = Path(DEFAULT_OUTDIR)


def find_bam_files(bam_dir: Path) -> list[Path]:
    """Find mini BAM files first, then all BAM files as a fallback."""

    if not bam_dir.exists():
        raise FileNotFoundError(f"bam-dir does not exist: {bam_dir}")
    if not bam_dir.is_dir():
        raise NotADirectoryError(f"bam-dir is not a directory: {bam_dir}")

    mini_bams = sorted(bam_dir.glob("*.mini.sorted.bam"))
    if mini_bams:
        return mini_bams

    return sorted(bam_dir.glob("*.bam"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _r_script_path() -> Path:
    return (
        _repo_root()
        / "workflows"
        / "rnaseq_deg"
        / "R"
        / "differential_expression_limma_voom.R"
    )


def _ensure_inputs(config: RnaSeqDegConfig, bam_files: Iterable[Path]) -> list[Path]:
    bam_files = list(bam_files)
    if not bam_files:
        raise FileNotFoundError(
            f"No BAM files found in {config.bam_dir} "
            "(*.mini.sorted.bam first, then *.bam)."
        )
    if not config.gff.exists():
        raise FileNotFoundError(f"GFF file does not exist: {config.gff}")

    r_script = _r_script_path()
    if not r_script.exists():
        raise FileNotFoundError(f"R script does not exist: {r_script}")

    return bam_files


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_run_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")


def _write_manifest(manifest_file: Path, manifest: dict[str, object]) -> None:
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with manifest_file.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _validate_workflow_inputs(config: RnaSeqDegConfig) -> ValidationResult:
    result = ValidationResult()
    result.extend(validate_bam_dir(config.bam_dir))
    result.extend(validate_gff(config.gff))
    result.extend(validate_tools())
    return result


def run_rnaseq_deg(config: RnaSeqDegConfig) -> Path:
    """Run featureCounts and limma-voom DEG analysis for the mini dataset."""

    start_time = _utc_now()
    log_file = config.outdir / "logs" / "run.log"
    manifest_file = config.outdir / "manifest.json"
    counts_dir = config.outdir / "counts"
    de_dir = config.outdir / "mini_de"
    counts_file = counts_dir / COUNTS_FILENAME
    significant_genes = de_dir / f"{config.prefix}.significant_genes.tsv"
    report_file = config.outdir / "reports" / "report.md"
    standardized_evidence = config.outdir / "integration" / "standardized_evidence.tsv"
    candidate_gene_table = config.outdir / "integration" / "candidate_gene_table.tsv"
    recommendation_report = config.outdir / "integration" / "recommendation_report.md"
    commands_sh = config.outdir / "provenance" / "commands.sh"
    checksums_sha256 = config.outdir / "provenance" / "checksums.sha256"
    commands: list[dict[str, str]] = []
    manifest: dict[str, object] = {
        "task_name": "rnaseq_deg",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "bam_dir": str(config.bam_dir),
        "gff": str(config.gff),
        "contrast": config.contrast,
        "prefix": config.prefix,
        "trait": config.trait,
        "threads": config.threads,
        "outdir": str(config.outdir),
        "commands": commands,
        "outputs": {
            "counts": str(counts_file),
            "significant_genes": str(significant_genes),
            "run_log": str(log_file),
            "report": str(report_file),
            "standardized_evidence": str(standardized_evidence),
            "candidate_gene_table": str(candidate_gene_table),
            "recommendation_report": str(recommendation_report),
            "commands_sh": str(commands_sh),
            "checksums_sha256": str(checksums_sha256),
        },
        "error_message": None,
    }

    print("[deg] Starting mini RNA-seq DEG workflow", flush=True)
    print(f"[deg] bam-dir: {config.bam_dir}", flush=True)
    print(f"[deg] gff: {config.gff}", flush=True)
    print(f"[deg] contrast: {config.contrast}", flush=True)
    print(f"[deg] prefix: {config.prefix}", flush=True)
    print(f"[deg] trait: {config.trait}", flush=True)
    print(f"[deg] threads: {config.threads}", flush=True)
    print(f"[deg] outdir: {config.outdir}", flush=True)
    if config.contrast == "JM-LM":
        print("[deg] contrast JM-LM: logFC < 0 means LM higher expression", flush=True)

    config.outdir.mkdir(parents=True, exist_ok=True)
    _append_run_log(log_file, f"[{start_time}] workflow started")

    try:
        validation = _validate_workflow_inputs(config)
        for warning in validation.warnings:
            print(f"[deg:warning] {warning}", flush=True)
            _append_run_log(log_file, f"[warning] {warning}")
        if validation.errors:
            for error in validation.errors:
                print(f"[deg:error] {error}", flush=True)
                _append_run_log(log_file, f"[error] {error}")
            raise ValueError("Input validation failed.")

        bam_files = _ensure_inputs(config, find_bam_files(config.bam_dir))
        print(f"[deg] Found {len(bam_files)} BAM file(s)", flush=True)
        for bam in bam_files:
            print(f"[deg]   {bam}", flush=True)

        counts_dir.mkdir(parents=True, exist_ok=True)
        de_dir.mkdir(parents=True, exist_ok=True)

        featurecounts_command = [
            "featureCounts",
            "-T",
            str(config.threads),
            "-p",
            "-t",
            "exon",
            "-g",
            "Parent",
            "-a",
            str(config.gff),
            "-o",
            str(counts_file),
            *[str(bam) for bam in bam_files],
        ]
        commands.append(
            {"name": "featureCounts", "command": format_command(featurecounts_command)}
        )
        print(f"[deg] Running featureCounts -> {counts_file}", flush=True)
        run_command(featurecounts_command, log_file=log_file)

        r_script = _r_script_path()
        r_command = [
            "Rscript",
            str(r_script),
            "--counts",
            str(counts_file),
            "--outdir",
            str(de_dir),
            "--prefix",
            config.prefix,
            "--contrast",
            config.contrast,
            "--fdr",
            "0.05",
            "--lfc",
            "1",
            "--min-count",
            "10",
            "--min-samples",
            "3",
        ]
        commands.append({"name": "Rscript", "command": format_command(r_command)})
        print(f"[deg] Running limma-voom R workflow -> {de_dir}", flush=True)
        run_command(r_command, log_file=log_file)

        print(f"[deg] Checking result: {significant_genes}", flush=True)
        if not significant_genes.exists():
            raise FileNotFoundError(
                f"Expected significant genes file was not created: {significant_genes}"
            )

        print(f"[deg] Generating report -> {report_file}", flush=True)
        generate_deg_report(
            DegReportConfig(
                task_name="rnaseq_deg",
                bam_dir=config.bam_dir,
                gff=config.gff,
                contrast=config.contrast,
                prefix=config.prefix,
                outdir=config.outdir,
                counts_file=counts_file,
                significant_genes_file=significant_genes,
                manifest_file=manifest_file,
                run_log_file=log_file,
            )
        )

        print(f"[deg] Standardizing evidence -> {standardized_evidence}", flush=True)
        standardize_transcriptomics_deg(
            outdir=config.outdir,
            prefix=config.prefix,
            contrast=config.contrast,
            trait=config.trait,
        )

        print(f"[deg] Aggregating candidates -> {candidate_gene_table}", flush=True)
        generate_candidate_gene_table(outdir=config.outdir)

        print(f"[deg] Generating recommendation report -> {recommendation_report}", flush=True)
        generate_recommendation_report(outdir=config.outdir)

        manifest["status"] = "success"
        print("[deg] Workflow finished successfully", flush=True)
        return significant_genes
    except subprocess.CalledProcessError as exc:
        manifest["status"] = "failed"
        manifest["error_message"] = (
            f"Command failed with exit code {exc.returncode}: "
            f"{format_command(exc.cmd)}"
        )
        raise
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise
    finally:
        end_time = _utc_now()
        manifest["end_time"] = end_time
        _append_run_log(log_file, f"[{end_time}] workflow ended: {manifest['status']}")
        _write_manifest(manifest_file, manifest)
        if manifest["status"] == "success":
            write_reproducibility_bundle(
                outdir=config.outdir,
                commands=commands,
                checksum_files=[
                    config.gff,
                    counts_file,
                    significant_genes,
                    standardized_evidence,
                    candidate_gene_table,
                    recommendation_report,
                    report_file,
                    manifest_file,
                ],
            )


def run_rnaseq_deg_task(config: RnaSeqDegConfig) -> Path:
    """Public workflow entry point shared by CLI and Web UI."""

    return run_rnaseq_deg(config)
