"""Output guardrails for LLM reviewer notes."""

from __future__ import annotations

import re
from dataclasses import dataclass


DOI_RE = re.compile(r"\b10\.\d{4,9}/[A-Za-z0-9._;()/:+-]+", re.IGNORECASE)
POSITION_RE = re.compile(
    r"(?i)(?:chr\w+|scaffold\w+|contig\w+|si\d+\w*)[:：]\d+|\bposition=\d+"
)


@dataclass(frozen=True)
class GuardResult:
    passed: bool
    reasons: list[str]


def guard_reviewer_output(
    *,
    content: str,
    context: dict[str, object],
) -> GuardResult:
    """Reject LLM reviewer notes that violate project evidence boundaries.

    The guard only evaluates the reviewer-note text; it should not be treated
    as a replacement for the deterministic QA step.
    """

    reasons: list[str] = []
    text = content.strip()
    if not text:
        return GuardResult(False, ["empty_content"])

    allowed_dois = _allowed_dois(context)
    generated_dois = {_normalize_doi(doi) for doi in DOI_RE.findall(text)}
    fabricated_dois = sorted(doi for doi in generated_dois if doi not in allowed_dois)
    if fabricated_dois:
        reasons.append("fabricated_doi: " + ", ".join(fabricated_dois))

    if POSITION_RE.search(text):
        reasons.append("possible_fabricated_snp_indel_coordinate")

    if "LowQual" in text and not _contains_any(
        text,
        ["不应优先", "不应直接优先", "should not be prioritized", "not be prioritized"],
    ):
        reasons.append("lowqual_priority_boundary_missing")

    if _mentions_preliminary_kasp_caps(text) and _claims_final_marker(text):
        reasons.append("preliminary_kasp_caps_overclaimed_as_final")

    if not _contains_any(
        text,
        [
            "不能替代 WGS/GBS",
            "does not replace WGS/GBS",
            "not replace WGS/GBS",
            "不能替代 WGS",
        ],
    ):
        reasons.append("wgs_gbs_limitation_missing")

    return GuardResult(not reasons, reasons)


def _allowed_dois(context: dict[str, object]) -> set[str]:
    # Pull the allow-list from verified evidence and real external results, then
    # explicitly remove demo rows so the reviewer cannot promote them to real evidence.
    allowed: set[str] = set()
    allowed_report_dois = context.get("allowed_report_dois", [])
    if isinstance(allowed_report_dois, list):
        allowed.update(_normalize_doi(str(doi)) for doi in allowed_report_dois if str(doi).strip())
    for row in _rows(context.get("literature_evidence", [])):
        doi = _normalize_doi(str(row.get("doi", "")))
        if doi:
            allowed.add(doi)
    for row in _rows(context.get("literature_results", [])):
        if _is_demo_row(row):
            continue
        doi = _normalize_doi(str(row.get("doi", "")))
        if doi:
            allowed.add(doi)
    for text_key in ["literature_review_text", "report_text"]:
        allowed.update(
            _normalize_doi(doi)
            for doi in DOI_RE.findall(str(context.get(text_key, "")))
        )
    return allowed - _demo_dois(context)


def _normalize_doi(doi: str) -> str:
    return doi.strip().lower().rstrip(".,;，。；\"'`")


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _is_demo_row(row: dict[str, object]) -> bool:
    return bool(row.get("is_demo")) or row.get("source") == "PubMedFixture"


def _demo_dois(context: dict[str, object]) -> set[str]:
    demo_dois = {
        _normalize_doi(str(row.get("doi", "")))
        for row in _rows(context.get("literature_results", []))
        if _is_demo_row(row) and _normalize_doi(str(row.get("doi", "")))
    }
    literature_analysis = context.get("literature_analysis", {})
    if isinstance(literature_analysis, dict):
        doi_sources = literature_analysis.get("doi_sources", {})
        if isinstance(doi_sources, dict):
            for key in ["literature_results_demo", "demo_dois"]:
                values = doi_sources.get(key, [])
                if isinstance(values, list):
                    demo_dois.update(
                        _normalize_doi(str(doi))
                        for doi in values
                        if _normalize_doi(str(doi))
                    )
    return demo_dois


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _mentions_preliminary_kasp_caps(text: str) -> bool:
    return "preliminary" in text and ("KASP" in text or "CAPS" in text)


def _claims_final_marker(text: str) -> bool:
    if _contains_any(text, ["不是最终", "not final", "not a final"]):
        return False
    return _contains_any(
        text,
        ["最终标记", "最终引物", "final marker", "final primer"],
    )
