"""Metabolomics evidence analysis from the mini flavonoid package."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path


TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")

INPUT_FILES = {
    "raw_metabolome": Path("metabolome") / "metabolome_raw_3372.tsv",
    "candidate_metabolites": Path("metabolome") / "candidate_metabolites.tsv",
    "flavonoid_related_significant_metabolites": (
        Path("metabolome") / "flavonoid_related_significant_metabolites.tsv"
    ),
    "target_gene_metabolite_network_edges": (
        Path("metabolome") / "target_gene_metabolite_network_edges.tsv"
    ),
    "target_gene_spls_coefficients": (
        Path("metabolome") / "target_gene_spls_coefficients.tsv"
    ),
    "target_gene_related_metabolite_abundance": (
        Path("metabolome") / "target_gene_related_metabolite_abundance.tsv"
    ),
    "sample_metadata": Path("sample_metadata.tsv"),
    "target_gene_evidence_summary": (
        Path("annotations") / "target_gene_evidence_summary.tsv"
    ),
}

OUTPUT_TABLES = {
    "candidate_metabolites": "candidate_metabolites.tsv",
    "flavonoid_related_significant_metabolites": (
        "flavonoid_related_significant_metabolites.tsv"
    ),
    "target_gene_metabolite_network_edges": (
        "target_gene_metabolite_network_edges.tsv"
    ),
    "target_gene_spls_coefficients": "target_gene_spls_coefficients.tsv",
}

DEFAULT_HEADERS = {
    "candidate_metabolites": [
        "Index",
        "Compounds",
        "Class I",
        "Class II",
        "Green_mean",
        "Golden_mean",
        "VIP",
        "P_value",
        "FDR",
        "Log2FC",
        "Direction",
        "Candidate_score",
    ],
    "flavonoid_related_significant_metabolites": [
        "Index",
        "Compounds",
        "Class I",
        "Class II",
        "Green_mean",
        "Golden_mean",
        "VIP",
        "P_value",
        "FDR",
        "Log2FC",
        "Direction",
    ],
    "target_gene_metabolite_network_edges": [
        "Gene",
        "Metabolite_index",
        "Metabolite_name",
        "Metabolite_subclass",
        "Pearson_r",
        "Pearson_FDR",
        "edge_sign",
        "edge_weight",
    ],
    "target_gene_spls_coefficients": [
        "Gene",
        "Metabolite_index",
        "Coefficient",
        "Metabolite_name",
        "abs_coefficient",
    ],
}


def build_metabolomics_evidence(*, dataset_dir: Path, output_dir: Path) -> dict[str, object]:
    """Copy package-derived metabolomics evidence tables and summarize them."""

    output_dir.mkdir(parents=True, exist_ok=True)
    warnings = _missing_input_warnings(dataset_dir)
    outputs: dict[str, str] = {}
    row_counts: dict[str, int] = {}

    for input_key, filename in OUTPUT_TABLES.items():
        source = dataset_dir / INPUT_FILES[input_key]
        target = output_dir / filename
        row_counts[input_key] = _copy_existing_or_write_empty(
            source=source,
            target=target,
            fallback_header=DEFAULT_HEADERS[input_key],
        )
        outputs[input_key] = str(target)

    summary_path = dataset_dir / INPUT_FILES["target_gene_evidence_summary"]
    network_path = output_dir / OUTPUT_TABLES["target_gene_metabolite_network_edges"]
    spls_path = output_dir / OUTPUT_TABLES["target_gene_spls_coefficients"]

    target_gene_summary = _target_gene_summary(summary_path)
    network_counts = _count_by_column(network_path, "Gene")
    spls_counts = _count_by_column(spls_path, "Gene")
    candidate_preview = _read_preview(output_dir / OUTPUT_TABLES["candidate_metabolites"])
    significant_preview = _read_preview(
        output_dir / OUTPUT_TABLES["flavonoid_related_significant_metabolites"]
    )
    top_network_edges = _read_preview(network_path)
    top_spls_coefficients = _read_preview(spls_path)

    return {
        "task_name": "metabolomics_evidence",
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "inputs": _input_status(dataset_dir),
        "outputs": outputs,
        "row_counts": row_counts,
        "warnings": warnings,
        "target_genes": list(TARGET_GENES),
        "target_gene_summary": target_gene_summary,
        "network_counts": network_counts,
        "spls_counts": spls_counts,
        "candidate_preview": candidate_preview,
        "significant_preview": significant_preview,
        "top_network_edges": top_network_edges,
        "top_spls_coefficients": top_spls_coefficients,
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


def _copy_existing_or_write_empty(
    *,
    source: Path,
    target: Path,
    fallback_header: list[str],
) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists() and source.is_file():
        shutil.copyfile(source, target)
        return _count_data_rows(target)

    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(fallback_header)
    return 0


def _count_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _read_dict_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _target_gene_summary(summary_path: Path) -> list[dict[str, str]]:
    rows = _read_dict_rows(summary_path)
    rows_by_gene = {row.get("Gene", ""): row for row in rows}
    summary = []
    for gene_id in TARGET_GENES:
        row = rows_by_gene.get(gene_id, {})
        summary.append(
            {
                "gene_id": gene_id,
                "description": row.get("Description", ""),
                "direction": row.get("Direction", ""),
                "n_network_edges": row.get("n_network_edges", ""),
                "max_abs_pearson": row.get("max_abs_pearson", ""),
                "top_correlated_metabolite": row.get(
                    "top_correlated_metabolite", ""
                ),
                "top_pearson_r": row.get("top_pearson_r", ""),
                "n_spls_coefficients": row.get("n_spls_coefficients", ""),
                "max_abs_spls_coefficient": row.get(
                    "max_abs_spls_coefficient", ""
                ),
                "top_spls_metabolite": row.get("top_spls_metabolite", ""),
            }
        )
    return summary


def _count_by_column(path: Path, column: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in _read_dict_rows(path):
        key = row.get(column, "")
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _read_preview(path: Path, limit: int = 8) -> list[dict[str, str]]:
    return _read_dict_rows(path)[:limit]
