import csv
import tempfile
import unittest
from pathlib import Path

from breeding_agent.agents.base import AgentOutput
from breeding_agent.agents.context_builder import build_flavonoid_agent_context
from breeding_agent.agents.flavonoid_final_qa_agent import FlavonoidFinalQAAgent
from breeding_agent.agents.flavonoid_literature_agent import (
    FlavonoidLiteratureAgent,
)
from breeding_agent.agents.flavonoid_marker_recommendation_agent import (
    FlavonoidMarkerRecommendationAgent,
)
from breeding_agent.agents.flavonoid_reviewer_agent import FlavonoidReviewerAgent
from breeding_agent.agents.flavonoid_validation_agent import (
    FlavonoidValidationAgent,
)
from breeding_agent.agents.prompt_templates import PROMPT_TEMPLATES


EVIDENCE_DIR = Path("outputs/flavonoid_marker_from_package/evidence")


class AgentInterfaceTest(unittest.TestCase):
    def test_context_builder_collects_all_evidence_types(self):
        self.assertTrue(EVIDENCE_DIR.exists(), f"Missing evidence dir: {EVIDENCE_DIR}")
        with tempfile.TemporaryDirectory() as tmpdir:
            variant_dir = _create_mock_variant_calling_dir(Path(tmpdir))
            context = build_flavonoid_agent_context(
                evidence_dir=EVIDENCE_DIR,
                candidate_rows=[
                    {
                        "gene_id": "Si5g31340.1",
                        "variant_evidence_status": "preliminary_pass_variants_detected",
                    }
                ],
                variant_calling_dir=variant_dir,
            )

        self.assertIn("transcriptomics_evidence", context)
        self.assertIn("metabolomics_evidence", context)
        self.assertIn("annotation_evidence", context)
        self.assertIn("literature_evidence", context)
        self.assertIn("genome_variant_evidence", context)
        self.assertIn("variant_calling_evidence", context)
        self.assertTrue(context["transcriptomics_evidence"])
        self.assertTrue(context["metabolomics_evidence"])
        self.assertTrue(context["annotation_evidence"])
        self.assertTrue(context["literature_evidence"])
        self.assertTrue(context["variant_calling_evidence"])
        self.assertIn("Si5g31340.1", context["evidence_by_gene"])

    def test_agents_return_agent_output_with_context(self):
        candidate_rows = [
            {
                "gene_id": "Si9g04210.1",
                "baseMean": "3234.583184",
                "log2FC": "-6.542585349",
                "pvalue": "2.5e-162",
                "padj": "5.62e-158",
                "variant_status": "not_called",
                "variant_evidence_status": "no_called_variant_in_current_mini_calling",
            }
        ]
        context = build_flavonoid_agent_context(
            evidence_dir=EVIDENCE_DIR,
            candidate_rows=candidate_rows,
        )

        literature_output = FlavonoidLiteratureAgent(EVIDENCE_DIR).run_with_context(
            context
        )
        marker_output = FlavonoidMarkerRecommendationAgent().run_with_context(context)
        validation_output = FlavonoidValidationAgent().run_with_context(context)
        reviewer_output = FlavonoidReviewerAgent().run_with_context(
            {
                **context,
                "literature_review_text": literature_output.structured_payload[
                    "literature_review_text"
                ],
                "marker_recommendation_text": marker_output.structured_payload[
                    "marker_recommendation_text"
                ],
                "validation_plan_text": validation_output.structured_payload[
                    "validation_plan_text"
                ],
                "report_text": "文献查阅 DOI 10.3390/life11060578 SNP InDel KASP CAPS 群体",
            }
        )
        qa_output = FlavonoidFinalQAAgent().run_with_context(
            {
                **context,
                "report_text": (
                    "文献查阅 DOI 10.3390/life11060578 SNP InDel KASP CAPS 群体 "
                    "Si9g04210.1 baseMean log2FC pvalue padj 1 2 3 4 "
                    "Si5g31340.1 baseMean log2FC pvalue padj 1 2 3 4 "
                    "Si9g34380.1 baseMean log2FC pvalue padj 1 2 3 4"
                ),
            }
        )

        for output in [
            literature_output,
            marker_output,
            validation_output,
            reviewer_output,
            qa_output,
        ]:
            self.assertIsInstance(output, AgentOutput)
            self.assertTrue(output.agent_name)
            self.assertIn("structured_payload", output.to_dict())

    def test_legacy_run_outputs_include_agent_output(self):
        literature_result = FlavonoidLiteratureAgent(EVIDENCE_DIR).run()
        marker_result = FlavonoidMarkerRecommendationAgent().run(
            [{"gene_id": "Si9g04210.1", "variant_status": "not_called"}]
        )
        validation_result = FlavonoidValidationAgent().run(
            [{"gene_id": "Si9g04210.1"}]
        )
        qa_result = FlavonoidFinalQAAgent().run(
            "文献查阅 DOI 10.3390/life11060578 SNP InDel KASP CAPS 群体"
        )

        for result in [literature_result, marker_result, validation_result, qa_result]:
            self.assertIn("agent_output", result)
            self.assertIn("agent_name", result["agent_output"])

    def test_prompt_templates_include_safety_constraints(self):
        combined = "\n".join(PROMPT_TEMPLATES.values())
        for phrase in [
            "不伪造 SNP/InDel",
            "不伪造 DOI",
            "LowQual 不得优先推荐",
            "不能替代 WGS/GBS",
            "preliminary KASP/CAPS 不等于最终标记",
            "学长硬性要求",
        ]:
            self.assertIn(phrase, combined)


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
            }
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
            }
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
            }
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
