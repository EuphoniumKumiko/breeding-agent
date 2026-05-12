"""Offline literature query plan builder from flavonoid evidence context."""

from __future__ import annotations

import re
from typing import Any

from breeding_agent.literature.query_plan import LiteratureQuery


DEFAULT_CROPS = ["Setaria italica", "foxtail millet", "millet"]
DEFAULT_TRAITS = ["flavonoid", "flavonoid biosynthesis", "flavonoid accumulation"]
DEFAULT_MARKER_TERMS = ["SNP", "InDel", "KASP", "CAPS", "marker", "breeding"]
DEFAULT_GENES = ["Si9g04210.1", "Si5g31340.1", "Si9g34380.1"]
MAX_QUERY_COUNT = 20


def build_literature_query_plan(
    context: dict[str, Any],
    *,
    max_queries: int = MAX_QUERY_COUNT,
) -> list[LiteratureQuery]:
    """Generate deduplicated offline literature search queries from evidence context.

    The builder only reads local evidence context and turns it into query
    intent; the actual PubMed search happens in the separate literature export
    pipeline.
    """

    # Seed the query families with the fixed crop/trait vocabulary and then
    # extend them with whatever terms are already present in the evidence.
    crop_terms = _ordered_unique([*DEFAULT_CROPS, *_terms(context.get("crop_terms", []))])
    trait_terms = _ordered_unique([*DEFAULT_TRAITS, *_terms(context.get("trait_terms", []))])
    gene_ids = _ordered_unique([*_gene_ids(context), *DEFAULT_GENES])
    annotation_terms = _annotation_terms(context)
    metabolite_terms = _metabolite_terms(context)

    candidates: list[dict[str, object]] = []
    primary_crop = crop_terms[0]
    primary_trait = trait_terms[0]
    biosynthesis_trait = _first_matching(trait_terms, "biosynthesis", "flavonoid biosynthesis")
    accumulation_trait = _first_matching(trait_terms, "accumulation", "flavonoid accumulation")

    for crop in crop_terms[:3]:
        candidates.append(
            _candidate(
                query=f"{crop} {primary_trait} biosynthesis",
                crop=crop,
                trait=primary_trait,
                query_type="trait_biosynthesis",
                keywords=[crop, primary_trait, "biosynthesis"],
                source_terms=["crop", "trait"],
            )
        )

    candidates.extend(
        [
            _candidate(
                query=f"{primary_crop} {primary_trait} candidate gene",
                crop=primary_crop,
                trait=primary_trait,
                query_type="candidate_gene",
                keywords=[primary_crop, primary_trait, "candidate gene"],
                source_terms=["crop", "trait"],
            ),
            _candidate(
                query=f"{primary_crop} {accumulation_trait} candidate gene",
                crop=primary_crop,
                trait=accumulation_trait,
                query_type="candidate_gene",
                keywords=[primary_crop, accumulation_trait, "candidate gene"],
                source_terms=["crop", "trait"],
            ),
        ]
    )

    for gene_id in gene_ids[:3]:
        candidates.append(
            _candidate(
                query=f"{primary_crop} {gene_id} {primary_trait}",
                crop=primary_crop,
                trait=primary_trait,
                gene_id=gene_id,
                query_type="gene_trait",
                keywords=[primary_crop, gene_id, primary_trait],
                source_terms=["crop", "gene_id", "trait"],
            )
        )

    for term in annotation_terms[:4]:
        candidates.append(
            _candidate(
                query=f"{primary_crop} {term} {primary_trait}",
                crop=primary_crop,
                trait=primary_trait,
                query_type="annotation_trait",
                keywords=[primary_crop, term, primary_trait],
                source_terms=["crop", "annotation_term", "trait"],
            )
        )

    for term in metabolite_terms[:3]:
        candidates.append(
            _candidate(
                query=f"{primary_crop} {term} {accumulation_trait}",
                crop=primary_crop,
                trait=accumulation_trait,
                query_type="metabolite_trait",
                keywords=[primary_crop, term, accumulation_trait],
                source_terms=["crop", "metabolite_term", "trait"],
            )
        )

    candidates.extend(
        [
            _candidate(
                query=f"{primary_crop} SNP marker",
                crop=primary_crop,
                trait=primary_trait,
                query_type="marker",
                keywords=[primary_crop, "SNP", "marker"],
                source_terms=["crop", "marker_terms"],
            ),
            _candidate(
                query=f"{primary_crop} KASP marker",
                crop=primary_crop,
                trait=primary_trait,
                query_type="marker",
                keywords=[primary_crop, "KASP", "marker"],
                source_terms=["crop", "marker_terms"],
            ),
            _candidate(
                query=f"{primary_crop} InDel CAPS marker breeding",
                crop=primary_crop,
                trait=primary_trait,
                query_type="marker",
                keywords=[primary_crop, "InDel", "CAPS", "marker", "breeding"],
                source_terms=["crop", "marker_terms"],
            ),
            _candidate(
                query=f"{crop_terms[1]} marker assisted selection",
                crop=crop_terms[1],
                trait=primary_trait,
                query_type="marker_assisted_selection",
                keywords=[crop_terms[1], "marker", "assisted selection", "breeding"],
                source_terms=["crop", "marker_terms"],
            ),
            _candidate(
                query=f"{crop_terms[2]} marker assisted selection",
                crop=crop_terms[2],
                trait=primary_trait,
                query_type="marker_assisted_selection",
                keywords=[crop_terms[2], "marker", "assisted selection", "breeding"],
                source_terms=["crop", "marker_terms"],
            ),
            _candidate(
                query=f"{primary_crop} {biosynthesis_trait} marker breeding",
                crop=primary_crop,
                trait=biosynthesis_trait,
                query_type="trait_marker",
                keywords=[primary_crop, biosynthesis_trait, "marker", "breeding"],
                source_terms=["crop", "trait", "marker_terms"],
            ),
        ]
    )

    # The final pass deduplicates by literal query string and enforces the
    # conservative max-query cap required by downstream export tooling.
    return _finalize(candidates, max_queries=max_queries)


def _candidate(
    *,
    query: str,
    crop: str,
    trait: str,
    query_type: str,
    keywords: list[str],
    source_terms: list[str],
    gene_id: str = "",
) -> dict[str, object]:
    keyword_values = list(keywords)
    if query_type.startswith("marker"):
        keyword_values.extend(DEFAULT_MARKER_TERMS)
    return {
        "query": _clean_text(query),
        "crop": crop,
        "trait": trait,
        "gene_id": gene_id,
        "query_type": query_type,
        "keywords": _ordered_unique(keyword_values),
        "source_terms": _ordered_unique(source_terms),
    }


def _finalize(
    candidates: list[dict[str, object]],
    *,
    max_queries: int,
) -> list[LiteratureQuery]:
    seen: set[str] = set()
    rows: list[LiteratureQuery] = []
    for candidate in candidates:
        query = str(candidate["query"])
        key = query.lower()
        if not query or key in seen:
            continue
        seen.add(key)
        rows.append(
            LiteratureQuery(
                query_id=f"Q{len(rows) + 1:03d}",
                query=query,
                crop=str(candidate["crop"]),
                trait=str(candidate["trait"]),
                gene_id=str(candidate["gene_id"]),
                query_type=str(candidate["query_type"]),
                keywords=_ordered_unique(_terms(candidate["keywords"])),
                source_terms=_ordered_unique(_terms(candidate["source_terms"])),
            )
        )
        if len(rows) >= max_queries:
            break
    return rows


def _gene_ids(context: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ["candidate_rows", "transcriptomics_evidence", "annotation_evidence"]:
        for row in _rows(context.get(key, [])):
            gene_id = _clean_text(row.get("gene_id", ""))
            if gene_id:
                values.append(gene_id)
    return values


def _annotation_terms(context: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    rows = [*_rows(context.get("candidate_rows", [])), *_rows(context.get("annotation_evidence", []))]
    for row in rows:
        for key in ["function_annotation", "Description", "Preferred_name", "PFAMs", "KEGG_Pathway"]:
            terms.extend(_extract_biological_terms(str(row.get(key, ""))))
    return _ordered_unique(terms)


def _metabolite_terms(context: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    rows = [*_rows(context.get("candidate_rows", [])), *_rows(context.get("metabolomics_evidence", []))]
    for row in rows:
        for key in ["top_correlated_metabolite", "top_spls_metabolite"]:
            text = _clean_metabolite(str(row.get(key, "")))
            if text:
                terms.append(text)
    terms.extend(["flavonoid pathway", "flavonoid biosynthesis pathway"])
    return _ordered_unique(terms)


def _extract_biological_terms(text: str) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned or cleaned == "NA":
        return []
    terms: list[str] = []
    lower = cleaned.lower()
    family_match = re.search(r"belongs to the (.+?) family", lower)
    if family_match:
        terms.append(family_match.group(1))
    for part in re.split(r"[,;/]", cleaned):
        token = _clean_text(part)
        if not token or token.lower().startswith(("ko", "map")):
            continue
        if token.lower().startswith("belongs to "):
            continue
        if len(token) <= 2:
            continue
        terms.append(token)
    return terms


def _clean_metabolite(text: str) -> str:
    text = _clean_text(text.replace("*", ""))
    return "" if text in {"", "NA"} else text


def _first_matching(values: list[str], needle: str, default: str) -> str:
    for value in values:
        if needle in value.lower():
            return value
    return default


def _terms(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if value in (None, ""):
        return []
    return [_clean_text(value)]


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())
