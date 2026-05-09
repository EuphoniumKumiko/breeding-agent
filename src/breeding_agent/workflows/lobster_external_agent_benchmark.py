"""Workflow for Lobster-style external omics agent benchmark."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.external_agents.lobster_comparison import (
    compare_lobster_reference_with_internal,
    write_comparison_outputs,
)
from breeding_agent.external_agents.lobster_reference_adapter import (
    build_lobster_reference_task,
    lobster_gene_assessments_to_rows,
    render_lobster_style_agent_report,
    run_lobster_style_reference_assessment,
)
from breeding_agent.external_agents.lobster_reference_schema import (
    BACKEND_MODE,
    BACKEND_NAME,
    REFERENCE_PROJECT_NAME,
    REFERENCE_PROJECT_URL,
)


DEFAULT_LOBSTER_BENCHMARK_OUTDIR = "outputs/lobster_external_agent_benchmark"


@dataclass(frozen=True)
class LobsterExternalAgentBenchmarkConfig:
    evidence_dir: Path
    outdir: Path = Path(DEFAULT_LOBSTER_BENCHMARK_OUTDIR)
    variant_calling_dir: Path | None = None
    internal_agent_outdir: Path | None = None


def run_lobster_external_agent_benchmark_task(
    config: LobsterExternalAgentBenchmarkConfig,
) -> dict[str, object]:
    """Run a deterministic Lobster-style reference benchmark."""

    evidence_dir = config.evidence_dir.expanduser().resolve()
    outdir = config.outdir.expanduser().resolve()
    variant_calling_dir = (
        config.variant_calling_dir.expanduser().resolve()
        if config.variant_calling_dir
        else None
    )
    internal_agent_outdir = (
        config.internal_agent_outdir.expanduser().resolve()
        if config.internal_agent_outdir
        else None
    )

    reference_dir = outdir / "lobster_reference"
    comparison_dir = outdir / "comparison"
    logs_dir = outdir / "logs"
    reference_dir.mkdir(parents=True, exist_ok=True)
    comparison_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    task = build_lobster_reference_task(
        evidence_dir=evidence_dir,
        variant_calling_dir=variant_calling_dir,
    )
    result = run_lobster_style_reference_assessment(
        evidence_dir=evidence_dir,
        variant_calling_dir=variant_calling_dir,
    )
    task_path = reference_dir / "lobster_reference_task.json"
    report_path = reference_dir / "lobster_style_agent_report.md"
    assessments_path = reference_dir / "lobster_style_gene_assessments.tsv"
    manifest_path = logs_dir / "benchmark_manifest.json"

    _write_json(task_path, task.to_dict())
    report_path.write_text(render_lobster_style_agent_report(result), encoding="utf-8")
    _write_tsv(
        assessments_path,
        [
            "gene_id",
            "transcriptomics_support",
            "metabolomics_support",
            "annotation_support",
            "literature_support",
            "variant_support",
            "general_omics_interpretation",
            "marker_recommendation",
            "validation_required",
            "limitations",
            "warnings",
            "confidence_label",
        ],
        lobster_gene_assessments_to_rows(result),
    )

    comparisons = compare_lobster_reference_with_internal(
        lobster_result=result,
        internal_agent_outdir=internal_agent_outdir or outdir,
    )
    comparison_outputs = write_comparison_outputs(
        outdir=outdir,
        lobster_result=result,
        comparisons=comparisons,
    )
    outputs = {
        "lobster_reference_task": str(task_path),
        "lobster_style_agent_report": str(report_path),
        "lobster_style_gene_assessments": str(assessments_path),
        "comparison_matrix": str(comparison_outputs["comparison_matrix"]),
        "lobster_vs_internal_comparison": str(
            comparison_outputs["lobster_vs_internal_comparison"]
        ),
        "benchmark_manifest": str(manifest_path),
    }
    manifest = {
        "task_name": "lobster_external_agent_benchmark",
        "status": "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reference_project_name": REFERENCE_PROJECT_NAME,
        "reference_project_url": REFERENCE_PROJECT_URL,
        "backend_name": BACKEND_NAME,
        "backend_mode": BACKEND_MODE,
        "real_lobster_run": False,
        "evidence_dir": str(evidence_dir),
        "variant_calling_dir": str(variant_calling_dir) if variant_calling_dir else None,
        "internal_agent_outdir": (
            str(internal_agent_outdir) if internal_agent_outdir else None
        ),
        "outdir": str(outdir),
        "outputs": outputs,
        "warnings": list(result.warnings),
        "limitations": list(result.limitations),
    }
    _write_json(manifest_path, manifest)
    return {
        "outputs": outputs,
        "manifest": manifest,
        "lobster_result": result.to_dict(),
        "comparisons": [item.to_dict() for item in comparisons],
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
