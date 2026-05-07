"""Standardize transcriptomics DEG outputs into evidence tables."""

from __future__ import annotations

import csv
from pathlib import Path

from breeding_agent.integration.evidence_schema import (
    STANDARD_EVIDENCE_COLUMNS,
    StandardEvidenceRecord,
)


SOURCE_MODULE = "Transcriptomics DEG Module"
ENTITY_TYPE = "gene_or_transcript"
OMICS_TYPE = "transcriptomics"


def standardize_transcriptomics_deg(
    *,
    outdir: Path,
    prefix: str,
    contrast: str,
    trait: str = "unknown",
) -> Path:
    """Convert transcriptomics significant DEG results to standardized evidence."""

    source_file = outdir / "mini_de" / f"{prefix}.significant_genes.tsv"
    if not source_file.exists():
        raise FileNotFoundError(f"Significant genes file does not exist: {source_file}")

    integration_dir = outdir / "integration"
    integration_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = integration_dir / "standardized_evidence.tsv"

    with source_file.open("r", encoding="utf-8", newline="") as input_handle:
        reader = csv.DictReader(input_handle, delimiter="\t")
        _ensure_required_columns(reader.fieldnames, source_file)

        records = [
            _row_to_record(
                row=row,
                trait=trait or "unknown",
                contrast=contrast,
                source_file=source_file,
            )
            for row in reader
        ]

    with evidence_file.open("w", encoding="utf-8", newline="") as output_handle:
        writer = csv.DictWriter(
            output_handle,
            fieldnames=STANDARD_EVIDENCE_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(record.as_dict() for record in records)

    return evidence_file


def _row_to_record(
    *,
    row: dict[str, str],
    trait: str,
    contrast: str,
    source_file: Path,
) -> StandardEvidenceRecord:
    logfc = _parse_float(row.get("logFC"))
    adj_p_val = _parse_float(row.get("adj.P.Val"))
    mean_count_jm = _parse_float(row.get("mean_count_JM"))
    mean_count_lm = _parse_float(row.get("mean_count_LM"))
    direction = _direction(contrast, logfc)

    return StandardEvidenceRecord(
        entity_id=row.get("Geneid", ""),
        entity_type=ENTITY_TYPE,
        omics_type=OMICS_TYPE,
        trait=trait,
        comparison=contrast,
        direction=direction,
        effect_size=row.get("logFC", ""),
        p_value=row.get("P.Value", ""),
        adj_p_value=row.get("adj.P.Val", ""),
        evidence_score=f"{_evidence_score(row, contrast):.3f}",
        source_module=SOURCE_MODULE,
        source_file=str(source_file),
        evidence_note=_evidence_note(
            logfc_text=row.get("logFC", ""),
            adj_p_val_text=row.get("adj.P.Val", ""),
            mean_count_jm_text=row.get("mean_count_JM", ""),
            mean_count_lm_text=row.get("mean_count_LM", ""),
            direction=direction,
            contrast=contrast,
        ),
    )


def _ensure_required_columns(fieldnames: list[str] | None, source_file: Path) -> None:
    required_columns = {
        "Geneid",
        "logFC",
        "P.Value",
        "adj.P.Val",
        "mean_count_JM",
        "mean_count_LM",
        "significant",
    }
    available = set(fieldnames or [])
    missing = sorted(required_columns - available)
    if missing:
        raise ValueError(
            f"Missing required DEG column(s) in {source_file}: {', '.join(missing)}"
        )


def _direction(contrast: str, logfc: float | None) -> str:
    if contrast != "JM-LM" or logfc is None:
        return "unknown"
    if logfc < 0:
        return "LM_higher"
    if logfc > 0:
        return "JM_higher"
    return "unknown"


def _evidence_score(row: dict[str, str], contrast: str) -> float:
    logfc = _parse_float(row.get("logFC"))
    adj_p_val = _parse_float(row.get("adj.P.Val"))
    mean_count_jm = _parse_float(row.get("mean_count_JM"))
    mean_count_lm = _parse_float(row.get("mean_count_LM"))

    score = 0.0
    if _parse_bool(row.get("significant")):
        score += 0.4
    if adj_p_val is not None and adj_p_val < 0.001:
        score += 0.3
    if logfc is not None and abs(logfc) > 2:
        score += 0.2
    if _mean_count_matches_logfc(
        contrast=contrast,
        logfc=logfc,
        mean_count_jm=mean_count_jm,
        mean_count_lm=mean_count_lm,
    ):
        score += 0.1
    return min(score, 1.0)


def _mean_count_matches_logfc(
    *,
    contrast: str,
    logfc: float | None,
    mean_count_jm: float | None,
    mean_count_lm: float | None,
) -> bool:
    if contrast != "JM-LM":
        return False
    if logfc is None or mean_count_jm is None or mean_count_lm is None:
        return False
    if logfc > 0:
        return mean_count_jm > mean_count_lm
    if logfc < 0:
        return mean_count_lm > mean_count_jm
    return False


def _evidence_note(
    *,
    logfc_text: str,
    adj_p_val_text: str,
    mean_count_jm_text: str,
    mean_count_lm_text: str,
    direction: str,
    contrast: str,
) -> str:
    return (
        f"logFC={logfc_text}; adj.P.Val={adj_p_val_text}; "
        f"mean_count_JM={mean_count_jm_text}; mean_count_LM={mean_count_lm_text}; "
        f"{_direction_explanation(direction, contrast)}"
    )


def _direction_explanation(direction: str, contrast: str) -> str:
    if contrast == "JM-LM":
        if direction == "LM_higher":
            return "For contrast=JM-LM, logFC < 0 means LM higher expression."
        if direction == "JM_higher":
            return "For contrast=JM-LM, logFC > 0 means JM higher expression."
        return "For contrast=JM-LM, logFC direction is unknown or zero."
    return f"Expression direction is not defined for contrast={contrast}."


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "t", "1", "yes", "y"}

