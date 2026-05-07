"""GFF input validation."""

from __future__ import annotations

from pathlib import Path

from breeding_agent.validators.validation_result import ValidationResult


def validate_gff(gff: Path, *, max_lines: int = 1000) -> ValidationResult:
    result = ValidationResult()

    if not gff.exists():
        result.add_error(f"GFF file does not exist: {gff}")
        return result
    if not gff.is_file():
        result.add_error(f"GFF path is not a file: {gff}")
        return result
    if gff.suffix.lower() not in {".gff", ".gff3"}:
        result.add_error(f"GFF file must end with .gff or .gff3: {gff}")

    saw_exon = False
    saw_parent = False
    try:
        with gff.open("r", encoding="utf-8", errors="replace") as handle:
            for index, line in enumerate(handle):
                if index >= max_lines:
                    break
                if "\texon\t" in line or " exon " in line:
                    saw_exon = True
                if "Parent=" in line:
                    saw_parent = True
                if saw_exon and saw_parent:
                    break
    except OSError as exc:
        result.add_error(f"Could not read GFF file {gff}: {exc}")
        return result

    if not saw_exon:
        result.add_warning(f"No exon feature found in first {max_lines} GFF lines: {gff}")
    if not saw_parent:
        result.add_warning(f"No Parent= attribute found in first {max_lines} GFF lines: {gff}")

    return result

