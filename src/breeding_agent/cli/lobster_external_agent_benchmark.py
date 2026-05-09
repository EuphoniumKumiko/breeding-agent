"""CLI for Lobster-style external omics agent benchmark."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from breeding_agent.workflows.lobster_external_agent_benchmark import (
    DEFAULT_LOBSTER_BENCHMARK_OUTDIR,
    LobsterExternalAgentBenchmarkConfig,
    run_lobster_external_agent_benchmark_task,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m breeding_agent.cli.lobster_external_agent_benchmark",
        description="Run a Lobster-style mock external omics agent benchmark.",
    )
    parser.add_argument(
        "--evidence-dir",
        required=True,
        type=Path,
        help="Directory containing standard flavonoid marker evidence TSV files.",
    )
    parser.add_argument(
        "--variant-calling-dir",
        default=None,
        type=Path,
        help="Optional Genomics Candidate Variant Calling output directory.",
    )
    parser.add_argument(
        "--internal-agent-outdir",
        required=True,
        type=Path,
        help="Existing internal LangGraph agent output directory to compare against.",
    )
    parser.add_argument(
        "--outdir",
        default=Path(DEFAULT_LOBSTER_BENCHMARK_OUTDIR),
        type=Path,
        help=f"Benchmark output directory. Default: {DEFAULT_LOBSTER_BENCHMARK_OUTDIR}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_lobster_external_agent_benchmark_task(
            LobsterExternalAgentBenchmarkConfig(
                evidence_dir=args.evidence_dir,
                variant_calling_dir=args.variant_calling_dir,
                internal_agent_outdir=args.internal_agent_outdir,
                outdir=args.outdir,
            )
        )
    except Exception as exc:  # noqa: BLE001 - CLI should report benchmark failure
        print(f"[lobster-external-agent-benchmark:error] {exc}", file=sys.stderr)
        return 1

    outputs = result.get("outputs", {})
    if not isinstance(outputs, dict):
        outputs = {}
    print("[lobster-external-agent-benchmark] benchmark finished", flush=True)
    print(
        "[lobster-external-agent-benchmark] lobster_style_agent_report: "
        f"{outputs.get('lobster_style_agent_report')}",
        flush=True,
    )
    print(
        "[lobster-external-agent-benchmark] comparison_matrix: "
        f"{outputs.get('comparison_matrix')}",
        flush=True,
    )
    print(
        "[lobster-external-agent-benchmark] lobster_vs_internal_comparison: "
        f"{outputs.get('lobster_vs_internal_comparison')}",
        flush=True,
    )
    print(
        "[lobster-external-agent-benchmark] real_lobster_run: false",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
