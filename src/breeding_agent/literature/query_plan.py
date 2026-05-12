"""Schema and writers for offline literature query plans."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


QUERY_PLAN_JSONL = "literature_query_plan.jsonl"
QUERY_PLAN_TSV = "literature_query_plan.tsv"


@dataclass(frozen=True)
class LiteratureQuery:
    """One offline literature search query generated from current evidence."""

    query_id: str
    query: str
    crop: str
    trait: str
    gene_id: str
    query_type: str
    keywords: list[str]
    source_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable row."""

        return {
            "query_id": self.query_id,
            "query": self.query,
            "crop": self.crop,
            "trait": self.trait,
            "gene_id": self.gene_id,
            "query_type": self.query_type,
            "keywords": list(self.keywords),
            "source_terms": list(self.source_terms),
        }

    def to_tsv_row(self) -> dict[str, str]:
        """Return a TSV-friendly row."""

        data = self.to_dict()
        return {
            key: ";".join(value) if isinstance(value, list) else str(value)
            for key, value in data.items()
        }


def write_literature_query_plan(
    *,
    outdir: Path,
    query_plan: list[dict[str, Any]] | list[LiteratureQuery],
) -> dict[str, Path]:
    """Write query plan JSONL and TSV files under outdir/literature.

    The JSONL is the machine-friendly handoff to the literature pipeline; the
    TSV exists for quick human inspection in reports and notebooks.
    """

    literature_dir = outdir / "literature"
    literature_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = literature_dir / QUERY_PLAN_JSONL
    tsv_path = literature_dir / QUERY_PLAN_TSV
    rows = [_coerce_query(row) for row in query_plan]

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")

    fieldnames = [
        "query_id",
        "query",
        "crop",
        "trait",
        "gene_id",
        "query_type",
        "keywords",
        "source_terms",
    ]
    with tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(row.to_tsv_row() for row in rows)

    return {"jsonl": jsonl_path, "tsv": tsv_path}


def _coerce_query(row: dict[str, Any] | LiteratureQuery) -> LiteratureQuery:
    # Accept either the dataclass or a plain mapping so workflow state and file
    # serialization can share the same writer.
    if isinstance(row, LiteratureQuery):
        return row
    return LiteratureQuery(
        query_id=str(row.get("query_id", "")),
        query=str(row.get("query", "")),
        crop=str(row.get("crop", "")),
        trait=str(row.get("trait", "")),
        gene_id=str(row.get("gene_id", "")),
        query_type=str(row.get("query_type", "")),
        keywords=_string_list(row.get("keywords", [])),
        source_terms=_string_list(row.get("source_terms", [])),
    )


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]
