"""CLI for optional LangGraph flavonoid marker workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from breeding_agent.graphs.flavonoid_marker_graph import LANGGRAPH_INSTALL_MESSAGE
from breeding_agent.workflows.flavonoid_marker_langgraph import (
    DEFAULT_LANGGRAPH_OUTDIR,
    FlavonoidMarkerLangGraphConfig,
    run_flavonoid_marker_langgraph_task,
)


def build_parser() -> argparse.ArgumentParser:
    # This CLI is a thin wiring layer: it only collects paths/flags and hands
    # them to the LangGraph workflow wrapper.
    parser = argparse.ArgumentParser(
        prog="python -m breeding_agent.cli.flavonoid_markers_graph",
        description="Run LangGraph-based flavonoid marker recommendation workflow.",
    )
    parser.add_argument(
        "--evidence-dir",
        required=True,
        type=Path,
        help="Directory containing standard flavonoid marker evidence TSV files.",
    )
    parser.add_argument(
        "--outdir",
        default=Path(DEFAULT_LANGGRAPH_OUTDIR),
        type=Path,
        help=f"Output directory. Default: {DEFAULT_LANGGRAPH_OUTDIR}",
    )
    parser.add_argument(
        "--variant-calling-dir",
        default=None,
        type=Path,
        help="Optional genomics variant calling output directory.",
    )
    parser.add_argument(
        "--literature-results",
        default=None,
        type=Path,
        help="Optional normalized literature search JSONL exported by agri-breeding-literature-pipeline.",
    )
    parser.add_argument(
        "--use-llm-reviewer",
        action="store_true",
        help="Enable optional local OpenAI-compatible LLM enhancement for ReviewerAgent only.",
    )
    parser.add_argument(
        "--llm-config",
        default=Path("configs/llm.local.example.yaml"),
        type=Path,
        help="Local OpenAI-compatible LLM config path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # Parse CLI inputs, build workflow config, and print the generated artifact
    # locations for downstream inspection.
    args = build_parser().parse_args(argv)
    config = FlavonoidMarkerLangGraphConfig(
        evidence_dir=args.evidence_dir.expanduser(),
        outdir=args.outdir.expanduser(),
        variant_calling_dir=(
            args.variant_calling_dir.expanduser()
            if args.variant_calling_dir
            else None
        ),
        literature_results=(
            args.literature_results.expanduser()
            if args.literature_results
            else None
        ),
        use_llm_reviewer=bool(args.use_llm_reviewer),
        llm_config=args.llm_config.expanduser(),
    )
    try:
        result = run_flavonoid_marker_langgraph_task(config)
    except RuntimeError as exc:
        if LANGGRAPH_INSTALL_MESSAGE in str(exc):
            print(LANGGRAPH_INSTALL_MESSAGE, file=sys.stderr, flush=True)
            return 2
        print(f"[flavonoid-markers-graph:error] {exc}", file=sys.stderr, flush=True)
        return 1
    except Exception as exc:
        print(f"[flavonoid-markers-graph:error] {exc}", file=sys.stderr, flush=True)
        return 1

    outputs = result.get("outputs", {})
    qa_result = result.get("qa_result", {})
    if not isinstance(outputs, dict):
        outputs = {}
    if not isinstance(qa_result, dict):
        qa_result = {}
    print("[flavonoid-markers-graph] graph workflow finished", flush=True)
    print(f"[flavonoid-markers-graph] graph_trace: {outputs.get('graph_trace')}", flush=True)
    print(
        "[flavonoid-markers-graph] langgraph_summary: "
        f"{outputs.get('langgraph_summary')}",
        flush=True,
    )
    print(f"[flavonoid-markers-graph] report: {outputs.get('report')}", flush=True)
    print(f"[flavonoid-markers-graph] qa_check: {outputs.get('qa_check')}", flush=True)
    print(
        "[flavonoid-markers-graph] literature_query_plan_jsonl: "
        f"{outputs.get('literature_query_plan_jsonl')}",
        flush=True,
    )
    print(
        "[flavonoid-markers-graph] literature_query_plan_tsv: "
        f"{outputs.get('literature_query_plan_tsv')}",
        flush=True,
    )
    print(f"[flavonoid-markers-graph] qa passed: {qa_result.get('passed')}", flush=True)
    llm_metadata = result.get("llm_reviewer", {})
    if isinstance(llm_metadata, dict):
        print(
            "[flavonoid-markers-graph] llm reviewer: "
            f"enabled={llm_metadata.get('llm_reviewer_enabled')} "
            f"used={llm_metadata.get('llm_used')} "
            f"fallback={llm_metadata.get('fallback_used')} "
            f"model={llm_metadata.get('model')} "
            f"guard_passed={llm_metadata.get('guard_passed')} "
            f"fallback_reason={llm_metadata.get('fallback_reason')}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
