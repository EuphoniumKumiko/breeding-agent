import csv
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

    def test_marker_agent_describes_variant_evidence_quality_statuses(self):
        rows = [
            {
                "gene_id": "Si5g31340.1",
                "variant_status": "not_called",
                "variant_evidence_status": "preliminary_pass_variants_detected",
            },
            {
                "gene_id": "Si9g34380.1",
                "variant_status": "not_called",
                "variant_evidence_status": "only_low_quality_variants_detected",
            },
            {
                "gene_id": "Si9g04210.1",
                "variant_status": "not_called",
                "variant_evidence_status": "no_called_variant_in_current_mini_calling",
            },
        ]
        result = FlavonoidMarkerRecommendationAgent().run(rows)
        text = result["marker_recommendation_text"]

        self.assertIn("PASS variant", text)
        self.assertIn("LowQual variant，不应优先", text)
        self.assertIn("当前 mini calling 未检出 called variant", text)
        self.assertIn("不能写成已有候选位点", text)
        self.assertIn("不是最终标记", text)

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

    def test_cli_runs_with_optional_variant_calling_evidence(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            variant_dir = _create_mock_variant_calling_dir(tmpdir_path)
            outdir = tmpdir_path / "flavonoid_marker_from_package"
            exit_code = flavonoid_markers_main(
                [
                    "--evidence-dir",
                    str(EVIDENCE_DIR),
                    "--outdir",
                    str(outdir),
                    "--variant-calling-dir",
                    str(variant_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            qa_file = outdir / "logs" / "qa_check.json"
            report_file = outdir / "reports" / "flavonoid_marker_report.md"
            candidate_file = outdir / "integration" / "flavonoid_marker_candidates.tsv"
            qa_result = json.loads(qa_file.read_text(encoding="utf-8"))
            report_text = report_file.read_text(encoding="utf-8")
            candidate_text = candidate_file.read_text(encoding="utf-8")

            self.assertIs(qa_result["passed"], True)
            self.assertIn("候选区域变异 calling 证据", report_text)
            self.assertIn("不能替代 WGS/GBS", report_text)
            self.assertIn("LowQual 位点仅作为可追溯候选记录保留", report_text)
            self.assertIn("preliminary_pass_variants_detected", report_text)
            self.assertIn("no_called_variant_in_current_mini_calling", report_text)
            self.assertNotRegex(
                report_text,
                r"Si9g04210\.1.*preliminary_pass_variants_detected",
            )
            self.assertIn("variant_evidence_status", candidate_text)
            self.assertIn("preliminary_pass_variants_detected", candidate_text)


def _create_mock_variant_calling_dir(base_dir: Path) -> Path:
    variant_dir = base_dir / "genomics_variant_calling"
    tables_dir = variant_dir / "tables"
    tables_dir.mkdir(parents=True)
    _write_tsv(
        tables_dir / "candidate_variants.tsv",
        [
            "chrom",
            "pos",
            "ref",
            "alt",
            "variant_type",
            "qual",
            "filter",
            "depth",
            "source_vcf",
            "nearest_or_target_gene",
            "marker_implication",
        ],
        [
            {
                "chrom": "chr1",
                "pos": "10",
                "ref": "A",
                "alt": "G",
                "variant_type": "SNP",
                "qual": "60",
                "filter": "PASS",
                "depth": "12",
                "source_vcf": "mock.vcf.gz",
                "nearest_or_target_gene": "Si5g31340.1",
                "marker_implication": "mock",
            },
            {
                "chrom": "chr1",
                "pos": "20",
                "ref": "C",
                "alt": "T",
                "variant_type": "SNP",
                "qual": "9",
                "filter": "LowQual",
                "depth": "5",
                "source_vcf": "mock.vcf.gz",
                "nearest_or_target_gene": "Si9g34380.1",
                "marker_implication": "mock",
            },
        ],
    )
    _write_tsv(
        tables_dir / "kasp_candidate_sites.tsv",
        ["chrom", "pos", "ref", "alt", "gene_id", "kasp_readiness", "reason"],
        [
            {
                "chrom": "chr1",
                "pos": "10",
                "ref": "A",
                "alt": "G",
                "gene_id": "Si5g31340.1",
                "kasp_readiness": "preliminary_pass",
                "reason": "mock",
            },
            {
                "chrom": "chr1",
                "pos": "20",
                "ref": "C",
                "alt": "T",
                "gene_id": "Si9g34380.1",
                "kasp_readiness": "low_quality_review_required",
                "reason": "mock",
            },
        ],
    )
    _write_tsv(
        tables_dir / "caps_candidate_sites.tsv",
        ["chrom", "pos", "ref", "alt", "gene_id", "caps_status", "reason"],
        [
            {
                "chrom": "chr1",
                "pos": "10",
                "ref": "A",
                "alt": "G",
                "gene_id": "Si5g31340.1",
                "caps_status": "pass_variant_requires_enzyme_screening",
                "reason": "mock",
            },
            {
                "chrom": "chr1",
                "pos": "20",
                "ref": "C",
                "alt": "T",
                "gene_id": "Si9g34380.1",
                "caps_status": "low_quality_variant_requires_review",
                "reason": "mock",
            },
        ],
    )
    return variant_dir


def _write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
