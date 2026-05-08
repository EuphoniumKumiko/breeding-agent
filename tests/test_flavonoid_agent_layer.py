import json
import re
import tempfile
import unittest
from pathlib import Path

from breeding_agent.agents.flavonoid_final_qa_agent import FlavonoidFinalQAAgent
from breeding_agent.agents.flavonoid_literature_agent import (
    FlavonoidLiteratureAgent,
)
from breeding_agent.agents.flavonoid_marker_recommendation_agent import (
    FlavonoidMarkerRecommendationAgent,
)
from breeding_agent.agents.flavonoid_validation_agent import (
    FlavonoidValidationAgent,
)
from breeding_agent.cli.flavonoid_markers import main as flavonoid_markers_main


EVIDENCE_DIR = Path("outputs/flavonoid_marker_from_package/evidence")
COMPLETE_REPORT = """
# 测试报告
文献查阅过程展示 DOI 10.3390/life11060578。
群体验证需要 SNP、InDel、KASP、CAPS。
| gene_id | baseMean | log2FC | pvalue | padj |
| --- | ---: | ---: | ---: | ---: |
| Si9g04210.1 | 3234.583184 | -6.542585349 | 2.5e-162 | 5.62e-158 |
| Si5g31340.1 | 173.0025915 | 1.574439128 | 5.86e-10 | 4.71e-07 |
| Si9g34380.1 | 73.04607021 | 3.204977856 | 3.18e-17 | 8.95e-14 |
"""


class FlavonoidAgentLayerTest(unittest.TestCase):
    def test_literature_agent_returns_doi_review_text(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")

        result = FlavonoidLiteratureAgent(EVIDENCE_DIR).run()
        review_text = result["literature_review_text"]

        self.assertIn("文献查阅过程", review_text)
        self.assertIn("DOI", review_text)
        self.assertIn("10.3390/life11060578", review_text)

    def test_marker_agent_does_not_fabricate_variant_positions_when_not_called(self):
        rows = [
            {
                "gene_id": "Si9g04210.1",
                "variant_status": "not_called",
            }
        ]
        result = FlavonoidMarkerRecommendationAgent().run(rows)
        text = result["marker_recommendation_text"]

        self.assertIn("当前没有最终 SNP/InDel 位点", text)
        self.assertIn("SNP/InDel/KASP", text)
        self.assertIn("CAPS", text)
        self.assertIsNone(
            re.search(
                r"(?i)(?:chr\w+|scaffold\w+|contig\w+)[:：]\d+|\bposition=\d+|\b\d+:\d+\b",
                text,
            )
        )

    def test_validation_agent_output_contains_population_term(self):
        result = FlavonoidValidationAgent().run(
            [{"gene_id": "Si9g04210.1"}, {"gene_id": "Si5g31340.1"}]
        )
        text = result["validation_plan_text"]

        self.assertIn("群体", text)
        self.assertIn("Sanger", text)
        self.assertIn("SNP/InDel calling", text)
        self.assertIn("KASP", text)
        self.assertIn("CAPS/dCAPS", text)
        self.assertIn("qRT-PCR", text)
        self.assertIn("LC-MS/MS", text)

    def test_final_qa_agent_passes_complete_report(self):
        result = FlavonoidFinalQAAgent().run(COMPLETE_REPORT)

        self.assertIs(result["passed"], True)

    def test_cli_runs_with_real_evidence(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "flavonoid_marker_from_package"
            exit_code = flavonoid_markers_main(
                [
                    "--evidence-dir",
                    str(EVIDENCE_DIR),
                    "--outdir",
                    str(outdir),
                ]
            )

            self.assertEqual(exit_code, 0)
            qa_file = outdir / "logs" / "qa_check.json"
            report_file = outdir / "reports" / "flavonoid_marker_report.md"
            candidate_file = outdir / "integration" / "flavonoid_marker_candidates.tsv"
            self.assertTrue(qa_file.exists())
            self.assertTrue(report_file.exists())
            self.assertTrue(candidate_file.exists())
            qa_result = json.loads(qa_file.read_text(encoding="utf-8"))
            self.assertIs(qa_result["passed"], True)


if __name__ == "__main__":
    unittest.main()
