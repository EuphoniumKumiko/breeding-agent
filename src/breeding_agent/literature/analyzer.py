"""Rule-based analysis for LiteratureAgent v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from breeding_agent.literature.schema import LiteratureRecord


TARGET_GENES = ["Si9g04210.1", "Si5g31340.1", "Si9g34380.1"]


@dataclass(frozen=True)
class LiteratureAnalysis:
    """Summary of verified DOI evidence and external search results."""

    literature_result_count: int
    literature_query_count: int
    real_result_count: int
    demo_result_count: int
    real_doi_count: int
    demo_doi_count: int
    verified_doi_count: int
    doi_sources: dict[str, list[str]]
    query_counts: dict[str, int]
    matched_terms: list[str]
    gene_hits: dict[str, int]
    literature_relevance_counts: dict[str, int]
    real_records: list[dict[str, Any]]
    demo_records: list[dict[str, Any]]

    @property
    def allowed_report_dois(self) -> set[str]:
        """All DOI values allowed to appear in a report."""

        return set(self.doi_sources.get("allowed_report_dois", []))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "literature_result_count": self.literature_result_count,
            "literature_query_count": self.literature_query_count,
            "real_result_count": self.real_result_count,
            "demo_result_count": self.demo_result_count,
            "real_doi_count": self.real_doi_count,
            "demo_doi_count": self.demo_doi_count,
            "verified_doi_count": self.verified_doi_count,
            "doi_sources": self.doi_sources,
            "query_counts": self.query_counts,
            "matched_terms": self.matched_terms,
            "gene_hits": self.gene_hits,
            "literature_relevance_counts": self.literature_relevance_counts,
            "real_records": self.real_records,
            "demo_records": self.demo_records,
            "allowed_report_dois": sorted(self.allowed_report_dois),
        }


def analyze_literature(
    *,
    verified_literature_rows: list[dict[str, str]],
    literature_results: list[LiteratureRecord],
) -> LiteratureAnalysis:
    """Analyze external literature results without LLM or network calls.

    Real records contribute to report-allowed DOI evidence and relevance
    counts; demo fixture rows remain traceable but do not count as evidence.
    """

    real_records = [record for record in literature_results if record.is_real_evidence]
    demo_records = [record for record in literature_results if not record.is_real_evidence]
    verified_dois = sorted(
        {
            _normalize_doi(row.get("doi", ""))
            for row in verified_literature_rows
            if _normalize_doi(row.get("doi", ""))
        }
    )
    real_result_dois = sorted({record.doi for record in real_records if record.doi})
    demo_dois = sorted({record.doi for record in demo_records if record.doi})
    allowed_report_dois = sorted(set(verified_dois) | set(real_result_dois))

    query_counts: dict[str, int] = {}
    matched_terms: set[str] = set()
    gene_hits = {gene_id: 0 for gene_id in TARGET_GENES}
    literature_relevance_counts = {"high": 0, "medium": 0, "background": 0}
    annotated_real_records: list[dict[str, Any]] = []
    annotated_demo_records: list[dict[str, Any]] = []
    for record in literature_results:
        query_counts[record.query] = query_counts.get(record.query, 0) + 1
        matched_terms.update(record.matched_terms)
        searchable = " ".join(
            [
                record.query,
                record.title,
                record.abstract,
                " ".join(record.keywords),
                " ".join(record.matched_terms),
            ]
        )
        record_gene_hits = [
            gene_id for gene_id in TARGET_GENES if gene_id in searchable
        ]
        for gene_id in TARGET_GENES:
            if gene_id in record_gene_hits:
                gene_hits[gene_id] += 1
        relevance_level = _relevance_level(record)
        if record.is_real_evidence:
            literature_relevance_counts[relevance_level] += 1
        annotated_record = {
            **record.to_dict(),
            "relevance_level": relevance_level,
            "gene_hit_ids": record_gene_hits,
        }
        if record.is_real_evidence:
            annotated_real_records.append(annotated_record)
        else:
            annotated_demo_records.append(annotated_record)

    return LiteratureAnalysis(
        literature_result_count=len(literature_results),
        literature_query_count=len([query for query in query_counts if query]),
        real_result_count=len(real_records),
        demo_result_count=len(demo_records),
        real_doi_count=len(real_result_dois),
        demo_doi_count=len(demo_dois),
        verified_doi_count=len(verified_dois),
        doi_sources={
            "verified_evidence": verified_dois,
            "literature_results_real": real_result_dois,
            "literature_results_demo": demo_dois,
            "demo_dois": demo_dois,
            "allowed_report_dois": allowed_report_dois,
        },
        query_counts=query_counts,
        matched_terms=sorted(matched_terms),
        gene_hits=gene_hits,
        literature_relevance_counts=literature_relevance_counts,
        real_records=annotated_real_records,
        demo_records=annotated_demo_records,
    )


def _normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    doi = str(value).strip().lower()
    for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
        if doi.startswith(prefix):
            doi = doi[len(prefix):].strip()
    return doi


def _relevance_level(record: LiteratureRecord) -> str:
    # This is a coarse report-only label: it helps readers separate direct
    # Setaria-specific support from broader millet/flavonoid background.
    text = " ".join(
        [
            record.title,
            record.abstract,
            " ".join(record.matched_terms),
        ]
    ).lower()
    has_specific_crop = (
        "setaria italica" in text
        or "foxtail millet" in text
    )
    has_millet = "millet" in text
    has_topic = any(
        term in text
        for term in [
            "flavonoid",
            "metabolomic",
            "candidate gene",
            "marker",
            "breeding",
        ]
    )
    if has_specific_crop and has_topic:
        return "high"
    if has_millet and has_topic:
        return "medium"
    return "background"
