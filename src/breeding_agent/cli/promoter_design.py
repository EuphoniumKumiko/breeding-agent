"""CLI for the promoter design scaffold workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from breeding_agent.modules.promoter.promoter_task_schema import PromoterDesignInput
from breeding_agent.workflows.promoter_design import (
    DEFAULT_OUTDIR,
    PromoterDesignConfig,
    run_promoter_design_task,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m breeding_agent.cli.promoter_design",
        description="Run promoter design task scaffold without generating synthetic promoters.",
    )
    parser.add_argument("--gene-id", required=True, help="Target gene ID.")
    parser.add_argument(
        "--gene-sequence",
        required=True,
        help="Target gene sequence. Required; scaffold validates but does not generate promoter sequence.",
    )
    parser.add_argument(
        "--gene-function",
        required=True,
        help="Functional description of the target gene.",
    )
    parser.add_argument("--species", required=True, help="Species name.")
    parser.add_argument(
        "--target-expression-level",
        required=True,
        help="Target expression level, such as high, medium, or low.",
    )
    parser.add_argument(
        "--target-tissue-or-condition",
        default="",
        help="Optional target tissue, developmental stage, or treatment condition.",
    )
    parser.add_argument(
        "--outdir",
        default=Path(DEFAULT_OUTDIR),
        type=Path,
        help=f"Output directory. Default: {DEFAULT_OUTDIR}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    design_input = PromoterDesignInput(
        gene_id=args.gene_id,
        gene_sequence=args.gene_sequence,
        gene_function=args.gene_function,
        species=args.species,
        target_expression_level=args.target_expression_level,
        target_tissue_or_condition=args.target_tissue_or_condition,
    )
    config = PromoterDesignConfig(
        design_input=design_input,
        outdir=args.outdir.expanduser(),
    )

    try:
        result = run_promoter_design_task(config)
    except Exception as exc:
        print(f"[promoter-design:error] {exc}", file=sys.stderr, flush=True)
        return 1

    print("[promoter-design] scaffold workflow finished", flush=True)
    print(
        f"[promoter-design] candidate_table: {result.promoter_candidate_table}",
        flush=True,
    )
    print(f"[promoter-design] report: {result.promoter_design_report}", flush=True)
    print(
        f"[promoter-design] validation_plan: {result.promoter_validation_plan}",
        flush=True,
    )
    print(f"[promoter-design] manifest: {result.manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
