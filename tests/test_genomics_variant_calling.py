import csv
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

    def test_kasp_and_caps_tables_are_quality_stratified_from_real_vcf_records(self):
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
                        "chr1\t11\t.\tC\tT\t10\tLowQual\tDP=6",
                        "chr1\t20\t.\tAT\tA\t35\tPASS\tDP=8",
                        "chr1\t21\t.\tG\tGA\t5\tLowQual\tDP=4",
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

            self.assertEqual(result["counts"]["candidate_variants"], 4)
            self.assertEqual(result["counts"]["snps"], 2)
            self.assertEqual(result["counts"]["indels"], 2)
            self.assertEqual(result["counts"]["pass_variants"], 2)
            self.assertEqual(result["counts"]["lowqual_variants"], 2)
            self.assertEqual(result["counts"]["pass_snps"], 1)
            self.assertEqual(result["counts"]["lowqual_snps"], 1)
            self.assertEqual(result["counts"]["pass_indels"], 1)
            self.assertEqual(result["counts"]["lowqual_indels"], 1)

            kasp_rows = _read_tsv(tables_dir / "kasp_candidate_sites.tsv")
            kasp_by_pos = {row["pos"]: row for row in kasp_rows}
            self.assertEqual(
                kasp_by_pos["10"]["kasp_readiness"],
                "preliminary_pass",
            )
            self.assertEqual(
                kasp_by_pos["11"]["kasp_readiness"],
                "low_quality_review_required",
            )

            caps_rows = _read_tsv(tables_dir / "caps_candidate_sites.tsv")
            caps_by_pos = {row["pos"]: row for row in caps_rows}
            self.assertEqual(
                caps_by_pos["10"]["caps_status"],
                "pass_variant_requires_enzyme_screening",
            )
            self.assertEqual(
                caps_by_pos["11"]["caps_status"],
                "low_quality_variant_requires_review",
            )
            self.assertEqual(
                caps_by_pos["20"]["caps_status"],
                "pass_variant_requires_enzyme_screening",
            )
            self.assertEqual(
                caps_by_pos["21"]["caps_status"],
                "low_quality_variant_requires_review",
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
                    "pass_variants": 0,
                    "lowqual_variants": 0,
                    "pass_snps": 0,
                    "lowqual_snps": 0,
                    "pass_indels": 0,
                    "lowqual_indels": 0,
                    "kasp_preliminary_pass": 0,
                    "kasp_low_quality_review_required": 0,
                    "caps_pass_variant_requires_enzyme_screening": 0,
                    "caps_low_quality_variant_requires_review": 0,
                },
                "covered_target_genes": [],
                "warnings": [],
            }
        )

        self.assertIn("Variant Quality Summary", report)
        self.assertIn("PASS variants are prioritized", report)
        self.assertIn("LowQual variants are retained for traceability", report)
        self.assertIn("KASP/CAPS tables are preliminary screening outputs", report)
        self.assertIn("PASS 位点可优先进入后续标记开发复核", report)
        self.assertIn("LowQual 位点仅作为可追溯候选记录保留", report)
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


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


if __name__ == "__main__":
    unittest.main()
