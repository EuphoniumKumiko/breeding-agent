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
    """Reject LLM reviewer notes that violate project evidence boundaries."""

    reasons: list[str] = []
    text = content.strip()
    if not text:
        return GuardResult(False, ["empty_content"])

    allowed_dois = _allowed_dois(context)
    generated_dois = set(DOI_RE.findall(text))
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
    allowed: set[str] = set()
    for row in _rows(context.get("literature_evidence", [])):
        doi = str(row.get("doi", "")).strip()
        if doi:
            allowed.add(doi)
    for text_key in ["literature_review_text", "report_text"]:
        allowed.update(DOI_RE.findall(str(context.get(text_key, ""))))
    return allowed


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


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
