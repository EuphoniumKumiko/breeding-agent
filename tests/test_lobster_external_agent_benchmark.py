"""Tests for Lobster-style external omics agent benchmark."""

from __future__ import annotations

import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

from breeding_agent.external_agents.lobster_reference_adapter import (
    run_lobster_style_reference_assessment,
)
from breeding_agent.workflows.lobster_external_agent_benchmark import (
    LobsterExternalAgentBenchmarkConfig,
    run_lobster_external_agent_benchmark_task,
)


POSITION_RE = re.compile(
    r"(?i)(?:chr\w+|scaffold\w+|contig\w+|si\d+\w*)[:：]\d+|\bposition=\d+"
)


class TestLobsterExternalAgentBenchmark(unittest.TestCase):
    def test_reference_metadata_is_mock_lobster_style(self) -> None:
        result = run_lobster_style_reference_assessment(
            evidence_dir=Path("outputs/flavonoid_marker_from_package/evidence"),
            variant_calling_dir=Path("outputs/genomics_variant_calling"),
        )

        self.assertEqual(result.backend_name, "lobster_ai_reference")
        self.assertEqual(result.backend_mode, "mock_reference")
        self.assertFalse(result.real_lobster_run)
        self.assertEqual(result.reference_project_url, "https://github.com/the-omics-os/lobster")

    def test_workflow_writes_reports_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            internal_dir = tmp_path / "internal_langgraph"
            _write_fake_internal_langgraph_outputs(internal_dir)
            result = run_lobster_external_agent_benchmark_task(
                LobsterExternalAgentBenchmarkConfig(
                    evidence_dir=Path("outputs/flavonoid_marker_from_package/evidence"),
                    variant_calling_dir=Path("outputs/genomics_variant_calling"),
                    internal_agent_outdir=internal_dir,
                    outdir=tmp_path / "benchmark",
                )
            )

            outputs = result["outputs"]
            report_path = Path(outputs["lobster_style_agent_report"])
            comparison_path = Path(outputs["lobster_vs_internal_comparison"])
            matrix_path = Path(outputs["comparison_matrix"])
            manifest_path = Path(outputs["benchmark_manifest"])

            self.assertTrue(report_path.exists())
            self.assertTrue(comparison_path.exists())
            self.assertTrue(matrix_path.exists())
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["backend_name"], "lobster_ai_reference")
        self.assertEqual(manifest["backend_mode"], "mock_reference")
        self.assertFalse(manifest["real_lobster_run"])

    def test_report_states_not_real_lobster_run_and_does_not_fabricate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            internal_dir = tmp_path / "internal_langgraph"
            _write_fake_internal_langgraph_outputs(internal_dir)
            result = run_lobster_external_agent_benchmark_task(
                LobsterExternalAgentBenchmarkConfig(
                    evidence_dir=Path("outputs/flavonoid_marker_from_package/evidence"),
                    variant_calling_dir=Path("outputs/genomics_variant_calling"),
                    internal_agent_outdir=internal_dir,
                    outdir=tmp_path / "benchmark",
                )
            )
            report_text = Path(result["outputs"]["lobster_style_agent_report"]).read_text(
                encoding="utf-8"
            )

        self.assertIn(
            "This is a Lobster-style reference benchmark, not a real Lobster AI run.",
            report_text,
        )
        self.assertNotIn("10.9999", report_text)
        self.assertIsNone(POSITION_RE.search(report_text))

    def test_comparison_matrix_contains_required_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            internal_dir = tmp_path / "internal_langgraph"
            _write_fake_internal_langgraph_outputs(internal_dir)
            result = run_lobster_external_agent_benchmark_task(
                LobsterExternalAgentBenchmarkConfig(
                    evidence_dir=Path("outputs/flavonoid_marker_from_package/evidence"),
                    variant_calling_dir=Path("outputs/genomics_variant_calling"),
                    internal_agent_outdir=internal_dir,
                    outdir=tmp_path / "benchmark",
                )
            )
            matrix_path = Path(result["outputs"]["comparison_matrix"])
            with matrix_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))

        dimensions = {row["dimension"] for row in rows}
        self.assertIn("three_target_genes_covered", dimensions)
        self.assertIn("has_local_llm_reviewer_status", dimensions)
        self.assertIn("states_not_replace_wgs_gbs", dimensions)


def _write_fake_internal_langgraph_outputs(outdir: Path) -> None:
    graph_dir = outdir / "graph"
    reports_dir = outdir / "reports"
    logs_dir = outdir / "logs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    report_text = (
        "Si9g04210.1 Si5g31340.1 Si9g34380.1 群体 文献查阅 DOI "
        "10.3390/life11060578 baseMean log2FC pvalue padj SNP InDel KASP CAPS "
        "PASS LowQual preliminary 不能替代 WGS/GBS 育种 标记 graph_trace qa_check manifest"
    )
    (reports_dir / "flavonoid_marker_report.md").write_text(
        report_text,
        encoding="utf-8",
    )
    (graph_dir / "langgraph_summary.md").write_text(report_text, encoding="utf-8")
    (graph_dir / "node_decision_table.tsv").write_text(
        "node_id\tnode_name\toutput_summary\n"
        "1\treviewer_agent_node\tllm_reviewer_enabled=true; llm_used=true; "
        "fallback_used=false; model=qwen/qwen3.5-9b; guard_passed=true; fallback_reason=\n",
        encoding="utf-8",
    )
    (graph_dir / "graph_trace.json").write_text(
        json.dumps(
            [
                {
                    "node_name": "reviewer_agent_node",
                    "llm_reviewer_enabled": True,
                    "llm_used": True,
                    "fallback_used": False,
                    "model": "qwen/qwen3.5-9b",
                    "guard_passed": True,
                    "fallback_reason": "",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (logs_dir / "qa_check.json").write_text(
        json.dumps({"passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (outdir / "manifest.json").write_text(
        json.dumps({"llm_reviewer": {"llm_used": True}}, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
