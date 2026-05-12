"""Rule-based QA checks for flavonoid marker recommendation reports."""

from __future__ import annotations

import re


REQUIRED_GENE_IDS = ["Si9g04210.1", "Si5g31340.1", "Si9g34380.1"]
REQUIRED_TERMS = ["群体", "文献查阅", "DOI", "SNP", "InDel", "KASP", "CAPS"]

STATISTIC_LABELS = ["baseMean", "log2FC", "pvalue", "padj"]
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s|)]+", re.IGNORECASE)


def check_flavonoid_marker_report(
    report_text: str,
    *,
    allowed_dois: list[str] | set[str] | None = None,
    literature_analysis: dict[str, object] | None = None,
) -> dict[str, object]:
    """Check required report content without calling an LLM.

    This is the report-side guardrail for DOI provenance, gene coverage, and
    the expected flavonoid marker boundary statements.
    """

    gene_check = {
        gene_id: gene_id in report_text
        for gene_id in REQUIRED_GENE_IDS
    }
    term_check = {
        term: _contains_term(report_text, term)
        for term in REQUIRED_TERMS
    }
    statistics_check = {
        gene_id: _gene_has_statistics(report_text, gene_id)
        for gene_id in REQUIRED_GENE_IDS
    }
    has_statistics = all(statistics_check.values())
    has_literature_review = "文献查阅" in report_text
    report_doi_set = {_normalize_doi(doi) for doi in DOI_RE.findall(report_text)}
    demo_dois = _demo_dois(literature_analysis)
    # Demo DOIs are tracked for visibility but excluded from real evidence.
    report_demo_dois = sorted(report_doi_set & demo_dois)
    report_dois = sorted(report_doi_set - demo_dois)
    normalized_allowed_dois = (
        {_normalize_doi(doi) for doi in allowed_dois if _normalize_doi(doi)}
        if allowed_dois is not None
        else set()
    ) - demo_dois
    evidence_dois = normalized_allowed_dois or _real_evidence_dois(literature_analysis)
    has_doi = (
        bool(set(report_dois) & evidence_dois)
        if evidence_dois
        else bool(report_dois)
    )
    no_llm_generated_doi = True
    unexpected_dois: list[str] = []
    if allowed_dois is not None:
        unexpected_dois = [
            doi for doi in report_dois if doi not in normalized_allowed_dois
        ]
        no_llm_generated_doi = not unexpected_dois
    has_marker_types = all(
        marker_type in report_text
        for marker_type in ["SNP", "InDel", "KASP", "CAPS"]
    )

    missing_items: list[str] = []
    missing_items.extend(
        f"missing gene: {gene_id}"
        for gene_id, present in gene_check.items()
        if not present
    )
    missing_items.extend(
        f"missing term: {term}"
        for term, present in term_check.items()
        if not present
    )
    missing_items.extend(
        f"missing statistics for gene: {gene_id}"
        for gene_id, present in statistics_check.items()
        if not present
    )
    if not has_literature_review:
        missing_items.append("missing literature review section")
    if not has_doi:
        missing_items.append("missing DOI value")
    if not no_llm_generated_doi:
        missing_items.append("report DOI not present in allowed evidence: " + ", ".join(unexpected_dois))
    if report_demo_dois:
        missing_items.append(
            "demo DOI displayed in report and excluded from real evidence: "
            + ", ".join(report_demo_dois)
        )
    if not has_marker_types:
        missing_items.append("missing marker type recommendation")
    optional_variant_checks = _optional_variant_evidence_checks(report_text)
    missing_items.extend(optional_variant_checks)

    passed = (
        all(gene_check.values())
        and all(term_check.values())
        and has_statistics
        and has_literature_review
        and has_doi
        and no_llm_generated_doi
        and not report_demo_dois
        and has_marker_types
        and not optional_variant_checks
    )
    literature_metrics = _literature_metrics(literature_analysis)

    return {
        "gene_check": gene_check,
        "term_check": term_check,
        "has_statistics": has_statistics,
        "statistics_check": statistics_check,
        "has_literature_review": has_literature_review,
        "has_doi": has_doi,
        "report_dois": report_dois,
        "report_demo_dois": report_demo_dois,
        "allowed_report_dois": sorted(normalized_allowed_dois),
        "unexpected_dois": unexpected_dois,
        "no_llm_generated_doi": no_llm_generated_doi,
        **literature_metrics,
        "has_marker_types": has_marker_types,
        "optional_variant_checks": optional_variant_checks,
        "passed": passed,
        "missing_items": missing_items,
    }


def _contains_term(report_text: str, term: str) -> bool:
    if term == "DOI":
        return "doi" in report_text.lower()
    return term in report_text


def _gene_has_statistics(report_text: str, gene_id: str) -> bool:
    if not all(label in report_text for label in STATISTIC_LABELS):
        return False

    for line in report_text.splitlines():
        if gene_id not in line:
            continue
        if all(label in line for label in STATISTIC_LABELS):
            return True
        if len(NUMBER_RE.findall(line)) >= 4:
            return True
    return False


def _optional_variant_evidence_checks(report_text: str) -> list[str]:
    missing = []
    if "LowQual" in report_text and not (
        "不应直接优先" in report_text or "不应优先" in report_text
    ):
        missing.append("missing LowQual non-prioritization statement")
    if "preliminary" in report_text and ("KASP" in report_text or "CAPS" in report_text):
        if not ("不是最终标记" in report_text or "不是最终引物" in report_text):
            missing.append("missing preliminary KASP/CAPS limitation statement")
    if "variant calling" in report_text or "候选区域变异 calling" in report_text:
        if not ("不能替代 WGS/GBS" in report_text or "不能替代 WGS" in report_text):
            missing.append("missing WGS/GBS limitation statement")
    return missing


def _normalize_doi(doi: str) -> str:
    normalized = doi.strip().lower()
    normalized = normalized.rstrip(".,;，。；\"'`")
    return normalized


def _literature_metrics(
    literature_analysis: dict[str, object] | None,
) -> dict[str, object]:
    if not literature_analysis:
        return {
            "literature_result_count": 0,
            "literature_query_count": 0,
            "literature_relevance_counts": {
                "high": 0,
                "medium": 0,
                "background": 0,
            },
            "doi_sources": {},
        }
    doi_sources = literature_analysis.get("doi_sources", {})
    relevance_counts = literature_analysis.get("literature_relevance_counts", {})
    return {
        "literature_result_count": literature_analysis.get("literature_result_count", 0),
        "literature_query_count": literature_analysis.get("literature_query_count", 0),
        "literature_relevance_counts": (
            relevance_counts
            if isinstance(relevance_counts, dict)
            else {"high": 0, "medium": 0, "background": 0}
        ),
        "doi_sources": doi_sources if isinstance(doi_sources, dict) else {},
    }


def _demo_dois(literature_analysis: dict[str, object] | None) -> set[str]:
    doi_sources = _doi_sources(literature_analysis)
    demo_values = [
        *doi_sources.get("literature_results_demo", []),
        *doi_sources.get("demo_dois", []),
    ]
    return {_normalize_doi(str(doi)) for doi in demo_values if _normalize_doi(str(doi))}


def _real_evidence_dois(literature_analysis: dict[str, object] | None) -> set[str]:
    doi_sources = _doi_sources(literature_analysis)
    evidence_values = [
        *doi_sources.get("verified_evidence", []),
        *doi_sources.get("literature_results_real", []),
    ]
    return {_normalize_doi(str(doi)) for doi in evidence_values if _normalize_doi(str(doi))}


def _doi_sources(literature_analysis: dict[str, object] | None) -> dict[str, list[object]]:
    if not literature_analysis:
        return {}
    doi_sources = literature_analysis.get("doi_sources", {})
    if not isinstance(doi_sources, dict):
        return {}
    normalized: dict[str, list[object]] = {}
    for key, value in doi_sources.items():
        normalized[str(key)] = value if isinstance(value, list) else []
    return normalized
