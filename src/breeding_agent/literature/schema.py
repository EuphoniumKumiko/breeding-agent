"""Schema objects for normalized external literature search results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LiteratureRecord:
    """Normalized literature search result consumed by LiteratureAgent v2.

    Demo rows are still serialized so the report can show them explicitly, but
    they never become real DOI evidence.
    """

    query: str
    title: str
    abstract: str
    doi: str
    pmid: str
    source: str
    year: int | None
    keywords: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    is_demo: bool = False

    @property
    def is_real_evidence(self) -> bool:
        """Whether this result may count as real PubMed/literature evidence."""

        return not self.is_demo and self.source != "PubMedFixture"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "query": self.query,
            "title": self.title,
            "abstract": self.abstract,
            "doi": self.doi,
            "pmid": self.pmid,
            "source": self.source,
            "year": self.year,
            "keywords": list(self.keywords),
            "matched_terms": list(self.matched_terms),
            "is_demo": self.is_demo,
            "is_real_evidence": self.is_real_evidence,
        }
