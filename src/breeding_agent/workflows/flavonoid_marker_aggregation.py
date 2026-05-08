"""Workflow orchestration for flavonoid marker evidence aggregation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.agents.flavonoid_central_host import (
    FlavonoidCentralHost,
)
from breeding_agent.reports.flavonoid_marker_report import (
    generate_flavonoid_marker_report_from_agent_result,
)


DEFAULT_OUTDIR = "outputs/flavonoid_marker_from_package"


@dataclass(frozen=True)
class FlavonoidMarkerAggregationConfig:
    evidence_dir: Path
    outdir: Path = Path(DEFAULT_OUTDIR)
    target_genes: list[str] | None = None


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
        agent_result = FlavonoidCentralHost(
            evidence_dir=evidence_dir,
            outdir=outdir,
            target_genes=config.target_genes,
        ).run()
        warnings = [str(warning) for warning in agent_result["warnings"]]
        for warning in warnings:
            print(f"[flavonoid-markers:warning] {warning}", flush=True)

        report_file = generate_flavonoid_marker_report_from_agent_result(
            outdir=outdir,
            agent_result=agent_result,
        )
        qa_result = agent_result["qa_result"]
        _write_json(qa_file, qa_result)

        manifest["status"] = "success"
        manifest["warnings"] = warnings
        manifest["outputs"] = {
            "candidate_table": str(agent_result["candidate_file"]),
            "report": str(report_file),
            "qa_check": str(qa_file),
            "manifest": str(manifest_file),
        }
        manifest["agent_layer"] = agent_result["agent_layer"]
        print(
            f"[flavonoid-markers] candidates: {agent_result['candidate_file']}",
            flush=True,
        )
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
