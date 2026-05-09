"""Comparison utilities for Lobster-style reference vs internal agents."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from breeding_agent.external_agents.lobster_reference_adapter import (
    LOBSTER_MOCK_NOTICE,
    render_lobster_style_agent_report,
)
from breeding_agent.external_agents.lobster_reference_schema import (
    LobsterStyleResult,
    LobsterVsInternalComparison,
)


DOI_RE = re.compile(r"\b10\.\d{4,9}/[A-Za-z0-9._;()/:+-]+", re.IGNORECASE)
TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")


def compare_lobster_reference_with_internal(
    *,
    lobster_result: LobsterStyleResult,
    internal_agent_outdir: Path,
) -> list[LobsterVsInternalComparison]:
    lobster_text = render_lobster_style_agent_report(lobster_result)
    internal_text = _internal_text_bundle(internal_agent_outdir)
    graph_dir = internal_agent_outdir / "graph"
    qa_path = internal_agent_outdir / "logs" / "qa_check.json"

    comparisons = [
        _comparison(
            "three_target_genes_covered",
            _all_targets(lobster_text),
            _all_targets(internal_text),
            "Checks Si9g04210.1, Si5g31340.1, and Si9g34380.1.",
        ),
        _comparison(
            "contains_群体",
            "群体" in lobster_text,
            "群体" in internal_text,
            "Required Chinese-facing breeding population term.",
        ),
        _comparison(
            "contains_doi",
            bool(DOI_RE.search(lobster_text)),
            bool(DOI_RE.search(internal_text)),
            "DOI must come from existing evidence, not generated.",
        ),
        _comparison(
            "contains_statistical_evidence",
            _contains_any(lobster_text, ["baseMean", "log2FC", "pvalue", "padj"]),
            _contains_any(internal_text, ["baseMean", "log2FC", "pvalue", "padj"]),
            "Transcriptomics statistical values are required.",
        ),
        _comparison(
            "contains_snp_indel_kasp_caps",
            _contains_all(lobster_text, ["SNP", "InDel", "KASP", "CAPS"]),
            _contains_all(internal_text, ["SNP", "InDel", "KASP", "CAPS"]),
            "Marker recommendation categories.",
        ),
        _comparison(
            "handles_pass_lowqual",
            _contains_all(lobster_text, ["PASS", "LowQual"]),
            _contains_all(internal_text, ["PASS", "LowQual"]),
            "Quality stratification from candidate variant calling.",
        ),
        _comparison(
            "states_kasp_caps_preliminary",
            _contains_any(lobster_text, ["preliminary", "不是最终", "not final"]),
            _contains_any(internal_text, ["preliminary", "不是最终", "not final"]),
            "KASP/CAPS screening is not final marker design.",
        ),
        _comparison(
            "states_not_replace_wgs_gbs",
            _contains_any(lobster_text, ["does not replace WGS/GBS", "不能替代 WGS/GBS"]),
            _contains_any(internal_text, ["does not replace WGS/GBS", "不能替代 WGS/GBS"]),
            "Candidate-region calling is not WGS/GBS population calling.",
        ),
        _comparison(
            "has_graph_trace_node_decision_qa",
            False,
            (graph_dir / "graph_trace.json").exists()
            and (graph_dir / "node_decision_table.tsv").exists()
            and qa_path.exists(),
            "Internal LangGraph should expose trace, decision table, and QA.",
        ),
        _comparison(
            "has_local_llm_reviewer_status",
            False,
            _internal_has_llm_status(internal_agent_outdir),
            "Only internal LangGraph has local LLM Reviewer metadata.",
        ),
        _comparison(
            "crop_breeding_marker_specific",
            True,
            _contains_any(internal_text, ["育种", "marker", "标记"]),
            "Internal agents are customized for crop breeding marker recommendation.",
        ),
        _comparison(
            "evidence_traceability",
            LOBSTER_MOCK_NOTICE in lobster_text,
            _contains_any(internal_text, ["graph_trace", "qa_check", "manifest"]),
            "Both sides should preserve traceability; Lobster-style side is explicit mock.",
        ),
    ]
    return comparisons


def write_comparison_outputs(
    *,
    outdir: Path,
    lobster_result: LobsterStyleResult,
    comparisons: list[LobsterVsInternalComparison],
) -> dict[str, Path]:
    comparison_dir = outdir / "comparison"
    comparison_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = comparison_dir / "comparison_matrix.tsv"
    report_path = comparison_dir / "lobster_vs_internal_comparison.md"
    _write_comparison_matrix(matrix_path, comparisons)
    report_path.write_text(
        render_comparison_report(
            lobster_result=lobster_result,
            comparisons=comparisons,
        ),
        encoding="utf-8",
    )
    return {
        "comparison_matrix": matrix_path,
        "lobster_vs_internal_comparison": report_path,
    }


def render_comparison_report(
    *,
    lobster_result: LobsterStyleResult,
    comparisons: list[LobsterVsInternalComparison],
) -> str:
    lines = [
        "# Lobster-style Reference vs Internal LangGraph Agent Comparison",
        "",
        "This comparison uses a Lobster-style reference benchmark, not a real Lobster AI run.",
        "",
        f"- reference_project_name: {lobster_result.reference_project_name}",
        f"- reference_project_url: {lobster_result.reference_project_url}",
        f"- backend_name: {lobster_result.backend_name}",
        f"- backend_mode: {lobster_result.backend_mode}",
        f"- real_lobster_run: {str(lobster_result.real_lobster_run).lower()}",
        "",
        "## Comparison Matrix",
        "",
        "| Dimension | Lobster-style reference | Internal LangGraph result | Notes |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        "| {dimension} | {lobster} | {internal} | {notes} |".format(
            dimension=item.dimension,
            lobster=item.lobster_style_reference,
            internal=item.internal_langgraph_result,
            notes=item.notes,
        )
        for item in comparisons
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Lobster AI is used here only as a design reference for multi-omics specialist-agent orchestration.",
            "- The internal workflow is more customized for foxtail millet breeding marker recommendation.",
            "- The internal workflow includes fixed target genes, QA, PASS/LowQual handling, local LLM Reviewer status, and Gradio display.",
            "- Neither side in this benchmark produces final KASP primers, CAPS enzyme plans, WGS/GBS validation, or experimental validation.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _write_comparison_matrix(
    path: Path,
    comparisons: list[LobsterVsInternalComparison],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dimension",
                "lobster_style_reference",
                "internal_langgraph_result",
                "notes",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(item.to_dict() for item in comparisons)


def _comparison(
    dimension: str,
    lobster_value: bool,
    internal_value: bool,
    notes: str,
) -> LobsterVsInternalComparison:
    return LobsterVsInternalComparison(
        dimension=dimension,
        lobster_style_reference=str(bool(lobster_value)).lower(),
        internal_langgraph_result=str(bool(internal_value)).lower(),
        notes=notes,
    )


def _internal_text_bundle(internal_agent_outdir: Path) -> str:
    paths = [
        internal_agent_outdir / "reports" / "flavonoid_marker_report.md",
        internal_agent_outdir / "graph" / "langgraph_summary.md",
        internal_agent_outdir / "graph" / "node_decision_table.tsv",
        internal_agent_outdir / "logs" / "qa_check.json",
        internal_agent_outdir / "manifest.json",
    ]
    return "\n".join(_read_text(path) for path in paths)


def _internal_has_llm_status(internal_agent_outdir: Path) -> bool:
    for path in [
        internal_agent_outdir / "graph" / "graph_trace.json",
        internal_agent_outdir / "graph" / "graph_state_final.json",
        internal_agent_outdir / "manifest.json",
    ]:
        data = _read_json(path)
        if _json_contains_key(data, "llm_used"):
            return True
    return False


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> object:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _json_contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_json_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_json_contains_key(item, key) for item in value)
    return False


def _all_targets(text: str) -> bool:
    return all(gene in text for gene in TARGET_GENES)


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _contains_all(text: str, needles: list[str]) -> bool:
    return all(needle in text for needle in needles)
