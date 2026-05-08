"""Command line entry point for flavonoid marker aggregation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from breeding_agent.workflows.flavonoid_marker_aggregation import (
    DEFAULT_OUTDIR,
    FlavonoidMarkerAggregationConfig,
    run_flavonoid_marker_aggregation_task,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m breeding_agent.cli.flavonoid_markers",
        description="Run rule-based flavonoid marker evidence aggregation.",
    )
    parser.add_argument(
        "--evidence-dir",
        required=True,
        type=Path,
        help="Directory containing standard flavonoid marker evidence TSV files.",
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
    config = FlavonoidMarkerAggregationConfig(
        evidence_dir=args.evidence_dir.expanduser(),
        outdir=args.outdir.expanduser(),
    )

    try:
        report_file = run_flavonoid_marker_aggregation_task(config)
    except Exception as exc:
        print(f"[flavonoid-markers:error] {exc}", file=sys.stderr, flush=True)
        return 1

    print(f"[flavonoid-markers] final report: {report_file}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
