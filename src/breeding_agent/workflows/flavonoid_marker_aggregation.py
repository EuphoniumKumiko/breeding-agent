"""Workflow orchestration for flavonoid marker evidence aggregation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.integration.flavonoid_marker_aggregator import (
    aggregate_flavonoid_marker_candidates,
)
from breeding_agent.integration.flavonoid_marker_qa import (
    check_flavonoid_marker_report,
)
from breeding_agent.reports.flavonoid_marker_report import (
    generate_flavonoid_marker_report,
)


DEFAULT_OUTDIR = "outputs/flavonoid_marker_from_package"


@dataclass(frozen=True)
class FlavonoidMarkerAggregationConfig:
    evidence_dir: Path
    outdir: Path = Path(DEFAULT_OUTDIR)


def run_flavonoid_marker_aggregation(
    config: FlavonoidMarkerAggregationConfig,
) -> Path:
    """Run aggregation, report generation, QA, and manifest writing."""

    start_time = _utc_now()
    outdir = config.outdir
    evidence_dir = config.evidence_dir
    qa_file = outdir / "logs" / "qa_check.json"
    manifest_file = outdir / "manifest.json"

    manifest: dict[str, object] = {
        "task_name": "flavonoid_marker_aggregation",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "evidence_dir": str(evidence_dir),
        "outdir": str(outdir),
        "outputs": {},
        "warnings": [],
        "error_message": None,
    }

    print("[flavonoid-markers] Starting aggregation workflow", flush=True)
    print(f"[flavonoid-markers] evidence-dir: {evidence_dir}", flush=True)
    print(f"[flavonoid-markers] outdir: {outdir}", flush=True)

    outdir.mkdir(parents=True, exist_ok=True)
    qa_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = aggregate_flavonoid_marker_candidates(
            evidence_dir=evidence_dir,
            outdir=outdir,
        )
        for warning in result.warnings:
            print(f"[flavonoid-markers:warning] {warning}", flush=True)

        report_file = generate_flavonoid_marker_report(
            outdir=outdir,
            evidence_dir=evidence_dir,
            candidate_rows=result.candidate_rows,
            literature_rows=result.literature_rows,
            warnings=result.warnings,
        )
        qa_result = check_flavonoid_marker_report(
            report_file.read_text(encoding="utf-8")
        )
        _write_json(qa_file, qa_result)
        report_file = generate_flavonoid_marker_report(
            outdir=outdir,
            evidence_dir=evidence_dir,
            candidate_rows=result.candidate_rows,
            literature_rows=result.literature_rows,
            warnings=result.warnings,
            qa_result=qa_result,
        )

        manifest["status"] = "success"
        manifest["warnings"] = result.warnings
        manifest["outputs"] = {
            "candidate_table": str(result.candidate_file),
            "report": str(report_file),
            "qa_check": str(qa_file),
            "manifest": str(manifest_file),
        }
        print(f"[flavonoid-markers] candidates: {result.candidate_file}", flush=True)
        print(f"[flavonoid-markers] report: {report_file}", flush=True)
        print(f"[flavonoid-markers] qa_check: {qa_file}", flush=True)
        print(
            f"[flavonoid-markers] qa passed: {qa_result.get('passed')}",
            flush=True,
        )
        return report_file
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise
    finally:
        manifest["end_time"] = _utc_now()
        _write_json(manifest_file, manifest)


def run_flavonoid_marker_aggregation_task(
    config: FlavonoidMarkerAggregationConfig,
) -> Path:
    """Public workflow entry point shared by CLI and future UIs."""

    return run_flavonoid_marker_aggregation(config)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
