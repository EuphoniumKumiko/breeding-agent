"""Rule-based aggregation for foxtail millet flavonoid marker evidence."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


REQUIRED_GENE_IDS = ["Si9g04210.1", "Si5g31340.1", "Si9g34380.1"]

TRANSCRIPTOME_EVIDENCE = "transcriptome_evidence.tsv"
METABOLOME_EVIDENCE = "metabolome_evidence.tsv"
ANNOTATION_EVIDENCE = "annotation_evidence.tsv"
GENOME_VARIANT_EVIDENCE = "genome_variant_evidence.tsv"
LITERATURE_EVIDENCE = "literature_evidence.tsv"

CANDIDATE_FILENAME = "flavonoid_marker_candidates.tsv"
CANDIDATE_COLUMNS = [
    "gene_id",
    "baseMean",
    "log2FC",
    "pvalue",
    "padj",
    "Green_mean",
    "Golden_mean",
    "Direction",
    "top_correlated_metabolite",
    "top_pearson_r",
    "top_spls_metabolite",
    "function_annotation",
    "KEGG_ko",
    "KEGG_Pathway",
    "PFAMs",
    "variant_status",
    "marker_recommendation",
    "evidence_warnings",
]

NOT_CALLED_VARIANT_NOTE = (
    "当前 mini 数据包未提供最终 SNP/InDel 位点；建议后续基于 BAM、genome.fa/"
    "genome.gff 或 genome.bam_compatible.fa.gz 与 genome.original_coords.gff "
    "进行候选区域 SNP/InDel calling，再筛选 KASP/CAPS 可转化位点。"
)


@dataclass(frozen=True)
class FlavonoidMarkerAggregationResult:
    candidate_file: Path
    candidate_rows: list[dict[str, str]]
    literature_rows: list[dict[str, str]]
    warnings: list[str]


def aggregate_flavonoid_marker_candidates(
    *,
    evidence_dir: Path,
    outdir: Path,
) -> FlavonoidMarkerAggregationResult:
    """Aggregate standard evidence files into fixed target-gene candidates."""

    integration_dir = outdir / "integration"
    integration_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    transcriptome_rows = _read_gene_evidence(
        evidence_dir / TRANSCRIPTOME_EVIDENCE,
        warnings=warnings,
    )
    metabolome_rows = _read_gene_evidence(
        evidence_dir / METABOLOME_EVIDENCE,
        warnings=warnings,
    )
    annotation_rows = _read_gene_evidence(
        evidence_dir / ANNOTATION_EVIDENCE,
        warnings=warnings,
    )
    variant_rows = _read_gene_evidence(
        evidence_dir / GENOME_VARIANT_EVIDENCE,
        warnings=warnings,
    )
    literature_rows = _read_evidence_rows(
        evidence_dir / LITERATURE_EVIDENCE,
        warnings=warnings,
    )

    candidate_rows = [
        _candidate_row(
            gene_id=gene_id,
            transcriptome=transcriptome_rows.get(gene_id, {}),
            metabolome=metabolome_rows.get(gene_id, {}),
            annotation=annotation_rows.get(gene_id, {}),
            variant=variant_rows.get(gene_id, {}),
            warnings=warnings,
        )
        for gene_id in REQUIRED_GENE_IDS
    ]

    candidate_file = integration_dir / CANDIDATE_FILENAME
    _write_tsv(candidate_file, CANDIDATE_COLUMNS, candidate_rows)
    return FlavonoidMarkerAggregationResult(
        candidate_file=candidate_file,
        candidate_rows=candidate_rows,
        literature_rows=literature_rows,
        warnings=warnings,
    )


def read_flavonoid_marker_candidates(candidate_file: Path) -> list[dict[str, str]]:
    """Read an aggregated flavonoid marker candidate table."""

    return _read_evidence_rows(candidate_file, warnings=[])


def read_literature_evidence(evidence_dir: Path) -> list[dict[str, str]]:
    """Read literature evidence rows if the evidence file exists."""

    return _read_evidence_rows(evidence_dir / LITERATURE_EVIDENCE, warnings=[])


def _read_gene_evidence(
    path: Path,
    *,
    warnings: list[str],
) -> dict[str, dict[str, str]]:
    rows = _read_evidence_rows(path, warnings=warnings)
    return {
        row["gene_id"].strip(): row
        for row in rows
        if row.get("gene_id", "").strip()
    }


def _read_evidence_rows(path: Path, *, warnings: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        warnings.append(f"Evidence file missing: {path}")
        return []
    if not path.is_file():
        warnings.append(f"Evidence path is not a file: {path}")
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _candidate_row(
    *,
    gene_id: str,
    transcriptome: dict[str, str],
    metabolome: dict[str, str],
    annotation: dict[str, str],
    variant: dict[str, str],
    warnings: list[str],
) -> dict[str, str]:
    variant_status = _value(variant, "variant_status", default="not_called")
    marker_recommendation = _marker_recommendation(variant_status)
    row_warnings = _row_warnings(
        gene_id=gene_id,
        transcriptome=transcriptome,
        metabolome=metabolome,
        annotation=annotation,
        variant=variant,
    )

    return {
        "gene_id": gene_id,
        "baseMean": _value(transcriptome, "baseMean"),
        "log2FC": _value(transcriptome, "log2FC"),
        "pvalue": _value(transcriptome, "pvalue"),
        "padj": _value(transcriptome, "padj"),
        "Green_mean": _value(transcriptome, "Green_mean"),
        "Golden_mean": _value(transcriptome, "Golden_mean"),
        "Direction": _value(transcriptome, "Direction"),
        "top_correlated_metabolite": _value(
            metabolome,
            "top_correlated_metabolite",
        ),
        "top_pearson_r": _value(metabolome, "top_pearson_r"),
        "top_spls_metabolite": _value(metabolome, "top_spls_metabolite"),
        "function_annotation": _value(annotation, "Description"),
        "KEGG_ko": _value(annotation, "KEGG_ko"),
        "KEGG_Pathway": _value(annotation, "KEGG_Pathway"),
        "PFAMs": _value(annotation, "PFAMs"),
        "variant_status": variant_status,
        "marker_recommendation": marker_recommendation,
        "evidence_warnings": "; ".join([*warnings, *row_warnings]),
    }


def _marker_recommendation(variant_status: str) -> str:
    if variant_status == "not_called":
        return (
            "variant_status=not_called; 先进行候选区域 SNP/InDel calling。获得可靠"
            "多态位点后，优先将高质量 SNP/InDel 转化为 KASP 标记；若变异影响"
            "限制性内切酶识别位点，可补充开发 CAPS 标记。"
        )
    return (
        "优先评估已 calling 的 SNP/InDel 位点；选择高置信、与黄酮表型相关的"
        "位点开发 KASP 标记，并筛选可设计限制性酶切实验的 CAPS 标记。"
    )


def _row_warnings(
    *,
    gene_id: str,
    transcriptome: dict[str, str],
    metabolome: dict[str, str],
    annotation: dict[str, str],
    variant: dict[str, str],
) -> list[str]:
    warnings = []
    evidence_by_name = {
        "transcriptome": transcriptome,
        "metabolome": metabolome,
        "annotation": annotation,
        "genome_variant": variant,
    }
    for evidence_name, row in evidence_by_name.items():
        if not row:
            warnings.append(f"{evidence_name} evidence missing for {gene_id}")
    return warnings


def _value(row: dict[str, str], key: str, *, default: str = "") -> str:
    value = row.get(key, default)
    if value is None:
        return default
    return value.strip()


def _write_tsv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
