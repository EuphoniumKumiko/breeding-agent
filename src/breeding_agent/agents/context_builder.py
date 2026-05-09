"""Build structured context for flavonoid marker agents."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

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


def build_flavonoid_agent_context(
    *,
    evidence_dir: Path,
    candidate_rows: list[dict[str, str]] | None = None,
    variant_calling_dir: Path | None = None,
    variant_evidence_rows: list[dict[str, str]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a structured, LLM-ready context without calling an LLM."""

    context_warnings = list(warnings or [])
    evidence_files = {
        "transcriptomics": evidence_dir / TRANSCRIPTOME_EVIDENCE,
        "metabolomics": evidence_dir / METABOLOME_EVIDENCE,
        "annotation": evidence_dir / ANNOTATION_EVIDENCE,
        "genome_variant": evidence_dir / GENOME_VARIANT_EVIDENCE,
        "literature": evidence_dir / LITERATURE_EVIDENCE,
    }
    transcriptomics_rows = _read_tsv(evidence_files["transcriptomics"], context_warnings)
    metabolomics_rows = _read_tsv(evidence_files["metabolomics"], context_warnings)
    annotation_rows = _read_tsv(evidence_files["annotation"], context_warnings)
    genome_variant_rows = _read_tsv(evidence_files["genome_variant"], context_warnings)
    literature_rows = _read_tsv(evidence_files["literature"], context_warnings)

    loaded_variant_rows = list(variant_evidence_rows or [])
    variant_calling_loaded = False
    if variant_calling_dir is not None and not loaded_variant_rows:
        variant_result = load_flavonoid_variant_evidence(variant_calling_dir)
        loaded_variant_rows = variant_result.rows
        variant_calling_loaded = variant_result.loaded
        context_warnings.extend(variant_result.warnings)
    elif variant_calling_dir is not None:
        variant_calling_loaded = True

    evidence_by_gene = {
        gene_id: {
            "transcriptomics": _row_by_gene(transcriptomics_rows, gene_id),
            "metabolomics": _row_by_gene(metabolomics_rows, gene_id),
            "annotation": _row_by_gene(annotation_rows, gene_id),
            "genome_variant": _row_by_gene(genome_variant_rows, gene_id),
            "variant_calling": _row_by_gene(loaded_variant_rows, gene_id),
            "candidate": _row_by_gene(candidate_rows or [], gene_id),
        }
        for gene_id in REQUIRED_GENE_IDS
    }

    return {
        "task": "flavonoid_marker_recommendation",
        "target_genes": list(REQUIRED_GENE_IDS),
        "hard_requirements": {
            "core_inputs": {
                "transcriptomics": "bam/ 中所有文件",
                "metabolomics": "metabolome_raw_3372.tsv",
                "genome": "genome.fa 和 genome.gff",
                "annotation": "local_region_emapper_annotations.tsv",
            },
            "required_conclusion": (
                "优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 "
                "SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。"
            ),
            "do_not_fabricate_doi": True,
            "do_not_fabricate_variant_positions": True,
            "lowqual_not_prioritized": True,
            "preliminary_kasp_caps_not_final": True,
            "variant_calling_not_wgs_gbs_population_calling": True,
        },
        "evidence_dir": str(evidence_dir),
        "evidence_files": {key: str(path) for key, path in evidence_files.items()},
        "transcriptomics_evidence": transcriptomics_rows,
        "metabolomics_evidence": metabolomics_rows,
        "annotation_evidence": annotation_rows,
        "genome_variant_evidence": genome_variant_rows,
        "literature_evidence": literature_rows,
        "variant_calling_evidence": loaded_variant_rows,
        "candidate_rows": list(candidate_rows or []),
        "evidence_by_gene": evidence_by_gene,
        "variant_calling": {
            "dir": str(variant_calling_dir) if variant_calling_dir else None,
            "loaded": variant_calling_loaded,
        },
        "warnings": context_warnings,
    }


def _read_tsv(path: Path, warnings: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        warnings.append(f"Context evidence file missing: {path}")
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def _row_by_gene(rows: list[dict[str, str]], gene_id: str) -> dict[str, str]:
    for row in rows:
        if row.get("gene_id", "").strip() == gene_id:
            return row
    return {}
