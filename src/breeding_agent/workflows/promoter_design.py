"""Workflow scaffold for promoter design tasks."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.modules.promoter.promoter_task_schema import (
    PromoterCandidate,
    PromoterDesignInput,
    PromoterDesignOutput,
)


DEFAULT_OUTDIR = "outputs/promoter_design_demo"
MIN_GENE_SEQUENCE_LENGTH = 20


@dataclass(frozen=True)
class PromoterDesignConfig:
    design_input: PromoterDesignInput
    outdir: Path = Path(DEFAULT_OUTDIR)


def run_promoter_design_task(config: PromoterDesignConfig) -> PromoterDesignOutput:
    """Run the promoter design scaffold without generating synthetic promoters."""

    start_time = _utc_now()
    outdir = config.outdir.expanduser().resolve()
    manifest_file = outdir / "manifest.json"
    manifest: dict[str, object] = {
        "task_name": "promoter_design_scaffold",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "inputs": _input_dict(config.design_input),
        "outputs": {},
        "warnings": [],
        "error_message": None,
        "uses_llm": False,
        "uses_external_api": False,
        "trains_model": False,
        "generates_synthetic_promoter": False,
    }
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        _validate_input(config.design_input)
        scaffold_warning = (
            "Current workflow is a promoter design task scaffold and does not "
            "generate validated or directly usable synthetic promoter sequences."
        )
        candidate = PromoterCandidate(
            candidate_id=f"{config.design_input.gene_id}_promoter_scaffold_001",
            gene_id=config.design_input.gene_id,
            promoter_sequence="NOT_GENERATED",
            design_status="not_generated_scaffold",
            intended_use=(
                "Use this record to define data requirements and validation steps; "
                "do not use it as an experimental promoter sequence."
            ),
            limitations=(
                "No trained promoter generator, no external model call, and no "
                "experimental promoter activity evidence were used."
            ),
        )

        fasta_file = outdir / "promoter_candidates.fasta"
        table_file = outdir / "promoter_candidate_table.tsv"
        report_file = outdir / "promoter_design_report.md"
        validation_plan_file = outdir / "promoter_validation_plan.md"

        _write_placeholder_fasta(fasta_file)
        _write_candidate_table(table_file, [candidate])
        report_file.write_text(
            _render_design_report(
                design_input=config.design_input,
                candidate=candidate,
                warning=scaffold_warning,
            ),
            encoding="utf-8",
        )
        validation_plan_file.write_text(
            _render_validation_plan(config.design_input),
            encoding="utf-8",
        )

        outputs = {
            "promoter_candidates_fasta": str(fasta_file),
            "promoter_candidate_table": str(table_file),
            "promoter_design_report": str(report_file),
            "promoter_validation_plan": str(validation_plan_file),
            "manifest": str(manifest_file),
        }
        manifest["status"] = "success"
        manifest["warnings"] = [scaffold_warning]
        manifest["outputs"] = outputs
        manifest["end_time"] = _utc_now()
        _write_json(manifest_file, manifest)
        return PromoterDesignOutput(
            promoter_candidates_fasta=fasta_file,
            promoter_candidate_table=table_file,
            promoter_design_report=report_file,
            promoter_validation_plan=validation_plan_file,
            manifest=manifest_file,
            candidates=[candidate],
            warnings=[scaffold_warning],
        )
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        manifest["end_time"] = _utc_now()
        _write_json(manifest_file, manifest)
        raise


def _validate_input(design_input: PromoterDesignInput) -> None:
    sequence = _normalize_sequence(design_input.gene_sequence)
    if not sequence:
        raise ValueError("gene_sequence is required for promoter design scaffold.")
    if len(sequence) < MIN_GENE_SEQUENCE_LENGTH:
        raise ValueError(
            "gene_sequence is too short for promoter design scaffold; "
            f"minimum length is {MIN_GENE_SEQUENCE_LENGTH} bp."
        )
    invalid_chars = sorted(set(sequence) - set("ACGTN"))
    if invalid_chars:
        raise ValueError(
            "gene_sequence contains unsupported bases: " + "".join(invalid_chars)
        )
    if not design_input.gene_id.strip():
        raise ValueError("gene_id is required for promoter design scaffold.")
    if not design_input.gene_function.strip():
        raise ValueError("gene_function is required for promoter design scaffold.")
    if not design_input.species.strip():
        raise ValueError("species is required for promoter design scaffold.")
    if not design_input.target_expression_level.strip():
        raise ValueError(
            "target_expression_level is required for promoter design scaffold."
        )


def _write_placeholder_fasta(path: Path) -> None:
    path.write_text(
        (
            "; No promoter sequence generated by promoter_design scaffold.\n"
            "; This file intentionally contains no FASTA records.\n"
        ),
        encoding="utf-8",
    )


def _write_candidate_table(path: Path, candidates: list[PromoterCandidate]) -> None:
    fieldnames = [
        "candidate_id",
        "gene_id",
        "promoter_sequence",
        "design_status",
        "intended_use",
        "limitations",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "candidate_id": candidate.candidate_id,
                    "gene_id": candidate.gene_id,
                    "promoter_sequence": candidate.promoter_sequence,
                    "design_status": candidate.design_status,
                    "intended_use": candidate.intended_use,
                    "limitations": candidate.limitations,
                }
            )


def _render_design_report(
    *,
    design_input: PromoterDesignInput,
    candidate: PromoterCandidate,
    warning: str,
) -> str:
    return "\n".join(
        [
            "# Promoter Design Scaffold Report",
            "",
            "## Task Boundary",
            "Current workflow is a promoter design task scaffold, not a trained promoter generator.",
            "It is not a final promoter generator and cannot provide directly usable synthetic promoter sequences.",
            "It does not train a model, call a real LLM, call external APIs, or implement GAN / diffusion / DNA language model generation.",
            "It does not output any promoter sequence that can be claimed as directly usable in experiments.",
            warning,
            "",
            "## Input Summary",
            f"- gene_id: `{design_input.gene_id}`",
            f"- species: `{design_input.species}`",
            f"- gene_function: {design_input.gene_function}",
            f"- target_expression_level: `{design_input.target_expression_level}`",
            f"- target_tissue_or_condition: `{design_input.target_tissue_or_condition or 'not_provided'}`",
            f"- gene_sequence_length: {len(_normalize_sequence(design_input.gene_sequence))} bp",
            "",
            "## Placeholder Candidate",
            "| candidate_id | design_status | promoter_sequence | intended_use |",
            "| --- | --- | --- | --- |",
            (
                f"| {candidate.candidate_id} | {candidate.design_status} | "
                f"{candidate.promoter_sequence} | {candidate.intended_use} |"
            ),
            "",
            "## Required Data Before Real Design",
            "- High-confidence promoter activity labels from stable transgenic validation, LUC reporter assay, STARR-seq, or MPRA.",
            "- Genome and annotation resources for species-specific promoter region definition.",
            "- TSS annotation and motif annotation for core promoter boundary and regulatory interpretation.",
            "- Independent experimental validation before any sequence is described as usable.",
            "",
            "## Relationship To Breeding-Agent",
            "This scaffold prepares a future design module that can be connected to LangGraph or Deep Agents orchestration later, while keeping the current flavonoid marker recommendation workflow as the main validated line.",
            "",
        ]
    )


def _render_validation_plan(design_input: PromoterDesignInput) -> str:
    return "\n".join(
        [
            "# Promoter Validation Plan",
            "",
            f"Target gene: `{design_input.gene_id}`",
            f"Target expression: `{design_input.target_expression_level}`",
            f"Target tissue or condition: `{design_input.target_tissue_or_condition or 'not_provided'}`",
            "",
            "## Before Sequence Generation",
            "1. Build a promoter dataset inventory with Tier 1 / Tier 2 experimental activity labels.",
            "2. Define species-specific promoter windows using genome, GFF, and TSS annotation.",
            "3. Separate strong experimental labels from weak expression or motif-derived labels.",
            "",
            "## After Future Candidate Generation",
            "1. Screen motifs, GC content, repeats, synthesis constraints, and cloning constraints.",
            "2. Test candidates with LUC reporter assay or MPRA/STARR-seq in the relevant system.",
            "3. Validate prioritized candidates in stable transgenic material when feasible.",
            "4. Measure target gene expression and downstream phenotype under the target condition.",
            "",
            "Current scaffold produces no validated promoter sequence.",
            "",
        ]
    )


def _input_dict(design_input: PromoterDesignInput) -> dict[str, object]:
    return {
        "gene_id": design_input.gene_id,
        "gene_sequence_length": len(_normalize_sequence(design_input.gene_sequence)),
        "gene_function": design_input.gene_function,
        "species": design_input.species,
        "target_expression_level": design_input.target_expression_level,
        "target_tissue_or_condition": design_input.target_tissue_or_condition,
    }


def _normalize_sequence(sequence: str) -> str:
    return "".join(sequence.split()).upper()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
