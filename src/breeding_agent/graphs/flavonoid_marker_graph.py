"""Optional LangGraph workflow for flavonoid marker recommendation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from breeding_agent.agents.context_builder import build_flavonoid_agent_context
from breeding_agent.agents.flavonoid_final_qa_agent import FlavonoidFinalQAAgent
from breeding_agent.agents.flavonoid_literature_agent import (
    FlavonoidLiteratureAgent,
)
from breeding_agent.agents.flavonoid_marker_recommendation_agent import (
    FlavonoidMarkerRecommendationAgent,
)
from breeding_agent.agents.flavonoid_reviewer_agent import FlavonoidReviewerAgent
from breeding_agent.agents.flavonoid_validation_agent import FlavonoidValidationAgent
from breeding_agent.graphs.state import FlavonoidGraphState
from breeding_agent.integration.flavonoid_marker_aggregator import (
    ANNOTATION_EVIDENCE,
    GENOME_VARIANT_EVIDENCE,
    LITERATURE_EVIDENCE,
    METABOLOME_EVIDENCE,
    REQUIRED_GENE_IDS,
    TRANSCRIPTOME_EVIDENCE,
    aggregate_flavonoid_marker_candidates,
)
from breeding_agent.reports.flavonoid_marker_report import (
    render_flavonoid_marker_report,
)


LANGGRAPH_INSTALL_MESSAGE = (
    "LangGraph is not installed. Install with: pip install langgraph"
)


def build_flavonoid_marker_graph():
    """Build the LangGraph StateGraph app, importing langgraph lazily."""

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError(LANGGRAPH_INSTALL_MESSAGE) from exc

    graph = StateGraph(FlavonoidGraphState)
    graph.add_node("load_evidence_node", load_evidence_node)
    graph.add_node("aggregate_candidates_node", aggregate_candidates_node)
    graph.add_node("build_agent_context_node", build_agent_context_node)
    graph.add_node("literature_agent_node", literature_agent_node)
    graph.add_node("marker_recommendation_agent_node", marker_recommendation_agent_node)
    graph.add_node("validation_agent_node", validation_agent_node)
    graph.add_node("reviewer_agent_node", reviewer_agent_node)
    graph.add_node("final_qa_agent_node", final_qa_agent_node)
    graph.add_node("report_node", report_node)
    graph.add_node("write_outputs_node", write_outputs_node)

    graph.add_edge(START, "load_evidence_node")
    graph.add_edge("load_evidence_node", "aggregate_candidates_node")
    graph.add_edge("aggregate_candidates_node", "build_agent_context_node")
    graph.add_edge("build_agent_context_node", "literature_agent_node")
    graph.add_edge("literature_agent_node", "marker_recommendation_agent_node")
    graph.add_edge("marker_recommendation_agent_node", "validation_agent_node")
    graph.add_edge("validation_agent_node", "reviewer_agent_node")
    graph.add_edge("reviewer_agent_node", "final_qa_agent_node")
    graph.add_edge("final_qa_agent_node", "report_node")
    graph.add_edge("report_node", "write_outputs_node")
    graph.add_edge("write_outputs_node", END)
    return graph.compile()


def load_evidence_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    evidence_dir = Path(str(state["evidence_dir"]))
    warnings = _warnings(state)
    required = [
        TRANSCRIPTOME_EVIDENCE,
        METABOLOME_EVIDENCE,
        ANNOTATION_EVIDENCE,
        GENOME_VARIANT_EVIDENCE,
        LITERATURE_EVIDENCE,
    ]
    missing = [name for name in required if not (evidence_dir / name).exists()]
    warnings.extend(f"Evidence file missing: {evidence_dir / name}" for name in missing)
    state["warnings"] = warnings
    state.setdefault("target_genes", list(REQUIRED_GENE_IDS))
    _append_trace(
        state,
        node_name="load_evidence_node",
        input_summary=f"evidence_dir={evidence_dir}",
        output_summary=f"checked={len(required)} missing={len(missing)}",
        warnings=[f"missing={name}" for name in missing],
        limitations=["Validates evidence file presence only; parsing happens downstream."],
    )
    return state


def aggregate_candidates_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    result = aggregate_flavonoid_marker_candidates(
        evidence_dir=Path(str(state["evidence_dir"])),
        outdir=Path(str(state["outdir"])),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
    )
    warnings = _warnings(state)
    warnings.extend(str(warning) for warning in result.warnings)
    state["warnings"] = warnings
    state["candidate_table_path"] = str(result.candidate_file)
    state["candidate_rows"] = result.candidate_rows
    state["literature_rows"] = result.literature_rows
    state["_variant_evidence_rows"] = result.variant_evidence_rows  # type: ignore[typeddict-unknown-key]
    _append_trace(
        state,
        node_name="aggregate_candidates_node",
        input_summary=f"evidence_dir={state['evidence_dir']}",
        output_summary=f"candidate_rows={len(result.candidate_rows)}",
        warnings=result.warnings,
        limitations=["Uses existing rule-based aggregator; no marker position fabrication."],
    )
    return state


def build_agent_context_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    context = build_flavonoid_agent_context(
        evidence_dir=Path(str(state["evidence_dir"])),
        candidate_rows=state.get("candidate_rows", []),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
        variant_evidence_rows=state.get("_variant_evidence_rows", []),  # type: ignore[typeddict-item]
        warnings=state.get("warnings", []),
    )
    state["agent_context"] = context
    _append_trace(
        state,
        node_name="build_agent_context_node",
        input_summary="candidate rows and evidence TSV paths",
        output_summary=(
            "context keys="
            + ",".join(sorted(key for key in context.keys() if not key.startswith("_")))
        ),
        warnings=context.get("warnings", []),
        limitations=["Builds structured context only; no LLM call."],
    )
    return state


def literature_agent_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    output = FlavonoidLiteratureAgent(Path(str(state["evidence_dir"]))).run_with_context(
        state["agent_context"]
    )
    payload = output.structured_payload
    state["literature_rows"] = _rows(payload.get("literature_rows", []))
    state["literature_review_text"] = str(payload.get("literature_review_text", ""))
    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="literature_agent_node",
        input_summary="literature_evidence rows",
        output=output.to_dict(),
    )
    return state


def marker_recommendation_agent_node(
    state: FlavonoidGraphState,
) -> FlavonoidGraphState:
    output = FlavonoidMarkerRecommendationAgent().run_with_context(
        state["agent_context"]
    )
    payload = output.structured_payload
    state["marker_recommendation_text"] = str(
        payload.get("marker_recommendation_text", "")
    )
    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="marker_recommendation_agent_node",
        input_summary="candidate rows with variant status",
        output=output.to_dict(),
    )
    return state


def validation_agent_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    output = FlavonoidValidationAgent().run_with_context(state["agent_context"])
    payload = output.structured_payload
    state["validation_plan_text"] = str(payload.get("validation_plan_text", ""))
    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="validation_agent_node",
        input_summary="candidate genes",
        output=output.to_dict(),
    )
    return state


def reviewer_agent_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    draft_report = render_flavonoid_marker_report(
        evidence_dir=Path(str(state["evidence_dir"])),
        candidate_rows=state.get("candidate_rows", []),
        literature_rows=state.get("literature_rows", []),
        warnings=state.get("warnings", []),
        literature_review_text=state.get("literature_review_text", ""),
        marker_recommendation_text=state.get("marker_recommendation_text", ""),
        validation_plan_text=state.get("validation_plan_text", ""),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
    )
    context = {
        **state.get("agent_context", {}),
        "literature_review_text": state.get("literature_review_text", ""),
        "marker_recommendation_text": state.get("marker_recommendation_text", ""),
        "validation_plan_text": state.get("validation_plan_text", ""),
        "report_text": draft_report,
    }
    output = FlavonoidReviewerAgent().run_with_context(context)
    payload = output.structured_payload
    state["reviewer_notes"] = str(payload.get("reviewer_notes", ""))
    state["reviewer_warnings"] = [str(item) for item in payload.get("issues", [])]
    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="reviewer_agent_node",
        input_summary="draft report without reviewer notes",
        output=output.to_dict(),
    )
    return state


def final_qa_agent_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    report_without_qa = render_flavonoid_marker_report(
        evidence_dir=Path(str(state["evidence_dir"])),
        candidate_rows=state.get("candidate_rows", []),
        literature_rows=state.get("literature_rows", []),
        warnings=state.get("warnings", []),
        literature_review_text=state.get("literature_review_text", ""),
        marker_recommendation_text=state.get("marker_recommendation_text", ""),
        validation_plan_text=state.get("validation_plan_text", ""),
        reviewer_notes=state.get("reviewer_notes", ""),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
    )
    output = FlavonoidFinalQAAgent().run_with_context(
        {**state.get("agent_context", {}), "report_text": report_without_qa}
    )
    state["qa_result"] = output.structured_payload
    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="final_qa_agent_node",
        input_summary="report text without QA section",
        output=output.to_dict(),
    )
    return state


def report_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    report_text = render_flavonoid_marker_report(
        evidence_dir=Path(str(state["evidence_dir"])),
        candidate_rows=state.get("candidate_rows", []),
        literature_rows=state.get("literature_rows", []),
        warnings=state.get("warnings", []),
        literature_review_text=state.get("literature_review_text", ""),
        marker_recommendation_text=state.get("marker_recommendation_text", ""),
        validation_plan_text=state.get("validation_plan_text", ""),
        reviewer_notes=state.get("reviewer_notes", ""),
        qa_result=state.get("qa_result", {}),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
    )
    report_path = Path(str(state["outdir"])) / "reports" / "flavonoid_marker_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    state["report_text"] = report_text
    state["report_path"] = str(report_path)
    _append_trace(
        state,
        node_name="report_node",
        input_summary="agent outputs and QA result",
        output_summary=f"report_path={report_path}",
        warnings=[],
        limitations=["Writes Markdown report from existing report renderer."],
    )
    return state


def write_outputs_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    outdir = Path(str(state["outdir"]))
    qa_path = outdir / "logs" / "qa_check.json"
    manifest_path = outdir / "manifest.json"
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(qa_path, state.get("qa_result", {}))
    state["manifest_path"] = str(manifest_path)
    _append_trace(
        state,
        node_name="write_outputs_node",
        input_summary="report path, QA result, graph state",
        output_summary=f"qa_check={qa_path}; manifest={manifest_path}",
        warnings=state.get("warnings", []),
        limitations=["Graph trace artifacts are written by workflow wrapper after graph completion."],
    )
    return state


def initial_graph_state(
    *,
    evidence_dir: Path,
    outdir: Path,
    variant_calling_dir: Path | None = None,
    target_genes: list[str] | None = None,
) -> FlavonoidGraphState:
    return {
        "evidence_dir": str(evidence_dir),
        "outdir": str(outdir),
        "variant_calling_dir": str(variant_calling_dir) if variant_calling_dir else None,
        "target_genes": target_genes or list(REQUIRED_GENE_IDS),
        "agent_context": {},
        "candidate_table_path": None,
        "candidate_rows": [],
        "literature_rows": [],
        "agent_outputs": [],
        "reviewer_warnings": [],
        "qa_result": {},
        "report_path": None,
        "manifest_path": None,
        "graph_trace": [],
        "errors": [],
        "warnings": [],
    }


def _append_trace_from_agent(
    state: FlavonoidGraphState,
    *,
    node_name: str,
    input_summary: str,
    output: dict[str, Any],
) -> None:
    _append_trace(
        state,
        node_name=node_name,
        agent_name=str(output.get("agent_name", "")),
        input_summary=input_summary,
        output_summary=str(output.get("summary", "")),
        evidence_used=[str(item) for item in output.get("evidence_used", [])],
        warnings=[str(item) for item in output.get("warnings", [])],
        limitations=[str(item) for item in output.get("limitations", [])],
        passed=_passed_from_payload(output.get("structured_payload", {})),
    )


def _append_trace(
    state: FlavonoidGraphState,
    *,
    node_name: str,
    input_summary: str,
    output_summary: str,
    agent_name: str = "",
    evidence_used: list[str] | None = None,
    warnings: list[str] | None = None,
    limitations: list[str] | None = None,
    passed: bool | None = None,
) -> None:
    trace = list(state.get("graph_trace", []))
    trace.append(
        {
            "node_id": len(trace) + 1,
            "node_name": node_name,
            "agent_name": agent_name,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "evidence_used": evidence_used or [],
            "warnings": warnings or [],
            "limitations": limitations or [],
            "passed": passed,
        }
    )
    state["graph_trace"] = trace


def _add_agent_output(state: FlavonoidGraphState, output: dict[str, Any]) -> None:
    outputs = list(state.get("agent_outputs", []))
    outputs.append(output)
    state["agent_outputs"] = outputs


def _warnings(state: FlavonoidGraphState) -> list[str]:
    return [str(warning) for warning in state.get("warnings", [])]


def _optional_path(value: object) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(text)


def _rows(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _passed_from_payload(payload: object) -> bool | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("passed")
    if isinstance(value, bool):
        return value
    return None


def _write_json(path: Path, payload: object) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
