"""Create flavonoid marker evidence tables from the mini data package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from breeding_agent.integration.flavonoid_marker_package_importer import (
    TARGET_GENES,
    create_evidence_from_package,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create standard flavonoid marker aggregation evidence tables from "
            "the mini data package."
        )
    )
    parser.add_argument(
        "--dataset-dir",
        required=True,
        type=Path,
        help="Mini flavonoid marker data package directory.",
    )
    parser.add_argument(
        "--outdir",
        required=True,
        type=Path,
        help="Directory for generated evidence TSV files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_dir = args.dataset_dir.expanduser()
    outdir = args.outdir.expanduser()

    try:
        result = create_evidence_from_package(
            dataset_dir=dataset_dir,
            outdir=outdir,
        )
    except Exception as exc:
        print(f"[flavonoid-evidence:error] {exc}", file=sys.stderr)
        return 1

    _print_warnings(result)
    _print_summary(result)
    return 0


def _print_warnings(result: dict[str, object]) -> None:
    for missing_path in result["optional_missing"]:
        print(
            f"[flavonoid-evidence:warning] Optional package file missing: {missing_path}",
            file=sys.stderr,
        )


def _print_summary(result: dict[str, object]) -> None:
    print("[flavonoid-evidence] Wrote evidence files:")
    for filename, path, row_count in result["written_files"]:
        print(f"[flavonoid-evidence]   {filename}: {path} ({row_count} rows)")

    missing_targets = result.get("missing_targets", [])
    if missing_targets:
        print(
            "[flavonoid-evidence] Target genes present: no; "
            f"missing={', '.join(str(gene_id) for gene_id in missing_targets)}"
        )
    else:
        print(
            "[flavonoid-evidence] Target genes present: yes; "
            f"all fixed targets found ({', '.join(TARGET_GENES)})"
        )


if __name__ == "__main__":
    raise SystemExit(main())
