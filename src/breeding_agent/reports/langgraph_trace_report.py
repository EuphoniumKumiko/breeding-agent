"""Reports for the optional LangGraph flavonoid marker workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


NODE_DECISION_COLUMNS = [
    "node_id",
    "node_name",
    "agent_name",
    "input_summary",
    "output_summary",
    "evidence_used",
    "warnings",
    "limitations",
    "passed",
]


def write_langgraph_trace_reports(
    *,
    outdir: Path,
    final_state: dict[str, Any],
) -> dict[str, Path]:
    """Write graph trace artifacts and return their paths."""

    graph_dir = outdir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph_trace_path = graph_dir / "graph_trace.json"
    final_state_path = graph_dir / "graph_state_final.json"
    decision_table_path = graph_dir / "node_decision_table.tsv"
    summary_path = graph_dir / "langgraph_summary.md"

    trace = _trace(final_state)
    _write_json(graph_trace_path, trace)
    _write_json(final_state_path, _json_safe(final_state))
    write_node_decision_table(decision_table_path, trace)
    summary_path.write_text(
        render_langgraph_summary(final_state),
        encoding="utf-8",
    )
    return {
        "graph_trace": graph_trace_path,
        "graph_state_final": final_state_path,
        "node_decision_table": decision_table_path,
        "langgraph_summary": summary_path,
    }


def write_node_decision_table(path: Path, graph_trace: list[dict[str, Any]]) -> Path:
    """Write node-level decision metadata as TSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=NODE_DECISION_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in graph_trace:
            writer.writerow(
                {
                    "node_id": row.get("node_id", ""),
                    "node_name": row.get("node_name", ""),
                    "agent_name": row.get("agent_name", ""),
                    "input_summary": row.get("input_summary", ""),
                    "output_summary": row.get("output_summary", ""),
                    "evidence_used": _join(row.get("evidence_used", [])),
                    "warnings": _join(row.get("warnings", [])),
                    "limitations": _join(row.get("limitations", [])),
                    "passed": row.get("passed", ""),
                }
            )
    return path


def render_langgraph_summary(final_state: dict[str, Any]) -> str:
    """Render Markdown summary for the graph run."""

    trace = _trace(final_state)
    qa_result = final_state.get("qa_result", {})
    variant_dir = final_state.get("variant_calling_dir")
    variant_loaded = False
    context = final_state.get("agent_context", {})
    if isinstance(context, dict):
        variant_info = context.get("variant_calling", {})
        if isinstance(variant_info, dict):
            variant_loaded = bool(variant_info.get("loaded"))

    node_lines = [
        "| node_id | node_name | agent_name | passed | output_summary |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in trace:
        node_lines.append(
            "| {node_id} | {node_name} | {agent_name} | {passed} | {summary} |".format(
                node_id=row.get("node_id", ""),
                node_name=_cell(row.get("node_name", "")),
                agent_name=_cell(row.get("agent_name", "")),
                passed=_cell(row.get("passed", "")),
                summary=_cell(row.get("output_summary", "")),
            )
        )

    return "\n".join(
        [
            "# LangGraph Flavonoid Marker Recommendation Summary",
            "",
            "## LangGraph 多智能体聚合流程概览",
            (
                "本 workflow 使用 LangGraph 编排现有规则化 agents。当前没有接入真实 "
                "LLM、OpenAI SDK、本地开源大模型或外部 API。"
            ),
            "",
            "## Node 设计",
            "\n".join(node_lines),
            "",
            "## Agent 对应关系",
            "- literature_agent_node -> FlavonoidLiteratureAgent",
            "- marker_recommendation_agent_node -> FlavonoidMarkerRecommendationAgent",
            "- validation_agent_node -> FlavonoidValidationAgent",
            "- reviewer_agent_node -> FlavonoidReviewerAgent",
            "- final_qa_agent_node -> FlavonoidFinalQAAgent",
            "",
            "## Variant Evidence",
            f"- variant_calling_dir: `{variant_dir or 'not provided'}`",
            f"- variant evidence loaded: `{variant_loaded}`",
            (
                "- PASS variants can be reviewed first; LowQual variants are retained "
                "for traceability but should not be prioritized."
            ),
            "- Current candidate-region calling does not replace WGS/GBS population variant calling.",
            "",
            "## ReviewerAgent",
            (
                "ReviewerAgent checks missing statistics, DOI omissions, fabricated "
                "variant coordinates, LowQual over-prioritization, preliminary KASP/CAPS "
                "overclaiming, and WGS/GBS overclaiming."
            ),
            "",
            "## FinalQAAgent",
            f"- passed: `{qa_result.get('passed') if isinstance(qa_result, dict) else None}`",
            (
                "- FinalQAAgent checks fixed genes, statistics, DOI-backed literature, "
                "SNP/InDel/KASP/CAPS recommendations, population validation language, "
                "and optional variant calling limitations."
            ),
            "",
            "## Future Plan",
            (
                "后续可在 AgentInput/AgentOutput adapter 层接入 OpenAI 或本地开源大模型；"
                "Deep Agents 只作为后续阶段规划，本轮不接入。模型输出仍必须通过 "
                "ReviewerAgent 和 FinalQAAgent，并保留规则 fallback。"
            ),
            "",
        ]
    )


def _trace(final_state: dict[str, Any]) -> list[dict[str, Any]]:
    trace = final_state.get("graph_trace", [])
    if not isinstance(trace, list):
        return []
    return [row for row in trace if isinstance(row, dict)]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(payload), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _join(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(str(item).replace("\n", " ") for item in value)
    return str(value).replace("\n", " ")


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
