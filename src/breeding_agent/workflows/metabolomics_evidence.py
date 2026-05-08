"""Workflow for package-derived metabolomics evidence analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.modules.metabolomics.metabolomics_evidence import (
    build_metabolomics_evidence,
)
from breeding_agent.reports.metabolomics_report import generate_metabolomics_report


DEFAULT_OUTDIR = "outputs/gradio_metabolomics_run"


@dataclass(frozen=True)
class MetabolomicsEvidenceConfig:
    dataset_dir: Path
    outdir: Path = Path(DEFAULT_OUTDIR)


def run_metabolomics_evidence_analysis(
    config: MetabolomicsEvidenceConfig,
) -> dict[str, object]:
    """Run metabolomics evidence analysis and write outputs."""

    start_time = _utc_now()
    output_dir = config.outdir / "metabolomics"
    manifest_file = output_dir / "manifest.json"
    manifest: dict[str, object] = {
        "task_name": "metabolomics_evidence",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "dataset_dir": str(config.dataset_dir),
        "outdir": str(config.outdir),
        "outputs": {},
        "warnings": [],
        "error_message": None,
    }

    try:
        result = build_metabolomics_evidence(
            dataset_dir=config.dataset_dir,
            output_dir=output_dir,
        )
        report_file = generate_metabolomics_report(
            output_dir=output_dir,
            analysis_result=result,
        )
        result["outputs"]["report"] = str(report_file)  # type: ignore[index]
        result["outputs"]["manifest"] = str(manifest_file)  # type: ignore[index]

        manifest["status"] = "success"
        manifest["warnings"] = result["warnings"]
        manifest["outputs"] = result["outputs"]
        manifest["row_counts"] = result["row_counts"]
        return result
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise
    finally:
        manifest["end_time"] = _utc_now()
        _write_json(manifest_file, manifest)


def run_metabolomics_evidence_task(
    config: MetabolomicsEvidenceConfig,
) -> dict[str, object]:
    """Public entry point shared by tests and UI."""

    return run_metabolomics_evidence_analysis(config)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
