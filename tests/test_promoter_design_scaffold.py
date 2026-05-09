import csv
import json
import tempfile
import unittest
from pathlib import Path

from breeding_agent.cli.flavonoid_markers import main as flavonoid_markers_main
from breeding_agent.cli.promoter_design import main as promoter_design_main
from breeding_agent.modules.promoter.promoter_task_schema import PromoterDesignInput
from breeding_agent.workflows.promoter_design import (
    PromoterDesignConfig,
    run_promoter_design_task,
)


EVIDENCE_DIR = Path("outputs/flavonoid_marker_from_package/evidence")


class PromoterDesignScaffoldTest(unittest.TestCase):
    def test_promoter_design_input_can_be_constructed(self):
        design_input = PromoterDesignInput(
            gene_id="Si9g04210.1",
            gene_sequence="ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTAGC",
            gene_function="flavonoid-related candidate gene",
            species="foxtail_millet",
            target_expression_level="high",
            target_tissue_or_condition="seed",
        )

        self.assertEqual(design_input.gene_id, "Si9g04210.1")
        self.assertEqual(design_input.target_expression_level, "high")

    def test_empty_gene_sequence_fails_with_friendly_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "gene_sequence is required"):
                run_promoter_design_task(
                    PromoterDesignConfig(
                        design_input=PromoterDesignInput(
                            gene_id="Si9g04210.1",
                            gene_sequence="",
                            gene_function="flavonoid-related candidate gene",
                            species="foxtail_millet",
                            target_expression_level="high",
                        ),
                        outdir=Path(tmpdir) / "promoter_design",
                    )
                )

    def test_short_gene_sequence_cli_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = promoter_design_main(
                [
                    "--gene-id",
                    "Si9g04210.1",
                    "--gene-sequence",
                    "ATGC",
                    "--gene-function",
                    "flavonoid-related candidate gene",
                    "--species",
                    "foxtail_millet",
                    "--target-expression-level",
                    "high",
                    "--outdir",
                    str(Path(tmpdir) / "promoter_design"),
                ]
            )

        self.assertEqual(exit_code, 1)

    def test_workflow_generates_scaffold_outputs_without_fake_sequence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_promoter_design_task(
                PromoterDesignConfig(
                    design_input=PromoterDesignInput(
                        gene_id="Si9g04210.1",
                        gene_sequence="ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTAGC",
                        gene_function="flavonoid-related candidate gene",
                        species="foxtail_millet",
                        target_expression_level="high",
                        target_tissue_or_condition="seed",
                    ),
                    outdir=Path(tmpdir) / "promoter_design",
                )
            )

            report_text = result.promoter_design_report.read_text(encoding="utf-8")
            validation_text = result.promoter_validation_plan.read_text(
                encoding="utf-8"
            )
            fasta_text = result.promoter_candidates_fasta.read_text(encoding="utf-8")
            manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
            with result.promoter_candidate_table.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))

            self.assertTrue(result.promoter_design_report.exists())
            self.assertTrue(result.promoter_validation_plan.exists())
            self.assertTrue(result.manifest.exists())
        self.assertIn("not a trained promoter generator", report_text)
        self.assertIn("not a final promoter generator", report_text.lower())
        self.assertIn("Current scaffold produces no validated promoter sequence", validation_text)
        self.assertIn("intentionally contains no FASTA records", fasta_text)
        self.assertEqual(rows[0]["promoter_sequence"], "NOT_GENERATED")
        self.assertEqual(rows[0]["design_status"], "not_generated_scaffold")
        self.assertIs(manifest["generates_synthetic_promoter"], False)
        self.assertIs(manifest["trains_model"], False)

    def test_promoter_design_cli_demo_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "promoter_design_demo"
            exit_code = promoter_design_main(
                [
                    "--gene-id",
                    "Si9g04210.1",
                    "--gene-sequence",
                    "ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTAGC",
                    "--gene-function",
                    "flavonoid-related candidate gene",
                    "--species",
                    "foxtail_millet",
                    "--target-expression-level",
                    "high",
                    "--outdir",
                    str(outdir),
                ]
            )

        self.assertEqual(exit_code, 0)

    def test_existing_flavonoid_marker_cli_still_runs(self):
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
            qa_result = json.loads(
                (outdir / "logs" / "qa_check.json").read_text(encoding="utf-8")
            )

        self.assertEqual(exit_code, 0)
        self.assertIs(qa_result["passed"], True)
