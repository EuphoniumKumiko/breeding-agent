import csv
import tempfile
import unittest
from pathlib import Path

from breeding_agent.workflows.genomics_region import (
    GenomicsRegionConfig,
    run_genomics_region_task,
)
from breeding_agent.workflows.metabolomics_evidence import (
    MetabolomicsEvidenceConfig,
    run_metabolomics_evidence_task,
)


DATASET_DIR = Path("data/private/flavonoid_marker_mini_5genes_50kb")
TARGET_GENES = {"Si9g04210.1", "Si5g31340.1", "Si9g34380.1"}


@unittest.skipUnless(DATASET_DIR.exists(), f"Missing dataset dir: {DATASET_DIR}")
class OmicsModulesWithPackageTest(unittest.TestCase):
    def test_metabolomics_workflow_generates_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "metabolomics_run"
            result = run_metabolomics_evidence_task(
                MetabolomicsEvidenceConfig(
                    dataset_dir=DATASET_DIR,
                    outdir=outdir,
                )
            )
            output_dir = outdir / "metabolomics"

            self.assertEqual(result["warnings"], [])
            self.assertTrue((output_dir / "candidate_metabolites.tsv").exists())
            self.assertTrue(
                (
                    output_dir / "flavonoid_related_significant_metabolites.tsv"
                ).exists()
            )
            self.assertTrue(
                (output_dir / "target_gene_metabolite_network_edges.tsv").exists()
            )
            self.assertTrue((output_dir / "target_gene_spls_coefficients.tsv").exists())
            self.assertTrue((output_dir / "metabolomics_report.md").exists())
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_genomics_workflow_generates_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "genomics_run"
            result = run_genomics_region_task(
                GenomicsRegionConfig(
                    dataset_dir=DATASET_DIR,
                    outdir=outdir,
                )
            )
            output_dir = outdir / "genomics"

            self.assertEqual(result["warnings"], [])
            self.assertTrue((output_dir / "target_gene_regions.tsv").exists())
            self.assertTrue((output_dir / "annotation_summary.tsv").exists())
            self.assertTrue((output_dir / "marker_readiness.tsv").exists())
            self.assertTrue((output_dir / "genomics_report.md").exists())
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_genomics_marker_readiness_contains_fixed_genes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "genomics_run"
            run_genomics_region_task(
                GenomicsRegionConfig(
                    dataset_dir=DATASET_DIR,
                    outdir=outdir,
                )
            )
            rows = _read_tsv(outdir / "genomics" / "marker_readiness.tsv")
            genes = {row["gene_id"] for row in rows}

            self.assertTrue(TARGET_GENES.issubset(genes))

    def test_genomics_marker_readiness_variant_status_is_not_called(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "genomics_run"
            run_genomics_region_task(
                GenomicsRegionConfig(
                    dataset_dir=DATASET_DIR,
                    outdir=outdir,
                )
            )
            rows = _read_tsv(outdir / "genomics" / "marker_readiness.tsv")
            fixed_gene_rows = [row for row in rows if row["gene_id"] in TARGET_GENES]

            self.assertEqual(len(fixed_gene_rows), 3)
            self.assertTrue(
                all(row["variant_status"] == "not_called" for row in fixed_gene_rows)
            )


class OmicsModulesMissingInputsTest(unittest.TestCase):
    def test_metabolomics_missing_optional_files_return_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "dataset"
            outdir = Path(tmpdir) / "out"
            dataset_dir.mkdir()

            result = run_metabolomics_evidence_task(
                MetabolomicsEvidenceConfig(dataset_dir=dataset_dir, outdir=outdir)
            )

            self.assertGreater(len(result["warnings"]), 0)
            self.assertTrue(
                (outdir / "metabolomics" / "candidate_metabolites.tsv").exists()
            )
            self.assertTrue((outdir / "metabolomics" / "manifest.json").exists())

    def test_genomics_missing_optional_files_return_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = Path(tmpdir) / "dataset"
            outdir = Path(tmpdir) / "out"
            dataset_dir.mkdir()

            result = run_genomics_region_task(
                GenomicsRegionConfig(dataset_dir=dataset_dir, outdir=outdir)
            )
            marker_rows = _read_tsv(outdir / "genomics" / "marker_readiness.tsv")

            self.assertGreater(len(result["warnings"]), 0)
            self.assertTrue((outdir / "genomics" / "manifest.json").exists())
            self.assertTrue(TARGET_GENES.issubset({row["gene_id"] for row in marker_rows}))
            self.assertTrue(
                all(row["variant_status"] == "not_called" for row in marker_rows)
            )


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


if __name__ == "__main__":
    unittest.main()
