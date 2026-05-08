import gzip
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from breeding_agent.modules.genomics.variant_calling import (
    MissingToolError,
    build_variant_tables_from_vcf,
    parse_vcf_candidate_variants,
    require_tools,
)
from breeding_agent.reports.genomics_variant_report import (
    render_genomics_variant_report,
)
from breeding_agent.workflows.genomics_variant_calling import (
    GenomicsVariantCallingConfig,
    run_genomics_variant_calling_task,
)


DATASET_DIR = Path("data/private/flavonoid_marker_mini_5genes_50kb")


def _tools_available() -> bool:
    try:
        require_tools()
    except MissingToolError:
        return False
    return True


class GenomicsVariantCallingParsingTest(unittest.TestCase):
    def test_parse_vcf_candidate_variants(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            vcf_path = tmpdir_path / "test.vcf.gz"
            _write_gzip_text(
                vcf_path,
                "\n".join(
                    [
                        "##fileformat=VCFv4.2",
                        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\ts1",
                        "chr1\t10\t.\tA\tG\t60\tPASS\tDP=12\tGT:DP\t0/1:12",
                        "chr1\t20\t.\tAT\tA\t35\tPASS\tDP=8\tGT:DP\t0/1:8",
                        "",
                    ]
                ),
            )
            gene_intervals = [
                {"chrom": "chr1", "start": 1, "end": 15, "gene_id": "Si9g04210.1"}
            ]

            rows = parse_vcf_candidate_variants(
                vcf_path=vcf_path,
                gene_intervals=gene_intervals,
                region_intervals=[],
            )

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["variant_type"], "SNP")
            self.assertEqual(rows[0]["depth"], "12")
            self.assertEqual(rows[0]["nearest_or_target_gene"], "Si9g04210.1")
            self.assertEqual(rows[1]["variant_type"], "INDEL")

    def test_no_vcf_records_does_not_fabricate_candidate_variants(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            vcf_path = tmpdir_path / "empty.vcf.gz"
            tables_dir = tmpdir_path / "tables"
            _write_gzip_text(
                vcf_path,
                "\n".join(
                    [
                        "##fileformat=VCFv4.2",
                        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                        "",
                    ]
                ),
            )

            result = build_variant_tables_from_vcf(
                vcf_path=vcf_path,
                tables_dir=tables_dir,
                gff=None,
                regions_bed=None,
            )

            self.assertEqual(result["counts"]["candidate_variants"], 0)
            candidate_file = tables_dir / "candidate_variants.tsv"
            lines = candidate_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)

    def test_kasp_and_caps_tables_are_generated_from_real_vcf_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            vcf_path = tmpdir_path / "test.vcf.gz"
            tables_dir = tmpdir_path / "tables"
            _write_gzip_text(
                vcf_path,
                "\n".join(
                    [
                        "##fileformat=VCFv4.2",
                        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                        "chr1\t10\t.\tA\tG\t60\tPASS\tDP=12",
                        "chr1\t20\t.\tAT\tA\t35\tPASS\tDP=8",
                        "",
                    ]
                ),
            )

            result = build_variant_tables_from_vcf(
                vcf_path=vcf_path,
                tables_dir=tables_dir,
                gff=None,
                regions_bed=None,
            )

            self.assertEqual(result["counts"]["candidate_variants"], 2)
            self.assertEqual(result["counts"]["snps"], 1)
            self.assertEqual(result["counts"]["indels"], 1)
            self.assertIn(
                "preliminary",
                (tables_dir / "kasp_candidate_sites.tsv").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "requires_restriction_enzyme_screening",
                (tables_dir / "caps_candidate_sites.tsv").read_text(encoding="utf-8"),
            )


class GenomicsVariantCallingValidationTest(unittest.TestCase):
    def test_missing_tools_raise_clear_error(self):
        with patch(
            "breeding_agent.modules.genomics.variant_calling.shutil.which",
            return_value=None,
        ):
            with self.assertRaises(MissingToolError) as context:
                require_tools()

        self.assertIn("Install samtools and bcftools", str(context.exception))

    def test_report_contains_variant_calling_limitations(self):
        report = render_genomics_variant_report(
            {
                "inputs": {
                    "bam_dir": "dataset/bam",
                    "reference_fasta": "dataset/genome.fa",
                },
                "outputs": {"candidate_variants": "out/tables/candidate_variants.tsv"},
                "commands": [
                    {
                        "name": "bcftools call",
                        "command": "bcftools call -mv -Oz -o raw.vcf.gz mpileup.bcf",
                    }
                ],
                "counts": {
                    "candidate_variants": 0,
                    "snps": 0,
                    "indels": 0,
                    "kasp_candidate_sites": 0,
                    "caps_candidate_sites": 0,
                },
                "covered_target_genes": [],
                "warnings": [],
            }
        )

        self.assertIn("候选区域 calling", report)
        self.assertIn("不等同于 WGS 全基因组变异检测", report)
        self.assertIn("RNA-seq BAM", report)
        self.assertIn("更大群体", report)


@unittest.skipUnless(
    DATASET_DIR.exists() and _tools_available(),
    "Real calling requires local mini dataset plus samtools/bcftools.",
)
class GenomicsVariantCallingRealRunTest(unittest.TestCase):
    def test_real_candidate_region_calling_runs_when_tools_and_data_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = Path(tmpdir) / "genomics_variant_calling"
            result = run_genomics_variant_calling_task(
                GenomicsVariantCallingConfig(
                    dataset_dir=DATASET_DIR,
                    outdir=outdir,
                )
            )

            self.assertTrue((outdir / "variants" / "candidate_regions.raw.vcf.gz").exists())
            self.assertTrue(
                (outdir / "variants" / "candidate_regions.filtered.vcf.gz").exists()
            )
            self.assertTrue((outdir / "tables" / "candidate_variants.tsv").exists())
            self.assertTrue(
                (outdir / "reports" / "genomics_variant_calling_report.md").exists()
            )
            self.assertIn("counts", result)


def _write_gzip_text(path: Path, text: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(text)


if __name__ == "__main__":
    unittest.main()
