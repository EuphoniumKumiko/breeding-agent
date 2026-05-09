"""Workflow wrapper for optional LangGraph flavonoid marker recommendation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.graphs.flavonoid_marker_graph import (
    build_flavonoid_marker_graph,
    initial_graph_state,
)
from breeding_agent.reports.langgraph_trace_report import (
    write_langgraph_trace_reports,
)


DEFAULT_LANGGRAPH_OUTDIR = "outputs/flavonoid_marker_langgraph"


@dataclass(frozen=True)
class FlavonoidMarkerLangGraphConfig:
    evidence_dir: Path
    outdir: Path = Path(DEFAULT_LANGGRAPH_OUTDIR)
    variant_calling_dir: Path | None = None
    target_genes: list[str] | None = None


def run_flavonoid_marker_langgraph_task(
    config: FlavonoidMarkerLangGraphConfig,
) -> dict[str, object]:
    """Run the optional LangGraph workflow and write graph artifacts."""

    start_time = _utc_now()
    outdir = config.outdir
    manifest_path = outdir / "manifest.json"
    outdir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "task_name": "flavonoid_marker_langgraph",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "evidence_dir": str(config.evidence_dir),
        "outdir": str(outdir),
        "variant_calling_dir": (
            str(config.variant_calling_dir) if config.variant_calling_dir else None
        ),
        "outputs": {},
        "warnings": [],
        "error_message": None,
        "agent_layer": {
            "mode": "langgraph_rule_based_agents",
            "uses_llm": False,
            "uses_external_api": False,
            "uses_deep_agents": False,
            "uses_langgraph": True,
        },
    }

    try:
        graph = build_flavonoid_marker_graph()
        initial_state = initial_graph_state(
            evidence_dir=config.evidence_dir,
            outdir=outdir,
            variant_calling_dir=config.variant_calling_dir,
            target_genes=config.target_genes,
        )
        final_state = graph.invoke(initial_state)
        trace_outputs = write_langgraph_trace_reports(
            outdir=outdir,
            final_state=final_state,
        )
        outputs = {
            "candidate_table": final_state.get("candidate_table_path"),
            "report": final_state.get("report_path"),
            "qa_check": str(outdir / "logs" / "qa_check.json"),
            "manifest": str(manifest_path),
            **{key: str(value) for key, value in trace_outputs.items()},
        }
        manifest["status"] = "success"
        manifest["outputs"] = outputs
        manifest["warnings"] = final_state.get("warnings", [])
        manifest["qa_result"] = final_state.get("qa_result", {})
        manifest["graph_trace_nodes"] = len(final_state.get("graph_trace", []))
        result: dict[str, object] = {
            "final_state": final_state,
            "outputs": outputs,
            "qa_result": final_state.get("qa_result", {}),
        }
        return result
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise
    finally:
        manifest["end_time"] = _utc_now()
        _write_json(manifest_path, manifest)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
