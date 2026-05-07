"""Parse DEG significant gene result tables."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


TARGET_GENE_ID = "Si9g04210.1"


@dataclass(frozen=True)
class TargetGeneResult:
    found: bool
    logfc: float | None = None
    adj_p_val: float | None = None
    mean_count_jm: float | None = None
    mean_count_lm: float | None = None


@dataclass(frozen=True)
class DegResultSummary:
    significant_gene_count: int
    target_gene_id: str
    target_gene: TargetGeneResult
    result_file: Path


def parse_deg_results(
    outdir: Path,
    prefix: str,
    *,
    target_gene_id: str = TARGET_GENE_ID,
) -> DegResultSummary:
    result_file = outdir / "mini_de" / f"{prefix}.significant_genes.tsv"
    if not result_file.exists():
        raise FileNotFoundError(f"DEG result file does not exist: {result_file}")

    significant_gene_count = 0
    target_gene = TargetGeneResult(found=False)

    with result_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            significant_gene_count += 1
            gene_id = _get_first(row, "Geneid", "gene_id", "gene", "Gene")
            if gene_id == target_gene_id:
                target_gene = TargetGeneResult(
                    found=True,
                    logfc=_parse_float(row.get("logFC")),
                    adj_p_val=_parse_float(row.get("adj.P.Val")),
                    mean_count_jm=_parse_float(row.get("mean_count_JM")),
                    mean_count_lm=_parse_float(row.get("mean_count_LM")),
                )

    return DegResultSummary(
        significant_gene_count=significant_gene_count,
        target_gene_id=target_gene_id,
        target_gene=target_gene,
        result_file=result_file,
    )


def _get_first(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return None


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None

