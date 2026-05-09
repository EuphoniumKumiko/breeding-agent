"""Rule-based QA checks for flavonoid marker recommendation reports."""

from __future__ import annotations

import re


REQUIRED_GENE_IDS = ["Si9g04210.1", "Si5g31340.1", "Si9g34380.1"]
REQUIRED_TERMS = ["群体", "文献查阅", "DOI", "SNP", "InDel", "KASP", "CAPS"]

STATISTIC_LABELS = ["baseMean", "log2FC", "pvalue", "padj"]
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s|)]+", re.IGNORECASE)


def check_flavonoid_marker_report(report_text: str) -> dict[str, object]:
    """Check required report content without calling an LLM."""

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
    has_doi = DOI_RE.search(report_text) is not None
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
        and has_marker_types
        and not optional_variant_checks
    )

    return {
        "gene_check": gene_check,
        "term_check": term_check,
        "has_statistics": has_statistics,
        "statistics_check": statistics_check,
        "has_literature_review": has_literature_review,
        "has_doi": has_doi,
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
