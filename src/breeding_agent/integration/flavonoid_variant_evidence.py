"""Optional variant-calling evidence loader for flavonoid marker aggregation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")
DEFAULT_VARIANT_CALLING_DIR = Path("outputs/genomics_variant_calling")

CANDIDATE_VARIANTS_FILE = "candidate_variants.tsv"
KASP_CANDIDATES_FILE = "kasp_candidate_sites.tsv"
CAPS_CANDIDATES_FILE = "caps_candidate_sites.tsv"


@dataclass(frozen=True)
class FlavonoidVariantEvidenceResult:
    variant_calling_dir: Path
    rows: list[dict[str, str]]
    warnings: list[str]
    loaded: bool


def load_flavonoid_variant_evidence(
    variant_calling_dir: Path = DEFAULT_VARIANT_CALLING_DIR,
    target_genes: tuple[str, ...] = TARGET_GENES,
) -> FlavonoidVariantEvidenceResult:
    """Load optional candidate-region variant evidence grouped by target gene."""

    warnings: list[str] = []
    tables_dir = variant_calling_dir / "tables"
    candidate_file = tables_dir / CANDIDATE_VARIANTS_FILE
    kasp_file = tables_dir / KASP_CANDIDATES_FILE
    caps_file = tables_dir / CAPS_CANDIDATES_FILE

    required_files = [candidate_file, kasp_file, caps_file]
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        warnings.extend(
            f"Variant calling output missing: {path}" for path in missing_files
        )
        return FlavonoidVariantEvidenceResult(
            variant_calling_dir=variant_calling_dir,
            rows=[
                _empty_row(gene_id, "variant_calling_output_missing")
                for gene_id in target_genes
            ],
            warnings=warnings,
            loaded=False,
        )

    candidate_rows = _read_tsv(candidate_file, warnings)
    kasp_rows = _read_tsv(kasp_file, warnings)
    caps_rows = _read_tsv(caps_file, warnings)

    rows = [
        _summarize_gene_variant_evidence(
            gene_id=gene_id,
            candidate_rows=candidate_rows,
            kasp_rows=kasp_rows,
            caps_rows=caps_rows,
        )
        for gene_id in target_genes
    ]
    return FlavonoidVariantEvidenceResult(
        variant_calling_dir=variant_calling_dir,
        rows=rows,
        warnings=warnings,
        loaded=True,
    )


def _summarize_gene_variant_evidence(
    *,
    gene_id: str,
    candidate_rows: list[dict[str, str]],
    kasp_rows: list[dict[str, str]],
    caps_rows: list[dict[str, str]],
) -> dict[str, str]:
    gene_variants = [
        row
        for row in candidate_rows
        if row.get("nearest_or_target_gene", "").strip() == gene_id
    ]
    gene_kasp = [
        row for row in kasp_rows if row.get("gene_id", "").strip() == gene_id
    ]
    gene_caps = [
        row for row in caps_rows if row.get("gene_id", "").strip() == gene_id
    ]

    total_variants = len(gene_variants)
    pass_variants = sum(1 for row in gene_variants if _is_pass(row))
    lowqual_variants = total_variants - pass_variants
    snp_rows = [row for row in gene_variants if row.get("variant_type") == "SNP"]
    indel_rows = [row for row in gene_variants if row.get("variant_type") == "INDEL"]
    pass_snp_count = sum(1 for row in snp_rows if _is_pass(row))
    lowqual_snp_count = len(snp_rows) - pass_snp_count

    if pass_variants > 0:
        status = "preliminary_pass_variants_detected"
    elif lowqual_variants > 0:
        status = "only_low_quality_variants_detected"
    else:
        status = "no_called_variant_in_current_mini_calling"

    return {
        "gene_id": gene_id,
        "total_variants": str(total_variants),
        "pass_variants": str(pass_variants),
        "lowqual_variants": str(lowqual_variants),
        "snp_count": str(len(snp_rows)),
        "indel_count": str(len(indel_rows)),
        "pass_snp_count": str(pass_snp_count),
        "lowqual_snp_count": str(lowqual_snp_count),
        "kasp_preliminary_pass_count": str(
            _count(gene_kasp, "kasp_readiness", "preliminary_pass")
        ),
        "kasp_low_quality_review_required_count": str(
            _count(gene_kasp, "kasp_readiness", "low_quality_review_required")
        ),
        "caps_pass_variant_requires_enzyme_screening_count": str(
            _count(
                gene_caps,
                "caps_status",
                "pass_variant_requires_enzyme_screening",
            )
        ),
        "caps_low_quality_variant_requires_review_count": str(
            _count(gene_caps, "caps_status", "low_quality_variant_requires_review")
        ),
        "variant_evidence_status": status,
    }


def _empty_row(gene_id: str, status: str) -> dict[str, str]:
    return {
        "gene_id": gene_id,
        "total_variants": "0",
        "pass_variants": "0",
        "lowqual_variants": "0",
        "snp_count": "0",
        "indel_count": "0",
        "pass_snp_count": "0",
        "lowqual_snp_count": "0",
        "kasp_preliminary_pass_count": "0",
        "kasp_low_quality_review_required_count": "0",
        "caps_pass_variant_requires_enzyme_screening_count": "0",
        "caps_low_quality_variant_requires_review_count": "0",
        "variant_evidence_status": status,
    }


def _read_tsv(path: Path, warnings: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        warnings.append(f"Variant evidence file missing: {path}")
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def _is_pass(row: dict[str, str]) -> bool:
    return row.get("filter", "").strip() == "PASS"


def _count(rows: list[dict[str, str]], key: str, value: str) -> int:
    return sum(1 for row in rows if row.get(key, "").strip() == value)
