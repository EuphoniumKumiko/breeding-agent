"""BAM input validation."""

from __future__ import annotations

from pathlib import Path

from breeding_agent.validators.validation_result import ValidationResult


def validate_bam_dir(bam_dir: Path) -> ValidationResult:
    result = ValidationResult()

    if not bam_dir.exists():
        result.add_error(f"bam-dir does not exist: {bam_dir}")
        return result
    if not bam_dir.is_dir():
        result.add_error(f"bam-dir is not a directory: {bam_dir}")
        return result

    mini_bams = sorted(bam_dir.glob("*.mini.sorted.bam"))
    bams = sorted(bam_dir.glob("*.bam"))
    if not mini_bams and not bams:
        result.add_error(
            f"No BAM files found in {bam_dir} (*.mini.sorted.bam first, then *.bam)."
        )

    return result

