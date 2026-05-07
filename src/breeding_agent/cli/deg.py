"""Command line entry point for the mini RNA-seq DEG workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from breeding_agent.workflows.rnaseq_deg import (
    DEFAULT_CONTRAST,
    DEFAULT_GFF,
    DEFAULT_OUTDIR,
    DEFAULT_PREFIX,
    DEFAULT_THREADS,
    RnaSeqDegConfig,
    run_rnaseq_deg_task,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m breeding_agent.cli.deg",
        description="Run the mini RNA-seq DEG reproduction workflow.",
    )
    parser.add_argument("--bam-dir", required=True, type=Path, help="Directory with BAM files.")
    parser.add_argument(
        "--gff",
        default=Path(DEFAULT_GFF),
        type=Path,
        help=f"GFF annotation file. Default: {DEFAULT_GFF}",
    )
    parser.add_argument(
        "--contrast",
        default=DEFAULT_CONTRAST,
        help=f"DE contrast. Default: {DEFAULT_CONTRAST}",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Output prefix. Default: {DEFAULT_PREFIX}",
    )
    parser.add_argument(
        "--trait",
        default="unknown",
        help="Trait name written to standardized evidence. Default: unknown",
    )
    parser.add_argument(
        "--threads",
        default=DEFAULT_THREADS,
        type=int,
        help=f"featureCounts threads. Default: {DEFAULT_THREADS}",
    )
    parser.add_argument(
        "--outdir",
        default=Path(DEFAULT_OUTDIR),
        type=Path,
        help=f"Output directory. Default: {DEFAULT_OUTDIR}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.threads < 1:
        parser.error("--threads must be >= 1")

    config = RnaSeqDegConfig(
        bam_dir=args.bam_dir,
        gff=args.gff,
        contrast=args.contrast,
        prefix=args.prefix,
        trait=args.trait,
        threads=args.threads,
        outdir=args.outdir,
    )

    try:
        significant_genes = run_rnaseq_deg_task(config)
    except Exception as exc:
        print(f"[deg:error] {exc}", file=sys.stderr, flush=True)
        return 1

    print(f"[deg] significant genes: {significant_genes}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
