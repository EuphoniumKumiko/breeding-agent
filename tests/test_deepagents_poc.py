import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from breeding_agent.agents.context_builder import build_flavonoid_agent_context
from breeding_agent.cli.flavonoid_markers import main as flavonoid_markers_main
from breeding_agent.cli.flavonoid_markers_deepagents import (
    main as deepagents_cli_main,
)
from breeding_agent.cli.flavonoid_markers_graph import main as graph_cli_main
from breeding_agent.deepagents.flavonoid_deepagents_poc import (
    DEEPAGENTS_INSTALL_MESSAGE,
    build_deepagents_decision_rows,
    build_deepagents_trace,
    render_deepagents_summary,
    require_deepagents,
    write_deepagents_artifacts,
)
from breeding_agent.workflows.flavonoid_marker_deepagents import (
    FlavonoidMarkerDeepAgentsConfig,
    run_flavonoid_marker_deepagents_task,
)


EVIDENCE_DIR = Path("outputs/flavonoid_marker_from_package/evidence")


class DeepAgentsPOCTest(unittest.TestCase):
    def test_missing_dependency_message_is_friendly(self):
        if _deepagents_available():
            self.skipTest("Deep Agents is installed")
        with self.assertRaises(RuntimeError) as cm:
            require_deepagents()
        self.assertIn(DEEPAGENTS_INSTALL_MESSAGE, str(cm.exception))

    def test_cli_missing_dependency_returns_clear_code_or_success(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")
        with tempfile.TemporaryDirectory() as tmpdir:
            args = [
                "--evidence-dir",
                str(EVIDENCE_DIR),
                "--outdir",
                str(Path(tmpdir) / "flavonoid_marker_deepagents"),
            ]
            variant_dir = _existing_variant_dir()
            if variant_dir is not None:
                args.extend(["--variant-calling-dir", str(variant_dir)])
            exit_code = deepagents_cli_main(args)
        self.assertIn(exit_code, {0, 2})

    def test_workflow_missing_dependency_writes_failed_manifest(self):
        if _deepagents_available():
            self.skipTest("Deep Agents is installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "flavonoid_marker_deepagents"
            with self.assertRaises(RuntimeError) as cm:
                run_flavonoid_marker_deepagents_task(
                    FlavonoidMarkerDeepAgentsConfig(
                        evidence_dir=EVIDENCE_DIR,
                        outdir=outdir,
                        variant_calling_dir=_existing_variant_dir(),
                    )
                )
            manifest = json.loads((outdir / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn(DEEPAGENTS_INSTALL_MESSAGE, str(cm.exception))
        self.assertEqual(manifest["status"], "failed")
        self.assertIn(DEEPAGENTS_INSTALL_MESSAGE, manifest["error_message"])

    def test_context_builder_can_be_reused_by_deepagents_poc(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")
        context = build_flavonoid_agent_context(
            evidence_dir=EVIDENCE_DIR,
            candidate_rows=[
                {
                    "gene_id": "Si9g04210.1",
                    "variant_status": "not_called",
                    "variant_evidence_status": "no_called_variant_in_current_mini_calling",
                }
            ],
            variant_calling_dir=_existing_variant_dir(),
        )
        for key in [
            "transcriptomics_evidence",
            "metabolomics_evidence",
            "annotation_evidence",
            "literature_evidence",
            "genome_variant_evidence",
            "candidate_rows",
        ]:
            self.assertIn(key, context)
        self.assertIn("Si9g04210.1", context["evidence_by_gene"])

    def test_trace_summary_and_artifact_writers_are_deterministic(self):
        agent_result = _mock_agent_result()
        trace = build_deepagents_trace(agent_result)
        decision_rows = build_deepagents_decision_rows(trace)
        summary = render_deepagents_summary(
            agent_result=agent_result,
            trace=trace,
            decision_rows=decision_rows,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = write_deepagents_artifacts(
                outdir=Path(tmpdir),
                trace=trace,
                summary=summary,
                decision_rows=decision_rows,
            )
            for path in artifacts.values():
                self.assertTrue(Path(path).exists(), path)

        self.assertIn("deepagents_harness_start", json.dumps(trace, ensure_ascii=False))
        self.assertIn("marker_recommendation_agent", summary)
        self.assertIn("不伪造 SNP/InDel", summary)
        self.assertIn("不伪造 DOI", summary)
        self.assertIn("LowQual 不得作为优先推荐", summary)
        self.assertIn("不能替代 WGS/GBS", summary)
        self.assertIn("不调用真实大模型", summary)
        self.assertIn("不调用真实大模型", summary)
        self.assertIn("No real LLM", json.dumps(trace, ensure_ascii=False))

    def test_old_cli_is_unaffected(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "flavonoid_marker_from_package"
            exit_code = flavonoid_markers_main(
                ["--evidence-dir", str(EVIDENCE_DIR), "--outdir", str(outdir)]
            )
            qa_result = json.loads(
                (outdir / "logs" / "qa_check.json").read_text(encoding="utf-8")
            )
        self.assertEqual(exit_code, 0)
        self.assertIs(qa_result["passed"], True)

    def test_langgraph_cli_is_unaffected_by_deepagents_poc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            args = [
                "--evidence-dir",
                str(EVIDENCE_DIR),
                "--outdir",
                str(Path(tmpdir) / "flavonoid_marker_langgraph"),
            ]
            variant_dir = _existing_variant_dir()
            if variant_dir is not None:
                args.extend(["--variant-calling-dir", str(variant_dir)])
            exit_code = graph_cli_main(args)
        self.assertIn(exit_code, {0, 2})

    def test_real_deepagents_workflow_if_dependency_available(self):
        if not _deepagents_available():
            self.skipTest("Deep Agents is not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_flavonoid_marker_deepagents_task(
                FlavonoidMarkerDeepAgentsConfig(
                    evidence_dir=EVIDENCE_DIR,
                    outdir=Path(tmpdir) / "flavonoid_marker_deepagents",
                    variant_calling_dir=_existing_variant_dir(),
                )
            )
            outputs = result["outputs"]
            for key in [
                "deepagents_trace",
                "deepagents_summary",
                "deepagents_decision_table",
                "report",
                "qa_check",
                "manifest",
            ]:
                self.assertTrue(Path(outputs[key]).exists(), outputs[key])
            self.assertIs(result["qa_result"]["passed"], True)


def _deepagents_available() -> bool:
    return importlib.util.find_spec("deepagents") is not None


def _existing_variant_dir() -> Path | None:
    path = Path("outputs/genomics_variant_calling")
    return path if path.exists() else None


def _mock_agent_result() -> dict[str, object]:
    return {
        "candidate_rows": [
            {
                "gene_id": "Si9g04210.1",
                "variant_status": "not_called",
                "variant_evidence_status": "no_called_variant_in_current_mini_calling",
            }
        ],
        "agent_context": {
            "candidate_rows": [{"gene_id": "Si9g04210.1"}],
            "literature_evidence": [{"doi": "10.3390/life11060578"}],
            "variant_evidence": [],
        },
        "agent_outputs": [
            {
                "agent_name": "marker_recommendation_agent",
                "summary": "Generated marker recommendations.",
                "evidence_used": ["flavonoid_marker_candidates.tsv"],
                "warnings": [],
                "limitations": [
                    "No SNP/InDel positions are fabricated.",
                    "LowQual variants are not prioritized.",
                ],
                "structured_payload": {"passed": True},
            },
            {
                "agent_name": "final_qa_agent",
                "summary": "Final QA passed=True.",
                "evidence_used": ["final_report_text"],
                "warnings": [],
                "limitations": ["QA uses deterministic text checks."],
                "structured_payload": {"passed": True},
            },
        ],
        "qa_result": {"passed": True},
        "warnings": [],
        "variant_calling_dir": "outputs/genomics_variant_calling",
    }
