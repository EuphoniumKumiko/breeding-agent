"""Schemas for the Lobster-style external omics agent benchmark."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


REFERENCE_PROJECT_NAME = "Lobster AI"
REFERENCE_PROJECT_URL = "https://github.com/the-omics-os/lobster"
BACKEND_NAME = "lobster_ai_reference"
BACKEND_MODE = "mock_reference"


@dataclass(frozen=True)
class LobsterReferenceTask:
    reference_project_name: str = REFERENCE_PROJECT_NAME
    reference_project_url: str = REFERENCE_PROJECT_URL
    backend_name: str = BACKEND_NAME
    backend_mode: str = BACKEND_MODE
    target_genes: list[str] = field(default_factory=list)
    evidence_used: list[str] = field(default_factory=list)
    real_lobster_run: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_project_name": self.reference_project_name,
            "reference_project_url": self.reference_project_url,
            "backend_name": self.backend_name,
            "backend_mode": self.backend_mode,
            "target_genes": list(self.target_genes),
            "evidence_used": list(self.evidence_used),
            "real_lobster_run": self.real_lobster_run,
            "warnings": list(self.warnings),
            "note": "This is a Lobster-style reference benchmark, not a real Lobster AI run.",
        }


@dataclass(frozen=True)
class LobsterStyleGeneAssessment:
    gene_id: str
    transcriptomics_support: str
    metabolomics_support: str
    annotation_support: str
    literature_support: str
    variant_support: str
    general_omics_interpretation: str
    marker_recommendation: str
    validation_required: str
    limitations: list[str]
    warnings: list[str]
    confidence_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_id": self.gene_id,
            "transcriptomics_support": self.transcriptomics_support,
            "metabolomics_support": self.metabolomics_support,
            "annotation_support": self.annotation_support,
            "literature_support": self.literature_support,
            "variant_support": self.variant_support,
            "general_omics_interpretation": self.general_omics_interpretation,
            "marker_recommendation": self.marker_recommendation,
            "validation_required": self.validation_required,
            "limitations": list(self.limitations),
            "warnings": list(self.warnings),
            "confidence_label": self.confidence_label,
        }


@dataclass(frozen=True)
class LobsterStyleResult:
    reference_project_name: str
    reference_project_url: str
    backend_name: str
    backend_mode: str
    target_genes: list[str]
    evidence_used: list[str]
    gene_assessments: list[LobsterStyleGeneAssessment]
    limitations: list[str]
    warnings: list[str]
    real_lobster_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_project_name": self.reference_project_name,
            "reference_project_url": self.reference_project_url,
            "backend_name": self.backend_name,
            "backend_mode": self.backend_mode,
            "target_genes": list(self.target_genes),
            "evidence_used": list(self.evidence_used),
            "gene_assessments": [
                assessment.to_dict() for assessment in self.gene_assessments
            ],
            "limitations": list(self.limitations),
            "warnings": list(self.warnings),
            "real_lobster_run": self.real_lobster_run,
            "note": "This is a Lobster-style reference benchmark, not a real Lobster AI run.",
        }


@dataclass(frozen=True)
class LobsterVsInternalComparison:
    dimension: str
    lobster_style_reference: str
    internal_langgraph_result: str
    notes: str

    def to_dict(self) -> dict[str, str]:
        return {
            "dimension": self.dimension,
            "lobster_style_reference": self.lobster_style_reference,
            "internal_langgraph_result": self.internal_langgraph_result,
            "notes": self.notes,
        }
