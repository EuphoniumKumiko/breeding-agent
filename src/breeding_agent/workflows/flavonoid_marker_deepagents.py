"""Workflow wrapper for optional Deep Agents flavonoid marker POC."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.deepagents.flavonoid_deepagents_poc import run_deepagents_poc
from breeding_agent.reports.flavonoid_marker_report import (
    generate_flavonoid_marker_report_from_agent_result,
)


DEFAULT_DEEPAGENTS_OUTDIR = "outputs/flavonoid_marker_deepagents"


@dataclass(frozen=True)
class FlavonoidMarkerDeepAgentsConfig:
    evidence_dir: Path
    outdir: Path = Path(DEFAULT_DEEPAGENTS_OUTDIR)
    variant_calling_dir: Path | None = None


def run_flavonoid_marker_deepagents_task(
    config: FlavonoidMarkerDeepAgentsConfig,
) -> dict[str, object]:
    """Run the optional Deep Agents POC and write reproducible artifacts."""

    start_time = _utc_now()
    outdir = config.outdir.expanduser().resolve()
    evidence_dir = config.evidence_dir.expanduser().resolve()
    variant_calling_dir = (
        config.variant_calling_dir.expanduser().resolve()
        if config.variant_calling_dir
        else None
    )
    manifest_path = outdir / "manifest.json"
    qa_path = outdir / "logs" / "qa_check.json"
    outdir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "task_name": "flavonoid_marker_deepagents_poc",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "evidence_dir": str(evidence_dir),
        "outdir": str(outdir),
        "variant_calling_dir": str(variant_calling_dir) if variant_calling_dir else None,
        "outputs": {},
        "warnings": [],
        "error_message": None,
        "agent_layer": {
            "mode": "deepagents_poc_rule_based_agents",
            "uses_llm": False,
            "uses_external_api": False,
            "uses_langgraph": False,
            "uses_deep_agents": True,
            "deepagents_role": "optional_harness_poc",
        },
    }

    try:
        poc_result = run_deepagents_poc(
            evidence_dir=evidence_dir,
            outdir=outdir,
            variant_calling_dir=variant_calling_dir,
        )
        agent_result = _as_dict(poc_result.get("agent_result"))
        report_path = generate_flavonoid_marker_report_from_agent_result(
            outdir=outdir,
            agent_result=agent_result,
        )
        qa_result = _as_dict(agent_result.get("qa_result"))
        _write_json(qa_path, qa_result)

        artifacts = _as_dict(poc_result.get("artifacts"))
        outputs: dict[str, str] = {
            "deepagents_trace": str(artifacts.get("deepagents_trace", "")),
            "deepagents_summary": str(artifacts.get("deepagents_summary", "")),
            "deepagents_decision_table": str(
                artifacts.get("deepagents_decision_table", "")
            ),
            "candidate_table": _path_text(agent_result.get("candidate_file")),
            "report": str(report_path.resolve()),
            "qa_check": str(qa_path.resolve()),
            "manifest": str(manifest_path.resolve()),
        }
        manifest["status"] = "success"
        manifest["warnings"] = [str(item) for item in _as_list(agent_result.get("warnings"))]
        manifest["outputs"] = outputs
        manifest["qa_result"] = qa_result
        manifest["deepagents_trace_steps"] = len(_as_list(poc_result.get("trace")))
        manifest["end_time"] = _utc_now()
        _write_json(manifest_path, manifest)
        _assert_output_paths_exist(outputs)
        return {
            "agent_result": agent_result,
            "trace": poc_result.get("trace", []),
            "decision_rows": poc_result.get("decision_rows", []),
            "outputs": outputs,
            "qa_result": qa_result,
        }
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise
    finally:
        if manifest.get("status") != "success":
            manifest["end_time"] = _utc_now()
            _write_json(manifest_path, manifest)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _path_text(value: object) -> str:
    if not value:
        return ""
    return str(Path(str(value)).expanduser().resolve())


def _assert_output_paths_exist(outputs: dict[str, str]) -> None:
    required_keys = [
        "deepagents_trace",
        "deepagents_summary",
        "deepagents_decision_table",
        "report",
        "qa_check",
        "manifest",
    ]
    missing = [
        f"{key}: {outputs.get(key, '')}"
        for key in required_keys
        if not outputs.get(key) or not Path(outputs[key]).exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Deep Agents POC output path(s) missing: " + "; ".join(missing)
        )


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []
