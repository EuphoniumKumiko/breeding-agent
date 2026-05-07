"""External tool validation."""

from __future__ import annotations

from shutil import which

from breeding_agent.validators.validation_result import ValidationResult


def validate_tools() -> ValidationResult:
    result = ValidationResult()

    for tool in ("featureCounts", "Rscript"):
        if which(tool) is None:
            result.add_error(f"Required tool is not available in PATH: {tool}")

    return result

