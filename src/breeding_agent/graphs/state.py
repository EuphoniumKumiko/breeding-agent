"""State schema for optional LangGraph flavonoid marker workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class FlavonoidGraphState(TypedDict, total=False):
    """JSON-serializable state passed between graph nodes."""

    evidence_dir: str
    outdir: str
    variant_calling_dir: str | None
    target_genes: list[str]
    agent_context: dict[str, Any]
    candidate_table_path: str | None
    candidate_rows: list[dict[str, str]]
    literature_rows: list[dict[str, str]]
    literature_review_text: str
    marker_recommendation_text: str
    validation_plan_text: str
    reviewer_notes: str
    agent_outputs: list[dict[str, Any]]
    reviewer_warnings: list[str]
    qa_result: dict[str, Any]
    report_text: str
    report_path: str | None
    manifest_path: str | None
    graph_trace: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]
