"""Shared schema for standardized multi-omics evidence tables."""

from __future__ import annotations

from dataclasses import dataclass


STANDARD_EVIDENCE_COLUMNS: tuple[str, ...] = (
    "entity_id",
    "entity_type",
    "omics_type",
    "trait",
    "comparison",
    "direction",
    "effect_size",
    "p_value",
    "adj_p_value",
    "evidence_score",
    "source_module",
    "source_file",
    "evidence_note",
)


@dataclass(frozen=True)
class StandardEvidenceRecord:
    entity_id: str
    entity_type: str
    omics_type: str
    trait: str
    comparison: str
    direction: str
    effect_size: str
    p_value: str
    adj_p_value: str
    evidence_score: str
    source_module: str
    source_file: str
    evidence_note: str

    def as_dict(self) -> dict[str, str]:
        return {column: getattr(self, column) for column in STANDARD_EVIDENCE_COLUMNS}

