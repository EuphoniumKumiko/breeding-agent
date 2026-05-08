import csv
import tempfile
import unittest
from pathlib import Path

from breeding_agent.integration.flavonoid_variant_evidence import (
    load_flavonoid_variant_evidence,
)


class FlavonoidVariantEvidenceTest(unittest.TestCase):
    def test_missing_variant_calling_dir_returns_warning_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_flavonoid_variant_evidence(Path(tmpdir) / "missing")

            self.assertIs(result.loaded, False)
            self.assertTrue(result.warnings)
            self.assertTrue(
                all(
                    row["variant_evidence_status"]
                    == "variant_calling_output_missing"
                    for row in result.rows
                )
            )

    def test_mock_variant_tables_are_grouped_by_target_gene(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            variant_dir = Path(tmpdir) / "genomics_variant_calling"
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
                        "ref": "AT",
                        "alt": "A",
                        "variant_type": "INDEL",
                        "qual": "8",
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
                    },
                    {
                        "chrom": "chr1",
                        "pos": "20",
                        "ref": "AT",
                        "alt": "A",
                        "gene_id": "Si9g34380.1",
                        "caps_status": "low_quality_variant_requires_review",
                        "reason": "mock",
                    },
                ],
            )

            result = load_flavonoid_variant_evidence(variant_dir)
            rows = {row["gene_id"]: row for row in result.rows}

            self.assertIs(result.loaded, True)
            self.assertEqual(
                rows["Si5g31340.1"]["variant_evidence_status"],
                "preliminary_pass_variants_detected",
            )
            self.assertEqual(rows["Si5g31340.1"]["pass_variants"], "1")
            self.assertEqual(rows["Si5g31340.1"]["pass_snp_count"], "1")
            self.assertEqual(
                rows["Si5g31340.1"]["kasp_preliminary_pass_count"],
                "1",
            )
            self.assertEqual(
                rows["Si9g04210.1"]["variant_evidence_status"],
                "no_called_variant_in_current_mini_calling",
            )
            self.assertEqual(
                rows["Si9g34380.1"]["variant_evidence_status"],
                "only_low_quality_variants_detected",
            )


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
