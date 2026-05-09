"""Lobster-style mock reference adapter for external omics agent benchmarking."""

from __future__ import annotations

import csv
from pathlib import Path

from breeding_agent.external_agents.lobster_reference_schema import (
    BACKEND_MODE,
    BACKEND_NAME,
    REFERENCE_PROJECT_NAME,
    REFERENCE_PROJECT_URL,
    LobsterReferenceTask,
    LobsterStyleGeneAssessment,
    LobsterStyleResult,
)
from breeding_agent.integration.flavonoid_marker_aggregator import (
    ANNOTATION_EVIDENCE,
    GENOME_VARIANT_EVIDENCE,
    LITERATURE_EVIDENCE,
    METABOLOME_EVIDENCE,
    REQUIRED_GENE_IDS,
    TRANSCRIPTOME_EVIDENCE,
)
from breeding_agent.integration.flavonoid_variant_evidence import (
    load_flavonoid_variant_evidence,
)


LOBSTER_MOCK_NOTICE = (
    "This is a Lobster-style reference benchmark, not a real Lobster AI run."
)


def build_lobster_reference_task(
    *,
    evidence_dir: Path,
    variant_calling_dir: Path | None,
) -> LobsterReferenceTask:
    evidence_used = [
        str(evidence_dir / TRANSCRIPTOME_EVIDENCE),
        str(evidence_dir / METABOLOME_EVIDENCE),
        str(evidence_dir / ANNOTATION_EVIDENCE),
        str(evidence_dir / GENOME_VARIANT_EVIDENCE),
        str(evidence_dir / LITERATURE_EVIDENCE),
    ]
    if variant_calling_dir:
        evidence_used.append(str(variant_calling_dir / "tables"))
    return LobsterReferenceTask(
        target_genes=list(REQUIRED_GENE_IDS),
        evidence_used=evidence_used,
        warnings=[],
    )


def run_lobster_style_reference_assessment(
    *,
    evidence_dir: Path,
    variant_calling_dir: Path | None = None,
) -> LobsterStyleResult:
    """Generate a deterministic Lobster-style reference result from local evidence."""

    warnings: list[str] = []
    transcriptome = _read_by_gene(evidence_dir / TRANSCRIPTOME_EVIDENCE, warnings)
    metabolome = _read_by_gene(evidence_dir / METABOLOME_EVIDENCE, warnings)
    annotation = _read_by_gene(evidence_dir / ANNOTATION_EVIDENCE, warnings)
    genome_variant = _read_by_gene(evidence_dir / GENOME_VARIANT_EVIDENCE, warnings)
    literature_rows = _read_tsv(evidence_dir / LITERATURE_EVIDENCE, warnings)
    doi_text = _doi_summary(literature_rows)
    variant_evidence = _variant_evidence_by_gene(variant_calling_dir, warnings)

    assessments = [
        _gene_assessment(
            gene_id=gene_id,
            transcriptome=transcriptome.get(gene_id, {}),
            metabolome=metabolome.get(gene_id, {}),
            annotation=annotation.get(gene_id, {}),
            genome_variant=genome_variant.get(gene_id, {}),
            variant_evidence=variant_evidence.get(gene_id, {}),
            doi_text=doi_text,
        )
        for gene_id in REQUIRED_GENE_IDS
    ]

    return LobsterStyleResult(
        reference_project_name=REFERENCE_PROJECT_NAME,
        reference_project_url=REFERENCE_PROJECT_URL,
        backend_name=BACKEND_NAME,
        backend_mode=BACKEND_MODE,
        target_genes=list(REQUIRED_GENE_IDS),
        evidence_used=build_lobster_reference_task(
            evidence_dir=evidence_dir,
            variant_calling_dir=variant_calling_dir,
        ).evidence_used,
        gene_assessments=assessments,
        limitations=[
            LOBSTER_MOCK_NOTICE,
            "No Lobster package was installed, imported, or executed.",
            "The result uses only current breeding-agent evidence tables.",
            "No new DOI, SNP/InDel coordinate, or promoter sequence is generated.",
            "KASP/CAPS are preliminary screening categories, not final marker designs.",
            "Candidate-region calling does not replace WGS/GBS population variant calling.",
        ],
        warnings=warnings,
        real_lobster_run=False,
    )


def render_lobster_style_agent_report(result: LobsterStyleResult) -> str:
    lines = [
        "# Lobster-style External Omics Agent Reference Report",
        "",
        LOBSTER_MOCK_NOTICE,
        "",
        f"- reference_project_name: {result.reference_project_name}",
        f"- reference_project_url: {result.reference_project_url}",
        f"- backend_name: {result.backend_name}",
        f"- backend_mode: {result.backend_mode}",
        f"- real_lobster_run: {str(result.real_lobster_run).lower()}",
        "",
        "## Evidence Used",
        "",
    ]
    lines.extend(f"- `{item}`" for item in result.evidence_used)
    lines.extend(["", "## Gene Assessments", ""])
    for assessment in result.gene_assessments:
        lines.extend(
            [
                f"### {assessment.gene_id}",
                "",
                f"- transcriptomics_support: {assessment.transcriptomics_support}",
                f"- metabolomics_support: {assessment.metabolomics_support}",
                f"- annotation_support: {assessment.annotation_support}",
                f"- literature_support: {assessment.literature_support}",
                f"- variant_support: {assessment.variant_support}",
                f"- confidence_label: {assessment.confidence_label}",
                "",
                f"General omics interpretation: {assessment.general_omics_interpretation}",
                "",
                f"Marker recommendation: {assessment.marker_recommendation}",
                "",
                f"Validation required: {assessment.validation_required}",
                "",
                "Limitations:",
            ]
        )
        lines.extend(f"- {item}" for item in assessment.limitations)
        if assessment.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {item}" for item in assessment.warnings)
        lines.append("")
    lines.extend(["## Global Limitations", ""])
    lines.extend(f"- {item}" for item in result.limitations)
    return "\n".join(lines).rstrip() + "\n"


def lobster_gene_assessments_to_rows(
    result: LobsterStyleResult,
) -> list[dict[str, str]]:
    return [
        {
            "gene_id": assessment.gene_id,
            "transcriptomics_support": assessment.transcriptomics_support,
            "metabolomics_support": assessment.metabolomics_support,
            "annotation_support": assessment.annotation_support,
            "literature_support": assessment.literature_support,
            "variant_support": assessment.variant_support,
            "general_omics_interpretation": assessment.general_omics_interpretation,
            "marker_recommendation": assessment.marker_recommendation,
            "validation_required": assessment.validation_required,
            "limitations": "; ".join(assessment.limitations),
            "warnings": "; ".join(assessment.warnings),
            "confidence_label": assessment.confidence_label,
        }
        for assessment in result.gene_assessments
    ]


def _gene_assessment(
    *,
    gene_id: str,
    transcriptome: dict[str, str],
    metabolome: dict[str, str],
    annotation: dict[str, str],
    genome_variant: dict[str, str],
    variant_evidence: dict[str, str],
    doi_text: str,
) -> LobsterStyleGeneAssessment:
    transcriptomics_support = _transcriptomics_support(transcriptome)
    metabolomics_support = _metabolomics_support(metabolome)
    annotation_support = _annotation_support(annotation)
    literature_support = doi_text or "literature DOI evidence not available"
    variant_support = _variant_support(genome_variant, variant_evidence)
    general_interpretation = (
        f"{gene_id} has transcriptomics, metabolomics, annotation, literature, "
        "and optional candidate-region variant evidence summarized for a crop "
        "breeding marker review context."
    )
    marker_recommendation = _marker_recommendation(variant_evidence)
    limitations = [
        LOBSTER_MOCK_NOTICE,
        "Do not treat this as a real Lobster AI execution.",
        "No SNP/InDel coordinates are added by this benchmark.",
        "LowQual variants, if present, are traceability records and should not be prioritized.",
        "KASP/CAPS entries remain preliminary screening, not final primer or enzyme plans.",
        "This candidate-region result does not replace WGS/GBS population variant calling.",
    ]
    warnings = []
    if not transcriptome:
        warnings.append(f"Missing transcriptomics evidence for {gene_id}.")
    if not annotation:
        warnings.append(f"Missing annotation evidence for {gene_id}.")
    if variant_evidence.get("variant_evidence_status") in {
        "no_called_variant_in_current_mini_calling",
        "variant_calling_output_missing",
    }:
        warnings.append(
            f"{gene_id} has no called PASS variant in the current mini candidate-region calling."
        )
    return LobsterStyleGeneAssessment(
        gene_id=gene_id,
        transcriptomics_support=transcriptomics_support,
        metabolomics_support=metabolomics_support,
        annotation_support=annotation_support,
        literature_support=literature_support,
        variant_support=variant_support,
        general_omics_interpretation=general_interpretation,
        marker_recommendation=marker_recommendation,
        validation_required=(
            "Validate candidate marker associations in a larger 群体 with genotype "
            "and flavonoid phenotype data; confirm candidates by Sanger/KASP/CAPS "
            "follow-up as appropriate."
        ),
        limitations=limitations,
        warnings=warnings,
        confidence_label=_confidence_label(transcriptome, metabolome, annotation, doi_text),
    )


def _transcriptomics_support(row: dict[str, str]) -> str:
    if not row:
        return "missing"
    return (
        "baseMean={baseMean}; log2FC={log2FC}; pvalue={pvalue}; padj={padj}; "
        "Direction={Direction}"
    ).format(
        baseMean=row.get("baseMean", ""),
        log2FC=row.get("log2FC", ""),
        pvalue=row.get("pvalue", ""),
        padj=row.get("padj", ""),
        Direction=row.get("Direction", ""),
    )


def _metabolomics_support(row: dict[str, str]) -> str:
    if not row:
        return "missing"
    return (
        "top_correlated_metabolite={metabolite}; top_pearson_r={pearson}; "
        "top_spls_metabolite={spls}"
    ).format(
        metabolite=row.get("top_correlated_metabolite", ""),
        pearson=row.get("top_pearson_r", ""),
        spls=row.get("top_spls_metabolite", ""),
    )


def _annotation_support(row: dict[str, str]) -> str:
    if not row:
        return "missing"
    return (
        "Description={description}; KEGG_ko={ko}; KEGG_Pathway={pathway}; PFAMs={pfams}"
    ).format(
        description=row.get("Description", ""),
        ko=row.get("KEGG_ko", ""),
        pathway=row.get("KEGG_Pathway", ""),
        pfams=row.get("PFAMs", ""),
    )


def _variant_support(
    genome_variant: dict[str, str],
    variant_evidence: dict[str, str],
) -> str:
    if variant_evidence:
        return (
            "variant_evidence_status={status}; pass_variants={pass_variants}; "
            "lowqual_variants={lowqual}; snp_count={snp}; indel_count={indel}; "
            "kasp_preliminary_pass={kasp}; caps_screening={caps}"
        ).format(
            status=variant_evidence.get("variant_evidence_status", ""),
            pass_variants=variant_evidence.get("pass_variants", "0"),
            lowqual=variant_evidence.get("lowqual_variants", "0"),
            snp=variant_evidence.get("snp_count", "0"),
            indel=variant_evidence.get("indel_count", "0"),
            kasp=variant_evidence.get("kasp_preliminary_pass_count", "0"),
            caps=variant_evidence.get(
                "caps_pass_variant_requires_enzyme_screening_count", "0"
            ),
        )
    return genome_variant.get("variant_status", "not_called")


def _marker_recommendation(variant_evidence: dict[str, str]) -> str:
    status = variant_evidence.get("variant_evidence_status", "")
    if status == "preliminary_pass_variants_detected":
        return (
            "Prioritize PASS SNP/InDel candidates for downstream marker review; "
            "screen KASP/CAPS feasibility as preliminary, not final design."
        )
    if status == "only_low_quality_variants_detected":
        return (
            "Retain LowQual variants for traceability only; do not directly prioritize "
            "them for KASP/CAPS development."
        )
    return (
        "No called variant is available in the current mini calling; keep SNP/InDel/"
        "KASP/CAPS as follow-up marker development categories after validated calling."
    )


def _confidence_label(
    transcriptome: dict[str, str],
    metabolome: dict[str, str],
    annotation: dict[str, str],
    doi_text: str,
) -> str:
    score = sum(bool(item) for item in [transcriptome, metabolome, annotation, doi_text])
    if score >= 4:
        return "multi_omics_traceable_reference"
    if score >= 2:
        return "partial_omics_traceable_reference"
    return "limited_reference"


def _doi_summary(rows: list[dict[str, str]]) -> str:
    dois = sorted({row.get("doi", "").strip() for row in rows if row.get("doi", "").strip()})
    if not dois:
        return ""
    return "DOI evidence: " + "; ".join(dois)


def _variant_evidence_by_gene(
    variant_calling_dir: Path | None,
    warnings: list[str],
) -> dict[str, dict[str, str]]:
    if not variant_calling_dir:
        return {}
    result = load_flavonoid_variant_evidence(variant_calling_dir)
    warnings.extend(result.warnings)
    return {row.get("gene_id", ""): row for row in result.rows if row.get("gene_id")}


def _read_by_gene(path: Path, warnings: list[str]) -> dict[str, dict[str, str]]:
    return {
        row["gene_id"]: row
        for row in _read_tsv(path, warnings)
        if row.get("gene_id")
    }


def _read_tsv(path: Path, warnings: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        warnings.append(f"Evidence file missing: {path}")
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]
