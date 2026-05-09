"""Schemas for the promoter design scaffold task."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PromoterDesignInput:
    gene_id: str
    gene_sequence: str
    gene_function: str
    species: str
    target_expression_level: str
    target_tissue_or_condition: str = ""


@dataclass(frozen=True)
class PromoterCandidate:
    candidate_id: str
    gene_id: str
    promoter_sequence: str
    design_status: str
    intended_use: str
    limitations: str


@dataclass(frozen=True)
class PromoterDesignOutput:
    promoter_candidates_fasta: Path
    promoter_candidate_table: Path
    promoter_design_report: Path
    promoter_validation_plan: Path
    manifest: Path
    candidates: list[PromoterCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PromoterDatasetRecord:
    record_id: str
    species: str
    gene_id: str
    sequence_id: str
    sequence_source: str
    assay_type: str
    activity_measure: str
    condition: str
    tier: str
    doi: str = ""
    limitations: str = ""
