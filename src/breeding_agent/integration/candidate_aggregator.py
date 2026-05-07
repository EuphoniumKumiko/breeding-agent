"""Aggregate standardized evidence into candidate gene tables."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


EVIDENCE_FILENAME = "standardized_evidence.tsv"
CANDIDATE_TABLE_FILENAME = "candidate_gene_table.tsv"
CANDIDATE_TABLE_COLUMNS = [
    "candidate_id",
    "entity_type",
    "trait",
    "supporting_omics",
    "support_count",
    "best_adj_p_value",
    "max_abs_effect_size",
    "final_score",
    "recommendation_level",
    "evidence_summary",
]


def generate_candidate_gene_table(*, outdir: Path) -> Path:
    """Aggregate standardized evidence rows by entity_id."""

    integration_dir = outdir / "integration"
    evidence_file = integration_dir / EVIDENCE_FILENAME
    if not evidence_file.exists():
        raise FileNotFoundError(f"Standardized evidence file does not exist: {evidence_file}")

    records = _read_evidence(evidence_file)
    candidate_records = _aggregate_candidates(records)

    candidate_file = integration_dir / CANDIDATE_TABLE_FILENAME
    with candidate_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CANDIDATE_TABLE_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(candidate_records)

    return candidate_file


def _read_evidence(evidence_file: Path) -> list[dict[str, str]]:
    with evidence_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _aggregate_candidates(records: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in records:
        entity_id = row.get("entity_id", "").strip()
        if entity_id:
            grouped[entity_id].append(row)

    candidates = [
        _candidate_from_rows(candidate_id=entity_id, rows=rows)
        for entity_id, rows in grouped.items()
    ]
    return sorted(candidates, key=_candidate_sort_key, reverse=True)


def _candidate_from_rows(
    *,
    candidate_id: str,
    rows: list[dict[str, str]],
) -> dict[str, str]:
    entity_type = _first_non_empty(rows, "entity_type", default="unknown")
    traits = _unique_values(rows, "trait")
    omics_types = _unique_values(rows, "omics_type")
    directions = _unique_values(rows, "direction")
    best_adj_p_value = _min_float(rows, "adj_p_value")
    max_abs_effect_size = _max_abs_float(rows, "effect_size")
    max_evidence_score = _max_float(rows, "evidence_score") or 0.0
    support_count = len(omics_types)
    final_score = min(max_evidence_score + (0.1 * support_count), 1.0)

    return {
        "candidate_id": candidate_id,
        "entity_type": entity_type,
        "trait": ",".join(traits),
        "supporting_omics": ",".join(omics_types),
        "support_count": str(support_count),
        "best_adj_p_value": _format_float(best_adj_p_value),
        "max_abs_effect_size": _format_float(max_abs_effect_size),
        "final_score": f"{final_score:.3f}",
        "recommendation_level": _recommendation_level(
            final_score=final_score,
            support_count=support_count,
        ),
        "evidence_summary": _evidence_summary(
            omics_types=omics_types,
            support_count=support_count,
            max_score=max_evidence_score,
            directions=directions,
        ),
    }


def _unique_values(rows: list[dict[str, str]], key: str) -> list[str]:
    values = {row.get(key, "").strip() for row in rows if row.get(key, "").strip()}
    return sorted(values)


def _first_non_empty(
    rows: list[dict[str, str]],
    key: str,
    *,
    default: str,
) -> str:
    for row in rows:
        value = row.get(key, "").strip()
        if value:
            return value
    return default


def _min_float(rows: list[dict[str, str]], key: str) -> float | None:
    values = [_parse_float(row.get(key)) for row in rows]
    values = [value for value in values if value is not None]
    return min(values) if values else None


def _max_float(rows: list[dict[str, str]], key: str) -> float | None:
    values = [_parse_float(row.get(key)) for row in rows]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _max_abs_float(rows: list[dict[str, str]], key: str) -> float | None:
    values = [_parse_float(row.get(key)) for row in rows]
    values = [abs(value) for value in values if value is not None]
    return max(values) if values else None


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6g}"


def _recommendation_level(*, final_score: float, support_count: int) -> str:
    if support_count < 2:
        return "preliminary"
    if final_score >= 0.85:
        return "high"
    if final_score >= 0.6:
        return "medium"
    return "preliminary"


def _evidence_summary(
    *,
    omics_types: list[str],
    support_count: int,
    max_score: float,
    directions: list[str],
) -> str:
    omics_text = ", ".join(omics_types) if omics_types else "unknown omics"
    direction_text = ", ".join(directions) if directions else "unknown"
    summary = (
        f"Supported by {omics_text} evidence; max evidence_score={max_score:.3f}; "
        f"main direction(s): {direction_text}."
    )
    if support_count < 2:
        summary = (
            f"{summary} single-omics evidence only; requires additional omics, "
            "phenotype, and literature support."
        )
    return summary


def _candidate_sort_key(row: dict[str, str]) -> tuple[float, int, float]:
    final_score = _parse_float(row.get("final_score")) or 0.0
    support_count = int(row.get("support_count") or 0)
    max_abs_effect_size = _parse_float(row.get("max_abs_effect_size")) or 0.0
    return final_score, support_count, max_abs_effect_size
