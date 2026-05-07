"""Create flavonoid marker evidence tables from the mini data package."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")
SUMMARY_RELATIVE_PATH = Path("annotations") / "target_gene_evidence_summary.tsv"

TRANSCRIPTOME_COLUMNS = [
    "gene_id",
    "baseMean",
    "log2FC",
    "pvalue",
    "padj",
    "Green_mean",
    "Golden_mean",
    "Direction",
    "source_file",
]
METABOLOME_COLUMNS = [
    "gene_id",
    "n_network_edges",
    "max_abs_pearson",
    "top_correlated_metabolite",
    "top_pearson_r",
    "n_spls_coefficients",
    "max_abs_spls_coefficient",
    "top_spls_metabolite",
    "source_file",
]
ANNOTATION_COLUMNS = [
    "gene_id",
    "Description",
    "Preferred_name",
    "KEGG_ko",
    "KEGG_Pathway",
    "PFAMs",
    "source_file",
]
GENOME_VARIANT_COLUMNS = [
    "gene_id",
    "variant_status",
    "marker_implication",
    "source_file",
]
LITERATURE_COLUMNS = [
    "query",
    "title",
    "year",
    "doi",
    "url",
    "relevance",
    "used_in_report",
]

REQUIRED_SUMMARY_COLUMNS = {
    "Gene",
    "baseMean",
    "log2FoldChange",
    "pvalue",
    "padj",
    "Green_mean",
    "Golden_mean",
    "Direction",
    "Description",
    "Preferred_name",
    "KEGG_ko",
    "KEGG_Pathway",
    "PFAMs",
    "n_network_edges",
    "max_abs_pearson",
    "top_correlated_metabolite",
    "top_pearson_r",
    "n_spls_coefficients",
    "max_abs_spls_coefficient",
    "top_spls_metabolite",
}

OPTIONAL_INPUTS = [
    Path("bam") / "TG5_101_JM_1.mini.sorted.bam",
    Path("bam") / "TG5_101_JM_2.mini.sorted.bam",
    Path("bam") / "TG5_101_JM_3.mini.sorted.bam",
    Path("bam") / "TG5_101_LM_1.mini.sorted.bam",
    Path("bam") / "TG5_101_LM_2.mini.sorted.bam",
    Path("bam") / "TG5_101_LM_3.mini.sorted.bam",
    Path("metabolome") / "metabolome_raw_3372.tsv",
    Path("genome.fa"),
    Path("genome.gff"),
    Path("genome.original_coords.gff"),
    Path("genome.bam_compatible.fa.gz"),
    Path("annotations") / "local_region_emapper_annotations.tsv",
    Path("annotations") / "target_gene_emapper_annotations.tsv",
    Path("transcriptome") / "target_gene_expression_and_de.tsv",
    Path("metabolome") / "target_gene_metabolite_network_edges.tsv",
    Path("metabolome") / "target_gene_spls_coefficients.tsv",
    Path("sample_metadata.tsv"),
    Path("target_genes.tsv"),
]

VARIANT_IMPLICATION = (
    "当前 mini 数据包未提供最终 SNP/InDel 位点；建议后续基于 BAM、"
    "genome.bam_compatible.fa.gz 和 genome.original_coords.gff 进行候选区域 "
    "SNP/InDel calling，再筛选 KASP/CAPS 可转化位点。"
)

LITERATURE_RECORDS = [
    {
        "query": "flavonoid biosynthesis marker evidence",
        "title": "Seed reference for plant flavonoid biosynthesis and regulation",
        "year": "2021",
        "doi": "10.3390/life11060578",
        "url": "https://doi.org/10.3390/life11060578",
        "relevance": "flavonoid biosynthesis background and pathway interpretation",
        "used_in_report": "yes",
    },
    {
        "query": "crop flavonoid pathway candidate genes",
        "title": "Seed reference for flavonoid pathway genes in plant trait studies",
        "year": "2021",
        "doi": "10.3389/fpls.2021.665530",
        "url": "https://doi.org/10.3389/fpls.2021.665530",
        "relevance": "candidate gene interpretation for flavonoid-related traits",
        "used_in_report": "yes",
    },
    {
        "query": "flavonoid analysis methods",
        "title": "Seed reference for flavonoid analysis and validation methods",
        "year": "2014",
        "doi": "10.1007/978-1-4939-0446-4_7",
        "url": "https://doi.org/10.1007/978-1-4939-0446-4_7",
        "relevance": "method reference for downstream flavonoid validation",
        "used_in_report": "yes",
    },
    {
        "query": "plant flavonoid genes literature support",
        "title": "Seed reference for plant flavonoid gene evidence",
        "year": "2016",
        "doi": "10.1134/S2079059716030114",
        "url": "https://doi.org/10.1134/S2079059716030114",
        "relevance": "literature support for flavonoid candidate marker discussion",
        "used_in_report": "yes",
    },
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create standard flavonoid marker aggregation evidence tables from "
            "the mini data package."
        )
    )
    parser.add_argument(
        "--dataset-dir",
        required=True,
        type=Path,
        help="Mini flavonoid marker data package directory.",
    )
    parser.add_argument(
        "--outdir",
        required=True,
        type=Path,
        help="Directory for generated evidence TSV files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_dir = args.dataset_dir.expanduser()
    outdir = args.outdir.expanduser()

    try:
        return create_evidence(dataset_dir=dataset_dir, outdir=outdir)
    except Exception as exc:
        print(f"[flavonoid-evidence:error] {exc}", file=sys.stderr)
        return 1


def create_evidence(*, dataset_dir: Path, outdir: Path) -> int:
    summary_file = dataset_dir / SUMMARY_RELATIVE_PATH
    if not summary_file.exists():
        raise FileNotFoundError(
            f"Required input file does not exist: {summary_file}"
        )
    if not summary_file.is_file():
        raise ValueError(f"Required input path is not a file: {summary_file}")

    _warn_missing_optional_inputs(dataset_dir)
    rows_by_gene = _read_summary_rows(summary_file)
    target_rows = {
        gene_id: rows_by_gene[gene_id]
        for gene_id in TARGET_GENES
        if gene_id in rows_by_gene
    }

    outdir.mkdir(parents=True, exist_ok=True)
    written_files: list[tuple[str, Path, int]] = []

    written_files.append(
        (
            "transcriptome_evidence.tsv",
            _write_tsv(
                outdir / "transcriptome_evidence.tsv",
                TRANSCRIPTOME_COLUMNS,
                _transcriptome_records(target_rows, summary_file),
            ),
            len(target_rows),
        )
    )
    written_files.append(
        (
            "metabolome_evidence.tsv",
            _write_tsv(
                outdir / "metabolome_evidence.tsv",
                METABOLOME_COLUMNS,
                _metabolome_records(target_rows, summary_file),
            ),
            len(target_rows),
        )
    )
    written_files.append(
        (
            "annotation_evidence.tsv",
            _write_tsv(
                outdir / "annotation_evidence.tsv",
                ANNOTATION_COLUMNS,
                _annotation_records(target_rows, summary_file),
            ),
            len(target_rows),
        )
    )
    genome_variant_records = _genome_variant_records(dataset_dir)
    written_files.append(
        (
            "genome_variant_evidence.tsv",
            _write_tsv(
                outdir / "genome_variant_evidence.tsv",
                GENOME_VARIANT_COLUMNS,
                genome_variant_records,
            ),
            len(genome_variant_records),
        )
    )
    written_files.append(
        (
            "literature_evidence.tsv",
            _write_tsv(
                outdir / "literature_evidence.tsv",
                LITERATURE_COLUMNS,
                LITERATURE_RECORDS,
            ),
            len(LITERATURE_RECORDS),
        )
    )

    _print_summary(written_files=written_files, target_rows=target_rows)
    return 0


def _warn_missing_optional_inputs(dataset_dir: Path) -> None:
    for relative_path in OPTIONAL_INPUTS:
        path = dataset_dir / relative_path
        if not path.exists():
            print(
                f"[flavonoid-evidence:warning] Optional package file missing: {path}",
                file=sys.stderr,
            )


def _read_summary_rows(summary_file: Path) -> dict[str, dict[str, str]]:
    with summary_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = set(reader.fieldnames or [])
        missing_columns = sorted(REQUIRED_SUMMARY_COLUMNS - fieldnames)
        if missing_columns:
            raise ValueError(
                "Missing required column(s) in "
                f"{summary_file}: {', '.join(missing_columns)}"
            )
        return {
            row["Gene"]: row
            for row in reader
            if row.get("Gene")
        }


def _transcriptome_records(
    target_rows: dict[str, dict[str, str]],
    source_file: Path,
) -> list[dict[str, str]]:
    records = []
    for gene_id in TARGET_GENES:
        row = target_rows.get(gene_id)
        if row is None:
            continue
        records.append(
            {
                "gene_id": gene_id,
                "baseMean": row.get("baseMean", ""),
                "log2FC": row.get("log2FoldChange", ""),
                "pvalue": row.get("pvalue", ""),
                "padj": row.get("padj", ""),
                "Green_mean": row.get("Green_mean", ""),
                "Golden_mean": row.get("Golden_mean", ""),
                "Direction": row.get("Direction", ""),
                "source_file": str(source_file),
            }
        )
    return records


def _metabolome_records(
    target_rows: dict[str, dict[str, str]],
    source_file: Path,
) -> list[dict[str, str]]:
    records = []
    for gene_id in TARGET_GENES:
        row = target_rows.get(gene_id)
        if row is None:
            continue
        records.append(
            {
                "gene_id": gene_id,
                "n_network_edges": row.get("n_network_edges", ""),
                "max_abs_pearson": row.get("max_abs_pearson", ""),
                "top_correlated_metabolite": row.get("top_correlated_metabolite", ""),
                "top_pearson_r": row.get("top_pearson_r", ""),
                "n_spls_coefficients": row.get("n_spls_coefficients", ""),
                "max_abs_spls_coefficient": row.get(
                    "max_abs_spls_coefficient", ""
                ),
                "top_spls_metabolite": row.get("top_spls_metabolite", ""),
                "source_file": str(source_file),
            }
        )
    return records


def _annotation_records(
    target_rows: dict[str, dict[str, str]],
    source_file: Path,
) -> list[dict[str, str]]:
    records = []
    for gene_id in TARGET_GENES:
        row = target_rows.get(gene_id)
        if row is None:
            continue
        records.append(
            {
                "gene_id": gene_id,
                "Description": row.get("Description", ""),
                "Preferred_name": row.get("Preferred_name", ""),
                "KEGG_ko": row.get("KEGG_ko", ""),
                "KEGG_Pathway": row.get("KEGG_Pathway", ""),
                "PFAMs": row.get("PFAMs", ""),
                "source_file": str(source_file),
            }
        )
    return records


def _genome_variant_records(dataset_dir: Path) -> list[dict[str, str]]:
    source_file = " + ".join(
        [
            str(dataset_dir / "bam"),
            str(dataset_dir / "genome.bam_compatible.fa.gz"),
            str(dataset_dir / "genome.original_coords.gff"),
        ]
    )
    return [
        {
            "gene_id": gene_id,
            "variant_status": "not_called",
            "marker_implication": VARIANT_IMPLICATION,
            "source_file": source_file,
        }
        for gene_id in TARGET_GENES
    ]


def _write_tsv(
    path: Path,
    fieldnames: list[str],
    records: list[dict[str, str]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(records)
    return path


def _print_summary(
    *,
    written_files: list[tuple[str, Path, int]],
    target_rows: dict[str, dict[str, str]],
) -> None:
    print("[flavonoid-evidence] Wrote evidence files:")
    for filename, path, row_count in written_files:
        print(f"[flavonoid-evidence]   {filename}: {path} ({row_count} rows)")

    missing_targets = [gene_id for gene_id in TARGET_GENES if gene_id not in target_rows]
    if missing_targets:
        print(
            "[flavonoid-evidence] Target genes present: no; "
            f"missing={', '.join(missing_targets)}"
        )
    else:
        print("[flavonoid-evidence] Target genes present: yes; all fixed targets found")


if __name__ == "__main__":
    raise SystemExit(main())
