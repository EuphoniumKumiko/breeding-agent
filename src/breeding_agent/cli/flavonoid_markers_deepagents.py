"""CLI for optional Deep Agents flavonoid marker POC."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from breeding_agent.deepagents.flavonoid_deepagents_poc import (
    DEEPAGENTS_INSTALL_MESSAGE,
)
from breeding_agent.workflows.flavonoid_marker_deepagents import (
    DEFAULT_DEEPAGENTS_OUTDIR,
    FlavonoidMarkerDeepAgentsConfig,
    run_flavonoid_marker_deepagents_task,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m breeding_agent.cli.flavonoid_markers_deepagents",
        description="Run the optional Deep Agents flavonoid marker POC.",
    )
    parser.add_argument(
        "--evidence-dir",
        required=True,
        type=Path,
        help="Directory containing standard flavonoid marker evidence TSV files.",
    )
    parser.add_argument(
        "--outdir",
        default=Path(DEFAULT_DEEPAGENTS_OUTDIR),
        type=Path,
        help=f"Output directory. Default: {DEFAULT_DEEPAGENTS_OUTDIR}",
    )
    parser.add_argument(
        "--variant-calling-dir",
        default=None,
        type=Path,
        help="Optional genomics variant calling output directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = FlavonoidMarkerDeepAgentsConfig(
        evidence_dir=args.evidence_dir.expanduser(),
        outdir=args.outdir.expanduser(),
        variant_calling_dir=(
            args.variant_calling_dir.expanduser()
            if args.variant_calling_dir
            else None
        ),
    )
    try:
        result = run_flavonoid_marker_deepagents_task(config)
    except RuntimeError as exc:
        if DEEPAGENTS_INSTALL_MESSAGE in str(exc):
            print(DEEPAGENTS_INSTALL_MESSAGE, file=sys.stderr, flush=True)
            return 2
        print(f"[flavonoid-markers-deepagents:error] {exc}", file=sys.stderr, flush=True)
        return 1
    except Exception as exc:
        print(f"[flavonoid-markers-deepagents:error] {exc}", file=sys.stderr, flush=True)
        return 1

    outputs = result.get("outputs", {})
    qa_result = result.get("qa_result", {})
    if not isinstance(outputs, dict):
        outputs = {}
    if not isinstance(qa_result, dict):
        qa_result = {}
    print("[flavonoid-markers-deepagents] POC workflow finished", flush=True)
    print(
        "[flavonoid-markers-deepagents] deepagents_trace: "
        f"{outputs.get('deepagents_trace')}",
        flush=True,
    )
    print(
        "[flavonoid-markers-deepagents] deepagents_summary: "
        f"{outputs.get('deepagents_summary')}",
        flush=True,
    )
    print(
        "[flavonoid-markers-deepagents] report: "
        f"{outputs.get('report')}",
        flush=True,
    )
    print(
        "[flavonoid-markers-deepagents] qa_check: "
        f"{outputs.get('qa_check')}",
        flush=True,
    )
    print(
        f"[flavonoid-markers-deepagents] qa passed: {qa_result.get('passed')}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
