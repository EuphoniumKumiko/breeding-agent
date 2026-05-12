"""External literature result loading, normalization, analysis, and query planning.

This package stays offline by design: it prepares query plans, normalizes
JSONL search results, and separates real evidence from demo fixtures.
"""

from breeding_agent.literature.analyzer import LiteratureAnalysis, analyze_literature
from breeding_agent.literature.loader import load_literature_results
from breeding_agent.literature.query_builder import build_literature_query_plan
from breeding_agent.literature.query_plan import LiteratureQuery, write_literature_query_plan
from breeding_agent.literature.schema import LiteratureRecord

__all__ = [
    "LiteratureAnalysis",
    "LiteratureQuery",
    "LiteratureRecord",
    "analyze_literature",
    "build_literature_query_plan",
    "load_literature_results",
    "write_literature_query_plan",
]
