"""Workflow orchestration for candidate-region genomics variant calling."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.modules.genomics.variant_calling import (
    CommandResult,
    build_variant_tables_from_vcf,
    call_candidate_region_variants,
    ensure_bam_indexes,
    ensure_reference_index,
    require_tools,
    validate_variant_calling_inputs,
)
from breeding_agent.reports.genomics_variant_report import (
    generate_genomics_variant_report,
)


DEFAULT_DATASET_DIR = "data/private/flavonoid_marker_mini_5genes_50kb"
DEFAULT_OUTDIR = "outputs/genomics_variant_calling"


@dataclass(frozen=True)
class GenomicsVariantCallingConfig:
    dataset_dir: Path = Path(DEFAULT_DATASET_DIR)
    bam_dir: Path | None = None
    reference_fasta: Path | None = None
    regions_bed: Path | None = None
    gff: Path | None = None
    outdir: Path = Path(DEFAULT_OUTDIR)


def run_genomics_variant_calling(
    config: GenomicsVariantCallingConfig,
) -> dict[str, object]:
    """Run candidate-region variant calling and write all outputs."""

    start_time = _utc_now()
    dataset_dir = config.dataset_dir.expanduser()
    outdir = config.outdir.expanduser()
    variants_dir = outdir / "variants"
    tables_dir = outdir / "tables"
    logs_dir = outdir / "logs"
    log_file = logs_dir / "run.log"
    manifest_file = outdir / "manifest.json"
    commands: list[CommandResult] = []
    warnings: list[str] = []

    bam_dir = (config.bam_dir or dataset_dir / "bam").expanduser()
    reference_fasta = (
        config.reference_fasta.expanduser()
        if config.reference_fasta
        else _default_reference(dataset_dir)
    )
    regions_bed = (
        config.regions_bed.expanduser()
        if config.regions_bed
        else dataset_dir / "regions" / "regions.bed"
    )
    gff = config.gff.expanduser() if config.gff else _default_gff(dataset_dir)

    inputs = {
        "dataset_dir": str(dataset_dir),
        "bam_dir": str(bam_dir),
        "reference_fasta": str(reference_fasta),
        "regions_bed": str(regions_bed),
        "gff": str(gff),
    }
    manifest: dict[str, object] = {
        "task_name": "genomics_variant_calling",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "inputs": inputs,
        "outputs": {},
        "commands": [],
        "warnings": warnings,
        "error_message": None,
    }

    outdir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    _append_log(log_file, f"[{start_time}] genomics variant calling started")

    try:
        tools = require_tools()
        manifest["tools"] = tools
        bam_files = validate_variant_calling_inputs(
            bam_dir=bam_dir,
            reference_fasta=reference_fasta,
            regions_bed=regions_bed,
        )
        ensure_reference_index(
            reference_fasta=reference_fasta,
            log_file=log_file,
            commands=commands,
        )
        ensure_bam_indexes(
            bam_files=bam_files,
            log_file=log_file,
            commands=commands,
        )
        vcf_outputs = call_candidate_region_variants(
            bam_files=bam_files,
            reference_fasta=reference_fasta,
            regions_bed=regions_bed,
            variants_dir=variants_dir,
            log_file=log_file,
            commands=commands,
        )
        table_result = build_variant_tables_from_vcf(
            vcf_path=vcf_outputs["filtered_vcf"],
            tables_dir=tables_dir,
            gff=gff,
            regions_bed=regions_bed,
        )

        result: dict[str, object] = {
            "task_name": "genomics_variant_calling",
            "inputs": inputs,
            "outputs": {
                **{key: str(value) for key, value in vcf_outputs.items()},
                **table_result["outputs"],  # type: ignore[arg-type]
                "run_log": str(log_file),
                "manifest": str(manifest_file),
            },
            "commands": [
                {"name": command.name, "command": command.rendered}
                for command in commands
            ],
            "warnings": warnings,
            "counts": table_result["counts"],
            "covered_target_genes": table_result["covered_target_genes"],
        }
        report_file = generate_genomics_variant_report(outdir=outdir, result=result)
        result["outputs"]["report"] = str(report_file)  # type: ignore[index]

        manifest["status"] = "success"
        manifest["outputs"] = result["outputs"]
        manifest["commands"] = result["commands"]
        manifest["counts"] = result["counts"]
        manifest["covered_target_genes"] = result["covered_target_genes"]
        return result
    except subprocess.CalledProcessError as exc:
        manifest["status"] = "failed"
        manifest["commands"] = [
            {"name": command.name, "command": command.rendered}
            for command in commands
        ]
        manifest["error_message"] = (
            f"Command failed with exit code {exc.returncode}: {' '.join(exc.cmd)}"
        )
        raise
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise
    finally:
        end_time = _utc_now()
        manifest["end_time"] = end_time
        _append_log(log_file, f"[{end_time}] workflow ended: {manifest['status']}")
        _write_json(manifest_file, manifest)


def run_genomics_variant_calling_task(
    config: GenomicsVariantCallingConfig,
) -> dict[str, object]:
    """Public workflow entry point shared by CLI and tests."""

    return run_genomics_variant_calling(config)


def _default_reference(dataset_dir: Path) -> Path:
    bam_compatible = dataset_dir / "genome.bam_compatible.fa.gz"
    if bam_compatible.exists():
        return bam_compatible
    return dataset_dir / "genome.fa"


def _default_gff(dataset_dir: Path) -> Path:
    original = dataset_dir / "genome.original_coords.gff"
    if original.exists():
        return original
    return dataset_dir / "genome.gff"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
