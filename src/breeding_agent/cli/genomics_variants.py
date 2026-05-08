"""Command line entry point for candidate-region genomics variant calling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from breeding_agent.workflows.genomics_variant_calling import (
    DEFAULT_DATASET_DIR,
    DEFAULT_OUTDIR,
    GenomicsVariantCallingConfig,
    run_genomics_variant_calling_task,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m breeding_agent.cli.genomics_variants",
        description="Run candidate-region SNP/InDel calling with samtools/bcftools.",
    )
    parser.add_argument(
        "--dataset-dir",
        default=Path(DEFAULT_DATASET_DIR),
        type=Path,
        help=f"Mini flavonoid marker data package. Default: {DEFAULT_DATASET_DIR}",
    )
    parser.add_argument(
        "--bam-dir",
        type=Path,
        default=None,
        help="BAM directory. Default: <dataset-dir>/bam",
    )
    parser.add_argument(
        "--reference-fasta",
        type=Path,
        default=None,
        help=(
            "Reference FASTA. Default: <dataset-dir>/genome.bam_compatible.fa.gz "
            "if present, otherwise <dataset-dir>/genome.fa"
        ),
    )
    parser.add_argument(
        "--regions-bed",
        type=Path,
        default=None,
        help="Candidate regions BED. Default: <dataset-dir>/regions/regions.bed",
    )
    parser.add_argument(
        "--gff",
        type=Path,
        default=None,
        help=(
            "GFF annotation. Default: <dataset-dir>/genome.original_coords.gff "
            "if present, otherwise <dataset-dir>/genome.gff"
        ),
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
    config = GenomicsVariantCallingConfig(
        dataset_dir=args.dataset_dir.expanduser(),
        bam_dir=args.bam_dir.expanduser() if args.bam_dir else None,
        reference_fasta=(
            args.reference_fasta.expanduser() if args.reference_fasta else None
        ),
        regions_bed=args.regions_bed.expanduser() if args.regions_bed else None,
        gff=args.gff.expanduser() if args.gff else None,
        outdir=args.outdir.expanduser(),
    )

    try:
        result = run_genomics_variant_calling_task(config)
    except Exception as exc:
        print(f"[genomics-variants:error] {exc}", file=sys.stderr, flush=True)
        return 1

    outputs = result.get("outputs", {})
    counts = result.get("counts", {})
    print("[genomics-variants] candidate variant calling finished", flush=True)
    print(f"[genomics-variants] candidate_variants: {outputs.get('candidate_variants')}", flush=True)
    print(f"[genomics-variants] report: {outputs.get('report')}", flush=True)
    print(f"[genomics-variants] counts: {counts}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
