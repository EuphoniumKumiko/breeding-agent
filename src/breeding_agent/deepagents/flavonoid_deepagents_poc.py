"""Deterministic Deep Agents POC for flavonoid marker recommendation.

This module only proves that the project can host a Deep Agents-style harness.
It does not call a real LLM, local model, external API, or Deep Agents runtime
planner. The current POC keeps all biological decisions inside the existing
rule-based agents and writes trace artifacts for inspection.
"""

from __future__ import annotations

import csv
import importlib
import json
from pathlib import Path
from typing import Any

from breeding_agent.agents.flavonoid_central_host import FlavonoidCentralHost
from breeding_agent.integration.flavonoid_marker_aggregator import REQUIRED_GENE_IDS


DEEPAGENTS_INSTALL_MESSAGE = (
    "Deep Agents is not installed. Install according to project docs."
)

TRACE_FILENAME = "deepagents_trace.json"
SUMMARY_FILENAME = "deepagents_summary.md"
DECISION_TABLE_FILENAME = "deepagents_decision_table.tsv"
DECISION_COLUMNS = [
    "step_id",
    "step_name",
    "agent_name",
    "input_summary",
    "output_summary",
    "variant_calling_enabled",
    "variant_calling_dir",
    "gene_level_variant_evidence_integrated",
    "candidate_variant_rows",
    "kasp_candidate_rows",
    "caps_candidate_rows",
    "evidence_used",
    "warnings",
    "limitations",
    "passed",
]


def require_deepagents() -> Any:
    """Import Deep Agents as an optional dependency with a stable error."""

    try:
        return importlib.import_module("deepagents")
    except ImportError as exc:
        raise RuntimeError(DEEPAGENTS_INSTALL_MESSAGE) from exc


def run_deepagents_poc(
    *,
    evidence_dir: Path,
    outdir: Path,
    variant_calling_dir: Path | None = None,
) -> dict[str, object]:
    """Run the deterministic Deep Agents POC through existing rule agents."""

    require_deepagents()
    agent_result = FlavonoidCentralHost(
        evidence_dir=evidence_dir,
        outdir=outdir,
        variant_calling_dir=variant_calling_dir,
    ).run()
    trace = build_deepagents_trace(agent_result)
    decision_rows = build_deepagents_decision_rows(trace)
    summary = render_deepagents_summary(
        agent_result=agent_result,
        trace=trace,
        decision_rows=decision_rows,
    )
    artifacts = write_deepagents_artifacts(
        outdir=outdir,
        trace=trace,
        summary=summary,
        decision_rows=decision_rows,
    )
    return {
        "agent_result": agent_result,
        "trace": trace,
        "decision_rows": decision_rows,
        "summary": summary,
        "artifacts": artifacts,
    }


def build_deepagents_trace(agent_result: dict[str, object]) -> list[dict[str, object]]:
    """Build a JSON-serializable deterministic trace from rule-agent outputs."""

    agent_context = _as_dict(agent_result.get("agent_context"))
    agent_outputs = _display_agent_outputs(_as_list(agent_result.get("agent_outputs")))
    candidate_rows = _as_list(agent_result.get("candidate_rows"))
    warnings = [str(item) for item in _as_list(agent_result.get("warnings"))]
    variant_summary = summarize_variant_evidence(agent_result)
    trace: list[dict[str, object]] = [
        {
            "step_id": 1,
            "step_name": "deepagents_harness_start",
            "agent_name": "deepagents_poc_harness",
            "input_summary": _context_summary(agent_context, variant_summary),
            "output_summary": "Initialized deterministic Deep Agents POC harness.",
            "variant_evidence_summary": variant_summary,
            "evidence_used": [
                "transcriptome_evidence.tsv",
                "metabolome_evidence.tsv",
                "annotation_evidence.tsv",
                "literature_evidence.tsv",
                "optional candidate variant calling evidence",
            ],
            "warnings": warnings,
            "limitations": [
                "Deep Agents is used only as an optional POC dependency.",
                "No real LLM, local model, or external API is called.",
            ],
            "passed": True,
        },
        {
            "step_id": 2,
            "step_name": "aggregate_candidates",
            "agent_name": "flavonoid_marker_aggregator",
            "input_summary": "Read local evidence TSV files and optional variant calling outputs.",
            "output_summary": (
                f"Aggregated {len(candidate_rows)} fixed target genes; "
                f"{_variant_summary_text(variant_summary)}"
            ),
            "variant_evidence_summary": variant_summary,
            "evidence_used": ["flavonoid marker evidence package"],
            "warnings": warnings,
            "limitations": [
                "The aggregator does not fabricate SNP/InDel positions or DOI values.",
            ],
            "passed": True,
        },
        {
            "step_id": 3,
            "step_name": "build_context",
            "agent_name": "build_flavonoid_agent_context",
            "input_summary": f"Candidate rows={len(candidate_rows)}.",
            "output_summary": _context_summary(agent_context, variant_summary),
            "variant_evidence_summary": variant_summary,
            "evidence_used": [
                "transcriptomics evidence",
                "metabolomics evidence",
                "annotation evidence",
                "literature evidence",
                "variant evidence",
            ],
            "warnings": warnings,
            "limitations": [
                "Context is structured data only; no LLM prompt execution occurs.",
            ],
            "passed": True,
        },
    ]

    next_step_id = len(trace) + 1
    for output in agent_outputs:
        agent_output = _agent_output_dict(output)
        agent_name = str(agent_output.get("agent_name", "unknown_agent"))
        structured_payload = _as_dict(agent_output.get("structured_payload"))
        passed = structured_payload.get("passed", True)
        trace.append(
            {
                "step_id": next_step_id,
                "step_name": agent_name,
                "agent_name": agent_name,
                "input_summary": "Structured agent context from context_builder.",
                "output_summary": str(agent_output.get("summary", "")),
                "variant_evidence_summary": variant_summary,
                "evidence_used": [
                    str(item) for item in _as_list(agent_output.get("evidence_used"))
                ],
                "warnings": [
                    str(item) for item in _as_list(agent_output.get("warnings"))
                ],
                "limitations": [
                    str(item) for item in _as_list(agent_output.get("limitations"))
                ],
                "passed": bool(passed),
            }
        )
        next_step_id += 1

    trace.append(
        {
            "step_id": next_step_id,
            "step_name": "write_outputs",
            "agent_name": "deepagents_poc_writer",
            "input_summary": "Final report, QA result, and deterministic trace.",
            "output_summary": "Prepared Deep Agents POC artifacts.",
            "variant_evidence_summary": variant_summary,
            "evidence_used": ["agent_outputs", "qa_result", "final_report_text"],
            "warnings": warnings,
            "limitations": [
                "Artifacts explain future harness integration only; LangGraph remains the main graph workflow.",
            ],
            "passed": bool(_as_dict(agent_result.get("qa_result")).get("passed", False)),
        }
    )
    return trace


def build_deepagents_decision_rows(
    trace: list[dict[str, object]],
) -> list[dict[str, str]]:
    """Convert trace entries to TSV-friendly decision rows."""

    rows: list[dict[str, str]] = []
    for entry in trace:
        variant_summary = _as_dict(entry.get("variant_evidence_summary"))
        step_name = str(entry.get("step_name", ""))
        agent_name = str(entry.get("agent_name", ""))
        rows.append(
            {
                "step_id": str(entry.get("step_id", "")),
                "step_name": step_name,
                "agent_name": "" if agent_name == step_name else agent_name,
                "input_summary": str(entry.get("input_summary", "")),
                "output_summary": str(entry.get("output_summary", "")),
                "variant_calling_enabled": _bool_text(
                    variant_summary.get("variant_calling_enabled", False)
                ),
                "variant_calling_dir": str(variant_summary.get("variant_calling_dir", "")),
                "gene_level_variant_evidence_integrated": _bool_text(
                    variant_summary.get(
                        "gene_level_variant_evidence_integrated",
                        False,
                    )
                ),
                "candidate_variant_rows": str(
                    variant_summary.get("candidate_variant_rows", "0")
                ),
                "kasp_candidate_rows": str(
                    variant_summary.get("kasp_candidate_rows", "0")
                ),
                "caps_candidate_rows": str(
                    variant_summary.get("caps_candidate_rows", "0")
                ),
                "evidence_used": "; ".join(
                    str(item) for item in _as_list(entry.get("evidence_used"))
                ),
                "warnings": "; ".join(
                    str(item) for item in _as_list(entry.get("warnings"))
                ),
                "limitations": "; ".join(
                    str(item) for item in _as_list(entry.get("limitations"))
                ),
                "passed": str(bool(entry.get("passed", False))),
            }
        )
    return rows


def render_deepagents_summary(
    *,
    agent_result: dict[str, object],
    trace: list[dict[str, object]],
    decision_rows: list[dict[str, str]],
) -> str:
    """Render a compact Markdown summary for the Deep Agents POC."""

    qa_result = _as_dict(agent_result.get("qa_result"))
    variant_summary = summarize_variant_evidence(agent_result)
    agent_names = [
        row.get("agent_name") or row.get("step_name", "")
        for row in decision_rows
        if (row.get("agent_name") or row.get("step_name", "")).endswith("_agent")
    ]
    lines = [
        "# Deep Agents Flavonoid Marker POC Summary",
        "",
        "## 定位",
        (
            "本 POC 用于验证 breeding-agent 可以接入 Deep Agents 这类更高层 "
            "agent harness，但当前仍复用现有规则化 agents，不调用真实大模型、"
            "本地开源模型或外部 API。"
        ),
        "LangGraph 仍是当前主线 graph workflow；Deep Agents POC 不替换旧 workflow 或 LangGraph workflow。",
        "",
        "## 复用组件",
        "- Evidence: transcriptome、metabolome、annotation、literature 和 optional variant evidence。",
        "- Context builder: `build_flavonoid_agent_context`。",
        "- Interface: `AgentInput` / `AgentOutput` 兼容结构。",
        "- Rule agents: "
        + (", ".join(agent_names) if agent_names else "existing rule-based agents"),
        "",
        "## Trace 输出",
        f"- deepagents_trace steps: {len(trace)}",
        f"- deepagents_decision_table rows: {len(decision_rows)}",
        f"- FinalQAAgent passed: {qa_result.get('passed')}",
        "",
        "## Variant Evidence Integration",
        f"- variant_calling_enabled={_bool_text(variant_summary['variant_calling_enabled'])}",
        f"- variant_calling_dir={variant_summary['variant_calling_dir'] or 'None'}",
        (
            "- gene_level_variant_evidence_integrated="
            f"{_bool_text(variant_summary['gene_level_variant_evidence_integrated'])}"
        ),
        f"- candidate_variant_rows={variant_summary['candidate_variant_rows']}",
        f"- kasp_candidate_rows={variant_summary['kasp_candidate_rows']}",
        f"- caps_candidate_rows={variant_summary['caps_candidate_rows']}",
        "- raw candidate variant rows are not expanded in this POC trace; gene-level variant evidence is used by the marker recommendation layer.",
        "- PASS / LowQual 仍由上游 variant calling 和 marker recommendation 层约束。",
        "- Deep Agents POC 不伪造任何 SNP/InDel 位点。",
        "",
        "## 生物与证据边界",
        "- 不伪造 SNP/InDel 位点；没有 called variant 时保持 not_called 或当前 calling 状态。",
        "- 不伪造 DOI；只使用 evidence 中已有并经过核验的 DOI。",
        "- LowQual 不得作为优先推荐，仅作为可追溯候选记录保留。",
        "- preliminary KASP/CAPS screening 不等于最终 KASP marker、最终引物或酶切方案。",
        "- 当前 candidate-region variant calling 不能替代 WGS/GBS 群体变异检测。",
        "- 最终报告必须保留学长硬性要求：优先围绕 "
        + "、".join(REQUIRED_GENE_IDS)
        + " 开发候选 SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。",
        "",
        "## 后续方向",
        "后续如需接入 Deep Agents，可在本 trace/decision table 基础上增加真实 planner、工具调用审计和本地开源模型适配层；本轮不做模型接入。",
        "",
    ]
    return "\n".join(lines)


def write_deepagents_artifacts(
    *,
    outdir: Path,
    trace: list[dict[str, object]],
    summary: str,
    decision_rows: list[dict[str, str]],
) -> dict[str, str]:
    """Write Deep Agents POC trace, summary, and decision table."""

    deepagents_dir = outdir / "deepagents"
    deepagents_dir.mkdir(parents=True, exist_ok=True)
    trace_path = deepagents_dir / TRACE_FILENAME
    summary_path = deepagents_dir / SUMMARY_FILENAME
    decision_table_path = deepagents_dir / DECISION_TABLE_FILENAME

    _write_json(trace_path, trace)
    summary_path.write_text(summary, encoding="utf-8")
    _write_decision_table(decision_table_path, decision_rows)
    return {
        "deepagents_trace": str(trace_path.resolve()),
        "deepagents_summary": str(summary_path.resolve()),
        "deepagents_decision_table": str(decision_table_path.resolve()),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _write_decision_table(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_COLUMNS, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in DECISION_COLUMNS})


def summarize_variant_evidence(agent_result: dict[str, object]) -> dict[str, object]:
    """Summarize optional variant calling evidence for POC display artifacts."""

    agent_context = _as_dict(agent_result.get("agent_context"))
    candidate_rows = _as_list(agent_result.get("candidate_rows"))
    variant_calling_dir = _variant_calling_dir(agent_result, agent_context)
    variant_dir_path = Path(variant_calling_dir) if variant_calling_dir else None
    variant_calling_enabled = bool(variant_dir_path and variant_dir_path.exists())
    candidate_variant_rows = _count_tsv_rows(
        variant_dir_path / "tables" / "candidate_variants.tsv"
        if variant_dir_path
        else None
    )
    kasp_candidate_rows = _count_tsv_rows(
        variant_dir_path / "tables" / "kasp_candidate_sites.tsv"
        if variant_dir_path
        else None
    )
    caps_candidate_rows = _count_tsv_rows(
        variant_dir_path / "tables" / "caps_candidate_sites.tsv"
        if variant_dir_path
        else None
    )
    context_variant_rows = _as_list(agent_context.get("variant_calling_evidence"))
    gene_level_rows = (
        context_variant_rows
        or [
            row
            for row in candidate_rows
            if isinstance(row, dict) and row.get("variant_evidence_status")
        ]
    )
    return {
        "variant_calling_enabled": variant_calling_enabled,
        "variant_calling_dir": str(variant_dir_path) if variant_dir_path else "",
        "gene_level_variant_evidence_integrated": bool(gene_level_rows),
        "gene_level_variant_evidence_rows": len(gene_level_rows),
        "candidate_variant_rows": candidate_variant_rows,
        "kasp_candidate_rows": kasp_candidate_rows,
        "caps_candidate_rows": caps_candidate_rows,
        "raw_rows_expanded_in_trace": False,
    }


def _context_summary(
    context: dict[str, object],
    variant_summary: dict[str, object],
) -> str:
    return (
        f"candidate_rows={len(_as_list(context.get('candidate_rows')))}, "
        f"literature_rows={len(_as_list(context.get('literature_evidence')))}, "
        "gene_level_variant_evidence_rows="
        f"{variant_summary.get('gene_level_variant_evidence_rows', 0)}, "
        f"candidate_variant_rows={variant_summary.get('candidate_variant_rows', 0)}, "
        f"kasp_candidate_rows={variant_summary.get('kasp_candidate_rows', 0)}, "
        f"caps_candidate_rows={variant_summary.get('caps_candidate_rows', 0)}, "
        "raw candidate variant rows are not expanded in this POC trace"
    )


def _agent_output_dict(output: object) -> dict[str, object]:
    if isinstance(output, dict) and isinstance(output.get("agent_output"), dict):
        return _as_dict(output.get("agent_output"))
    return _as_dict(output)


def _display_agent_outputs(agent_outputs: list[object]) -> list[dict[str, object]]:
    """Keep one display row per agent, using the final output for duplicate QA."""

    ordered_names: list[str] = []
    by_name: dict[str, dict[str, object]] = {}
    for output in agent_outputs:
        agent_output = _agent_output_dict(output)
        agent_name = str(agent_output.get("agent_name", "unknown_agent"))
        if agent_name not in by_name:
            ordered_names.append(agent_name)
        by_name[agent_name] = agent_output
    return [by_name[name] for name in ordered_names]


def _variant_calling_dir(
    agent_result: dict[str, object],
    agent_context: dict[str, object],
) -> str:
    value = agent_result.get("variant_calling_dir")
    if value:
        return str(value)
    variant_calling = _as_dict(agent_context.get("variant_calling"))
    value = variant_calling.get("dir")
    return str(value) if value else ""


def _count_tsv_rows(path: Path | None) -> int:
    if path is None or not path.exists() or not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        next(reader, None)
        return sum(1 for row in reader if row)


def _variant_summary_text(variant_summary: dict[str, object]) -> str:
    return (
        "variant_calling_enabled="
        f"{_bool_text(variant_summary.get('variant_calling_enabled'))}, "
        "gene_level_variant_evidence_integrated="
        f"{_bool_text(variant_summary.get('gene_level_variant_evidence_integrated'))}, "
        f"candidate_variant_rows={variant_summary.get('candidate_variant_rows', 0)}, "
        f"kasp_candidate_rows={variant_summary.get('kasp_candidate_rows', 0)}, "
        f"caps_candidate_rows={variant_summary.get('caps_candidate_rows', 0)}"
    )


def _bool_text(value: object) -> str:
    return "true" if bool(value) else "false"


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []
