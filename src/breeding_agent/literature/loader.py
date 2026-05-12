"""Load external literature search result JSONL files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from breeding_agent.literature.normalizer import (
    dedupe_literature_records,
    normalize_literature_row,
)
from breeding_agent.literature.schema import LiteratureRecord


def load_literature_results(path: Path | None) -> list[LiteratureRecord]:
    """Load normalized records from a local JSONL file.

    No network access is performed. Missing or empty paths return an empty list
    so the main workflow can still run with only verified seed DOI evidence.
    """

    if path is None:
        return []
    expanded = path.expanduser()
    if not expanded.exists() or not expanded.is_file():
        return []

    records: list[LiteratureRecord] = []
    with expanded.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(
                    f"Literature JSONL line {line_number} is not an object: {expanded}"
                )
            records.append(normalize_literature_row(payload))
    return dedupe_literature_records(records)


def records_to_dicts(records: list[LiteratureRecord]) -> list[dict[str, Any]]:
    """Convert records to dictionaries for graph state serialization.

    The graph stores plain dictionaries so trace/state JSON stays easy to read
    in reports and Gradio.
    """

    return [record.to_dict() for record in records]
