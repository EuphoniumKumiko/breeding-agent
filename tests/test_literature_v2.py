import json
import tempfile
import unittest
from pathlib import Path

from breeding_agent.agents.flavonoid_literature_agent import FlavonoidLiteratureAgent
from breeding_agent.integration.flavonoid_marker_qa import check_flavonoid_marker_report
from breeding_agent.literature.analyzer import analyze_literature
from breeding_agent.literature.loader import load_literature_results
from breeding_agent.literature.normalizer import normalize_literature_row
from breeding_agent.reports.flavonoid_marker_report import render_flavonoid_marker_report


EVIDENCE_DIR = Path("outputs/flavonoid_marker_from_package/evidence")
FIXTURE = Path("tests/fixtures/literature_results_v2.jsonl")


class LiteratureV2Test(unittest.TestCase):
    def test_jsonl_loader_marks_demo_fixture_not_real_evidence(self):
        records = load_literature_results(FIXTURE)

        self.assertEqual(len(records), 2)
        demo = [record for record in records if record.source == "PubMedFixture"][0]
        real = [record for record in records if record.source == "PubMed"][0]
        self.assertTrue(demo.is_demo)
        self.assertFalse(demo.is_real_evidence)
        self.assertFalse(real.is_demo)
        self.assertTrue(real.is_real_evidence)

    def test_literature_agent_v2_separates_real_and_demo_doi_sources(self):
        output = FlavonoidLiteratureAgent(
            EVIDENCE_DIR,
            literature_results_path=FIXTURE,
        ).run()
        analysis = output["literature_analysis"]

        self.assertEqual(analysis["literature_result_count"], 2)
        self.assertEqual(analysis["real_result_count"], 1)
        self.assertEqual(analysis["demo_result_count"], 1)
        self.assertIn("10.1111/real.setaria", analysis["doi_sources"]["literature_results_real"])
        self.assertIn("10.1000/demo.fixture", analysis["doi_sources"]["literature_results_demo"])
        self.assertIn("10.1000/demo.fixture", analysis["doi_sources"]["demo_dois"])
        self.assertIn("10.1111/real.setaria", analysis["doi_sources"]["allowed_report_dois"])
        self.assertNotIn("10.1000/demo.fixture", analysis["doi_sources"]["allowed_report_dois"])
        self.assertNotIn("10.1000/demo.fixture", output["allowed_report_dois"])
        self.assertEqual(analysis["literature_relevance_counts"]["high"], 1)
        self.assertEqual(analysis["real_records"][0]["relevance_level"], "high")
        self.assertIn("demo fixture rows: 1", output["literature_review_text"])
        self.assertIn("不计入真实 PubMed evidence", output["literature_review_text"])
        self.assertIn("external relevance counts", output["literature_review_text"])

    def test_report_contains_literature_query_analysis_section(self):
        output = FlavonoidLiteratureAgent(
            EVIDENCE_DIR,
            literature_results_path=FIXTURE,
        ).run()
        report = render_flavonoid_marker_report(
            evidence_dir=EVIDENCE_DIR,
            candidate_rows=_candidate_rows(),
            literature_rows=output["literature_rows"],
            literature_analysis=output["literature_analysis"],
            warnings=[],
            literature_review_text=output["literature_review_text"],
            marker_recommendation_text="SNP InDel KASP CAPS；不是最终标记。",
            validation_plan_text="后续开展群体验证；不能替代 WGS/GBS 群体变异检测。",
        )

        self.assertIn("## 8. 文献查询与分析", report)
        self.assertIn("Real PubMed-like flavonoid pathway evidence", report)
        self.assertIn("Demo KASP marker fixture", report)
        self.assertIn("relevance_level", report)
        self.assertIn("directly relevant candidate/background support", report)
        self.assertIn("DEMO_ONLY", report)
        self.assertNotIn("10.1000/demo.fixture", report)
        self.assertIn("demo only; excluded from real DOI evidence", report)

    def test_literature_relevance_levels_are_rule_based(self):
        records = [
            normalize_literature_row(
                {
                    "query": "Setaria italica flavonoid biosynthesis",
                    "title": "Setaria italica flavonoid candidate gene analysis",
                    "abstract": "Marker and breeding context.",
                    "doi": "10.1111/high",
                    "source": "PubMed",
                    "is_demo": False,
                    "matched_terms": ["Setaria italica", "flavonoid", "candidate gene"],
                }
            ),
            normalize_literature_row(
                {
                    "query": "millet flavonoid background",
                    "title": "Millet flavonoid composition",
                    "abstract": "Food chemistry background.",
                    "doi": "10.1111/medium",
                    "source": "PubMed",
                    "is_demo": False,
                    "matched_terms": ["millet", "flavonoid"],
                }
            ),
            normalize_literature_row(
                {
                    "query": "plant food chemistry",
                    "title": "Cereal food chemistry",
                    "abstract": "General antioxidant analysis.",
                    "doi": "10.1111/background",
                    "source": "PubMed",
                    "is_demo": False,
                    "matched_terms": ["food chemistry"],
                }
            ),
        ]
        analysis = analyze_literature(
            verified_literature_rows=[],
            literature_results=records,
        ).to_dict()

        self.assertEqual(
            analysis["literature_relevance_counts"],
            {"high": 1, "medium": 1, "background": 1},
        )
        self.assertEqual(
            [record["relevance_level"] for record in analysis["real_records"]],
            ["high", "medium", "background"],
        )

    def test_report_qa_summary_redacts_demo_doi_values(self):
        output = FlavonoidLiteratureAgent(
            EVIDENCE_DIR,
            literature_results_path=FIXTURE,
        ).run()
        report = render_flavonoid_marker_report(
            evidence_dir=EVIDENCE_DIR,
            candidate_rows=_candidate_rows(),
            literature_rows=output["literature_rows"],
            literature_analysis=output["literature_analysis"],
            warnings=[],
            literature_review_text=output["literature_review_text"],
            marker_recommendation_text="SNP InDel KASP CAPS；不是最终标记。",
            validation_plan_text="后续开展群体验证；不能替代 WGS/GBS 群体变异检测。",
            qa_result={
                "passed": True,
                "report_dois": ["10.3390/life11060578"],
                "allowed_report_dois": ["10.3390/life11060578"],
                "report_demo_dois": [],
                "doi_sources": output["literature_analysis"]["doi_sources"],
                "literature_relevance_counts": output["literature_analysis"][
                    "literature_relevance_counts"
                ],
            },
        )

        self.assertIn("DEMO_ONLY", report)
        self.assertIn("demo only; excluded from real DOI evidence and report_dois", report)
        self.assertNotIn("10.1000/demo.fixture", report)

    def test_qa_excludes_demo_doi_from_report_and_allowed_doi_fields(self):
        literature_analysis = {
            "literature_result_count": 2,
            "literature_query_count": 2,
            "doi_sources": {
                "verified_evidence": ["10.3390/life11060578"],
                "literature_results_real": ["10.1111/real.setaria"],
                "literature_results_demo": ["10.1000/demo.fixture"],
                "demo_dois": ["10.1000/demo.fixture"],
                "allowed_report_dois": [
                    "10.3390/life11060578",
                    "10.1111/real.setaria",
                    "10.1000/demo.fixture",
                ],
            },
            "literature_relevance_counts": {"high": 1, "medium": 0, "background": 0},
        }
        report = _complete_report() + "\n外部 demo fixture DOI 10.1000/demo.fixture。\n"

        result = check_flavonoid_marker_report(
            report,
            allowed_dois=[
                "10.3390/life11060578",
                "10.1111/real.setaria",
                "10.1000/demo.fixture",
            ],
            literature_analysis=literature_analysis,
        )

        self.assertFalse(result["passed"])
        self.assertTrue(result["has_doi"])
        self.assertIn("10.3390/life11060578", result["report_dois"])
        self.assertNotIn("10.1000/demo.fixture", result["report_dois"])
        self.assertNotIn("10.1000/demo.fixture", result["allowed_report_dois"])
        self.assertIn("10.1000/demo.fixture", result["report_demo_dois"])
        self.assertIn(
            "10.1000/demo.fixture",
            result["doi_sources"]["literature_results_demo"],
        )
        self.assertEqual(
            result["literature_relevance_counts"],
            {"high": 1, "medium": 0, "background": 0},
        )

    def test_qa_blocks_report_doi_not_in_allowed_sources(self):
        report = _complete_report() + "\n额外伪造 DOI 10.9999/not.allowed。\n"
        result = check_flavonoid_marker_report(
            report,
            allowed_dois=["10.3390/life11060578"],
            literature_analysis={
                "literature_result_count": 2,
                "literature_query_count": 2,
                "doi_sources": {
                    "verified_evidence": ["10.3390/life11060578"],
                    "literature_results_real": [],
                    "literature_results_demo": [],
                    "allowed_report_dois": ["10.3390/life11060578"],
                },
            },
        )

        self.assertFalse(result["passed"])
        self.assertFalse(result["no_llm_generated_doi"])
        self.assertIn("10.9999/not.allowed", result["unexpected_dois"])
        self.assertEqual(result["literature_result_count"], 2)
        self.assertEqual(result["literature_query_count"], 2)


def _candidate_rows():
    return [
        {
            "gene_id": "Si9g04210.1",
            "baseMean": "3234.58",
            "log2FC": "-6.54",
            "pvalue": "2.5e-162",
            "padj": "5.62e-158",
            "variant_status": "not_called",
            "marker_recommendation": "候选 SNP/InDel/KASP/CAPS 开发需后续验证。",
        },
        {
            "gene_id": "Si5g31340.1",
            "baseMean": "173.00",
            "log2FC": "1.57",
            "pvalue": "5.86e-10",
            "padj": "4.71e-07",
            "variant_status": "not_called",
            "marker_recommendation": "候选 SNP/InDel/KASP/CAPS 开发需后续验证。",
        },
        {
            "gene_id": "Si9g34380.1",
            "baseMean": "73.04",
            "log2FC": "3.20",
            "pvalue": "3.18e-17",
            "padj": "8.95e-14",
            "variant_status": "not_called",
            "marker_recommendation": "候选 SNP/InDel/KASP/CAPS 开发需后续验证。",
        },
    ]


def _complete_report() -> str:
    return """
# 测试报告
文献查阅过程展示 DOI 10.3390/life11060578。
群体验证需要 SNP、InDel、KASP、CAPS。
| gene_id | baseMean | log2FC | pvalue | padj |
| --- | ---: | ---: | ---: | ---: |
| Si9g04210.1 | 3234.583184 | -6.542585349 | 2.5e-162 | 5.62e-158 |
| Si5g31340.1 | 173.0025915 | 1.574439128 | 5.86e-10 | 4.71e-07 |
| Si9g34380.1 | 73.04607021 | 3.204977856 | 3.18e-17 | 8.95e-14 |
"""


if __name__ == "__main__":
    unittest.main()
