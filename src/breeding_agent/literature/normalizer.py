"""Normalize and validate external literature result rows."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from breeding_agent.literature.schema import LiteratureRecord


DOI_PREFIX_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)


def normalize_literature_row(row: dict[str, Any]) -> LiteratureRecord:
    """Normalize one JSON/JSONL row without inventing identifiers.

    Demo rows are marked from their source metadata and kept separate from real
    external evidence.
    """

    doi = normalize_doi(row.get("doi", ""))
    source = _text(row.get("source", "PubMed"))
    is_demo = _bool(row.get("is_demo", False)) or source == "PubMedFixture"
    return LiteratureRecord(
        query=_text(row.get("query", "")),
        title=_text(row.get("title", "")),
        abstract=_text(row.get("abstract", "")),
        doi=doi,
        pmid=_text(row.get("pmid", row.get("PMID", row.get("pubmed_id", "")))),
        source=source or "PubMed",
        year=_year(row.get("year", "")),
        keywords=_string_list(row.get("keywords", [])),
        matched_terms=_string_list(row.get("matched_terms", [])),
        is_demo=is_demo,
    )


def normalize_doi(value: Any) -> str:
    """Normalize an existing DOI; return empty when absent."""

    doi = _text(value)
    if not doi:
        return ""
    doi = DOI_PREFIX_RE.sub("", doi)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return doi.strip().lower()


def dedupe_literature_records(
    records: Iterable[LiteratureRecord],
) -> list[LiteratureRecord]:
    """Deduplicate by DOI, then PMID, then title.

    This preserves the strongest identifier available without synthesizing any
    new bibliographic keys.
    """

    seen: set[tuple[str, str]] = set()
    deduped: list[LiteratureRecord] = []
    for record in records:
        if record.doi:
            key = ("doi", record.doi.lower())
        elif record.pmid:
            key = ("pmid", record.pmid)
        else:
            key = ("title", _title_key(record.title))
        if not key[1]:
            key = ("row", f"{len(deduped)}:{record.title}")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return _text(str(value))


def _string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
    if isinstance(value, dict):
        return [_text(item) for item in value.values() if _text(item)]
    if isinstance(value, Iterable):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _year(value: Any) -> int | None:
    match = re.search(r"\d{4}", _text(value))
    return int(match.group(0)) if match else None


def _title_key(title: str) -> str:
    normalized = title.lower()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
