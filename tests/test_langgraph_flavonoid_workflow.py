import csv
import json
import tempfile
import unittest
from pathlib import Path

from breeding_agent.cli.flavonoid_markers_graph import main as graph_cli_main
from breeding_agent.graphs.flavonoid_marker_graph import (
    aggregate_candidates_node,
    build_agent_context_node,
    build_flavonoid_marker_graph,
    final_qa_agent_node,
    initial_graph_state,
    literature_agent_node,
    load_evidence_node,
    marker_recommendation_agent_node,
    report_node,
    reviewer_agent_node,
    validation_agent_node,
    write_outputs_node,
)
from breeding_agent.graphs.state import FlavonoidGraphState
from breeding_agent.reports.langgraph_trace_report import write_node_decision_table
from breeding_agent.workflows.flavonoid_marker_langgraph import (
    FlavonoidMarkerLangGraphConfig,
    run_flavonoid_marker_langgraph_task,
)


EVIDENCE_DIR = Path("outputs/flavonoid_marker_from_package/evidence")
LITERATURE_RESULTS = Path("tests/fixtures/literature_results_v2.jsonl")


class LangGraphFlavonoidWorkflowTest(unittest.TestCase):
    def test_state_is_json_serializable(self):
        state: FlavonoidGraphState = {
            "evidence_dir": str(EVIDENCE_DIR),
            "outdir": "outputs/example",
            "variant_calling_dir": None,
            "target_genes": ["Si9g04210.1"],
            "agent_context": {"example": True},
            "candidate_table_path": None,
            "agent_outputs": [],
            "reviewer_warnings": [],
            "qa_result": {"passed": True},
            "report_path": None,
            "manifest_path": None,
            "graph_trace": [],
            "errors": [],
            "warnings": [],
        }
        encoded = json.dumps(state, ensure_ascii=False)
        self.assertIn("Si9g04210.1", encoded)

    def test_node_decision_table_writer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "node_decision_table.tsv"
            write_node_decision_table(
                path,
                [
                    {
                        "node_id": 1,
                        "node_name": "load_evidence_node",
                        "agent_name": "",
                        "input_summary": "in",
                        "output_summary": "out",
                        "evidence_used": ["transcriptome_evidence.tsv"],
                        "warnings": [],
                        "limitations": ["rule based"],
                        "passed": True,
                    }
                ],
            )
            with path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(rows[0]["node_name"], "load_evidence_node")
        self.assertEqual(rows[0]["evidence_used"], "transcriptome_evidence.tsv")

    def test_manual_nodes_build_expected_graph_trace_and_pass_qa(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")
        with tempfile.TemporaryDirectory() as tmpdir:
            state = initial_graph_state(
                evidence_dir=EVIDENCE_DIR,
                outdir=Path(tmpdir) / "flavonoid_marker_langgraph",
                variant_calling_dir=_existing_variant_dir(),
            )
            for node in [
                load_evidence_node,
                aggregate_candidates_node,
                build_agent_context_node,
                literature_agent_node,
                marker_recommendation_agent_node,
                validation_agent_node,
                reviewer_agent_node,
                final_qa_agent_node,
                report_node,
                write_outputs_node,
            ]:
                state = node(state)

            node_names = [row["node_name"] for row in state["graph_trace"]]
            self.assertIn("load_evidence_node", node_names)
            self.assertIn("marker_recommendation_agent_node", node_names)
            self.assertIn("reviewer_agent_node", node_names)
            self.assertIn("final_qa_agent_node", node_names)
            self.assertIs(state["qa_result"]["passed"], True)

    def test_manual_nodes_accept_external_literature_results(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")
        with tempfile.TemporaryDirectory() as tmpdir:
            state = initial_graph_state(
                evidence_dir=EVIDENCE_DIR,
                outdir=Path(tmpdir) / "flavonoid_marker_langgraph",
                variant_calling_dir=_existing_variant_dir(),
                literature_results_path=LITERATURE_RESULTS,
            )
            for node in [
                load_evidence_node,
                aggregate_candidates_node,
                build_agent_context_node,
                literature_agent_node,
                marker_recommendation_agent_node,
                validation_agent_node,
                reviewer_agent_node,
                final_qa_agent_node,
                report_node,
                write_outputs_node,
            ]:
                state = node(state)

            self.assertEqual(state["literature_analysis"]["literature_result_count"], 2)
            self.assertEqual(state["literature_analysis"]["demo_result_count"], 1)
            self.assertTrue(state["qa_result"]["no_llm_generated_doi"])
            self.assertIn("文献查询与分析", state["report_text"])
            self.assertIn("PubMedFixture", state["report_text"])
            query_plan_jsonl = Path(state["literature_query_plan_jsonl_path"])
            query_plan_tsv = Path(state["literature_query_plan_tsv_path"])
            self.assertTrue(query_plan_jsonl.exists())
            self.assertTrue(query_plan_tsv.exists())
            query_plan_text = query_plan_jsonl.read_text(encoding="utf-8")
            self.assertIn("Si9g04210.1", query_plan_text)
            self.assertIn("KASP marker", query_plan_text)

    def test_langgraph_missing_error_is_friendly_or_graph_builds(self):
        try:
            graph = build_flavonoid_marker_graph()
        except RuntimeError as exc:
            self.assertIn("pip install langgraph", str(exc))
        else:
            self.assertIsNotNone(graph)

    def test_graph_cli_returns_friendly_missing_dependency_code_or_success(self):
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
            args.extend(["--literature-results", str(LITERATURE_RESULTS)])
            exit_code = graph_cli_main(
                args
            )
        self.assertIn(exit_code, {0, 2})

    def test_real_langgraph_workflow_if_dependency_available(self):
        try:
            build_flavonoid_marker_graph()
        except RuntimeError as exc:
            if "pip install langgraph" in str(exc):
                self.skipTest("LangGraph is not installed")
            raise

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_flavonoid_marker_langgraph_task(
                FlavonoidMarkerLangGraphConfig(
                    evidence_dir=EVIDENCE_DIR,
                    outdir=Path(tmpdir) / "flavonoid_marker_langgraph",
                    variant_calling_dir=_existing_variant_dir(),
                )
            )
            outputs = result["outputs"]
            qa_result = result["qa_result"]

            required_keys = [
                "graph_trace",
                "graph_state_final",
                "node_decision_table",
                "langgraph_summary",
                "report",
                "qa_check",
                "manifest",
                "literature_query_plan_jsonl",
                "literature_query_plan_tsv",
            ]
            for key in required_keys:
                self.assertIn(key, outputs)
                self.assertTrue(Path(outputs[key]).exists(), outputs[key])

            trace_text = Path(outputs["graph_trace"]).read_text(encoding="utf-8")
            decision_text = Path(outputs["node_decision_table"]).read_text(
                encoding="utf-8"
            )
            summary_text = Path(outputs["langgraph_summary"]).read_text(
                encoding="utf-8"
            )

            self.assertIn("load_evidence_node", trace_text)
            self.assertIn("marker_recommendation_agent_node", trace_text)
            self.assertIn("reviewer_agent_node", trace_text)
            self.assertIn("final_qa_agent_node", trace_text)
            self.assertIn("node_name", decision_text)
            self.assertIn("marker_recommendation_agent_node", decision_text)
            self.assertIn("LangGraph 多智能体聚合流程概览", summary_text)
            self.assertIs(qa_result["passed"], True)


def _existing_variant_dir() -> Path | None:
    path = Path("outputs/genomics_variant_calling")
    return path if path.exists() else None
