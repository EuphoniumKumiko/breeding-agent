"""Genomics region and annotation analysis from the mini package."""

from __future__ import annotations

import csv
from pathlib import Path


TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")

INPUT_FILES = {
    "genome_fasta": Path("genome.fa"),
    "genome_gff": Path("genome.gff"),
    "genome_original_coords_gff": Path("genome.original_coords.gff"),
    "genome_bam_compatible_fasta": Path("genome.bam_compatible.fa.gz"),
    "regions_bed": Path("regions") / "regions.bed",
    "regions_samtools": Path("regions") / "regions.samtools.txt",
    "deg_features": Path("regions") / "deg_features.tsv",
    "target_genes": Path("target_genes.tsv"),
    "local_region_emapper_annotations": (
        Path("annotations") / "local_region_emapper_annotations.tsv"
    ),
    "target_gene_emapper_annotations": (
        Path("annotations") / "target_gene_emapper_annotations.tsv"
    ),
    "target_gene_evidence_summary": (
        Path("annotations") / "target_gene_evidence_summary.tsv"
    ),
}

TARGET_GENE_REGION_COLUMNS = [
    "gene_id",
    "resolved_id",
    "resolved_type",
    "chrom",
    "start",
    "end",
    "strand",
    "region_chrom",
    "region_start",
    "region_end",
    "region_name",
    "region_samtools",
    "source_file",
]
ANNOTATION_SUMMARY_COLUMNS = [
    "gene_id",
    "Description",
    "Preferred_name",
    "KEGG_ko",
    "KEGG_Pathway",
    "PFAMs",
    "source_file",
]
MARKER_READINESS_COLUMNS = [
    "gene_id",
    "variant_status",
    "candidate_marker_types",
    "readiness_summary",
    "required_next_step",
    "source_file",
]

VARIANT_NEXT_STEP = (
    "当前 mini 数据包未提供最终 SNP/InDel 位点；后续需要基于 BAM、"
    "genome.fa/genome.gff 或 genome.bam_compatible.fa.gz 与 "
    "genome.original_coords.gff 进行候选区域 SNP/InDel calling，再筛选 "
    "KASP/CAPS 可转化位点。"
)


def build_genomics_region_analysis(
    *,
    dataset_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Build region, annotation, and marker readiness tables."""

    output_dir.mkdir(parents=True, exist_ok=True)
    warnings = _missing_input_warnings(dataset_dir)
    input_status = _input_status(dataset_dir)

    target_regions = _target_gene_regions(dataset_dir)
    annotation_summary = _annotation_summary(dataset_dir)
    marker_readiness = _marker_readiness(dataset_dir)

    target_regions_file = output_dir / "target_gene_regions.tsv"
    annotation_summary_file = output_dir / "annotation_summary.tsv"
    marker_readiness_file = output_dir / "marker_readiness.tsv"

    _write_tsv(target_regions_file, TARGET_GENE_REGION_COLUMNS, target_regions)
    _write_tsv(annotation_summary_file, ANNOTATION_SUMMARY_COLUMNS, annotation_summary)
    _write_tsv(marker_readiness_file, MARKER_READINESS_COLUMNS, marker_readiness)

    return {
        "task_name": "genomics_region",
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "inputs": input_status,
        "outputs": {
            "target_gene_regions": str(target_regions_file),
            "annotation_summary": str(annotation_summary_file),
            "marker_readiness": str(marker_readiness_file),
        },
        "row_counts": {
            "target_gene_regions": len(target_regions),
            "annotation_summary": len(annotation_summary),
            "marker_readiness": len(marker_readiness),
        },
        "warnings": warnings,
        "target_genes": list(TARGET_GENES),
        "target_regions": target_regions,
        "annotation_summary": annotation_summary,
        "marker_readiness": marker_readiness,
    }


def _missing_input_warnings(dataset_dir: Path) -> list[str]:
    warnings = []
    for relative_path in INPUT_FILES.values():
        path = dataset_dir / relative_path
        if not path.exists():
            warnings.append(f"Input file missing: {path}")
    return warnings


def _input_status(dataset_dir: Path) -> dict[str, dict[str, object]]:
    status = {}
    for key, relative_path in INPUT_FILES.items():
        path = dataset_dir / relative_path
        status[key] = {
            "path": str(path),
            "exists": path.exists(),
        }
    return status


def _target_gene_regions(dataset_dir: Path) -> list[dict[str, str]]:
    deg_features_path = dataset_dir / INPUT_FILES["deg_features"]
    features = _read_dict_rows(deg_features_path)
    feature_rows = [
        row for row in features if row.get("deg_id") or row.get("resolved_id")
    ]
    regions = _read_bed_rows(dataset_dir / INPUT_FILES["regions_bed"])
    samtools_regions = _read_lines(dataset_dir / INPUT_FILES["regions_samtools"])

    if not feature_rows:
        feature_rows = [
            {
                "deg_id": gene_id,
                "resolved_id": gene_id,
                "resolved_type": "",
                "chrom": "",
                "start": "",
                "end": "",
                "strand": "",
            }
            for gene_id in TARGET_GENES
        ]

    output = []
    for row in feature_rows:
        gene_id = row.get("deg_id") or row.get("resolved_id") or ""
        matched_region, region_index = _match_region(row, regions)
        output.append(
            {
                "gene_id": gene_id,
                "resolved_id": row.get("resolved_id", ""),
                "resolved_type": row.get("resolved_type", ""),
                "chrom": row.get("chrom", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "strand": row.get("strand", ""),
                "region_chrom": matched_region.get("chrom", ""),
                "region_start": matched_region.get("start", ""),
                "region_end": matched_region.get("end", ""),
                "region_name": matched_region.get("name", ""),
                "region_samtools": (
                    samtools_regions[region_index]
                    if 0 <= region_index < len(samtools_regions)
                    else ""
                ),
                "source_file": str(deg_features_path),
            }
        )
    return output


def _annotation_summary(dataset_dir: Path) -> list[dict[str, str]]:
    annotation_path = dataset_dir / INPUT_FILES["target_gene_emapper_annotations"]
    rows = _read_dict_rows(annotation_path)
    if not rows:
        annotation_path = dataset_dir / INPUT_FILES["target_gene_evidence_summary"]
        rows = _read_dict_rows(annotation_path)

    output = []
    seen: set[str] = set()
    for row in rows:
        gene_id = row.get("query") or row.get("Gene") or ""
        if not gene_id:
            continue
        seen.add(gene_id)
        output.append(
            {
                "gene_id": gene_id,
                "Description": row.get("Description", ""),
                "Preferred_name": row.get("Preferred_name", ""),
                "KEGG_ko": row.get("KEGG_ko", ""),
                "KEGG_Pathway": row.get("KEGG_Pathway", ""),
                "PFAMs": row.get("PFAMs", ""),
                "source_file": str(annotation_path),
            }
        )

    for gene_id in TARGET_GENES:
        if gene_id not in seen:
            output.append(
                {
                    "gene_id": gene_id,
                    "Description": "",
                    "Preferred_name": "",
                    "KEGG_ko": "",
                    "KEGG_Pathway": "",
                    "PFAMs": "",
                    "source_file": str(annotation_path),
                }
            )
    return output


def _marker_readiness(dataset_dir: Path) -> list[dict[str, str]]:
    source_file = " + ".join(
        [
            str(dataset_dir / INPUT_FILES["regions_bed"]),
            str(dataset_dir / INPUT_FILES["target_gene_emapper_annotations"]),
            str(dataset_dir / INPUT_FILES["genome_bam_compatible_fasta"]),
            str(dataset_dir / INPUT_FILES["genome_original_coords_gff"]),
        ]
    )
    return [
        {
            "gene_id": gene_id,
            "variant_status": "not_called",
            "candidate_marker_types": "SNP/InDel/KASP/CAPS",
            "readiness_summary": (
                "已有候选区域和功能注释证据，可进入候选区域变异检测设计；"
                "尚不能输出正式标记位点。"
            ),
            "required_next_step": VARIANT_NEXT_STEP,
            "source_file": source_file,
        }
        for gene_id in TARGET_GENES
    ]


def _read_dict_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _read_bed_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) < 3:
                continue
            rows.append(
                {
                    "chrom": row[0],
                    "start": row[1],
                    "end": row[2],
                    "name": row[3] if len(row) > 3 else "",
                }
            )
    return rows


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def _match_region(
    feature: dict[str, str],
    regions: list[dict[str, str]],
) -> tuple[dict[str, str], int]:
    chrom = feature.get("chrom", "")
    try:
        feature_start = int(feature.get("start", ""))
        feature_end = int(feature.get("end", ""))
    except ValueError:
        return {}, -1

    for index, region in enumerate(regions):
        if region.get("chrom") != chrom:
            continue
        try:
            region_start_1based = int(region.get("start", "")) + 1
            region_end = int(region.get("end", ""))
        except ValueError:
            continue
        if region_start_1based <= feature_start and feature_end <= region_end:
            return region, index
    return {}, -1


def _write_tsv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
