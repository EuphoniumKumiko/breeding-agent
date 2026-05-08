import unittest

from breeding_agent.integration.flavonoid_marker_qa import (
    check_flavonoid_marker_report,
)


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


class FlavonoidMarkerQaTest(unittest.TestCase):
    def test_complete_report_passes_qa(self):
        result = check_flavonoid_marker_report(COMPLETE_REPORT)

        self.assertIs(result["passed"], True)
        self.assertEqual(result["missing_items"], [])

    def test_missing_gene_fails_qa(self):
        report = COMPLETE_REPORT.replace("Si5g31340.1", "missing_gene")
        result = check_flavonoid_marker_report(report)

        self.assertIs(result["passed"], False)
        self.assertIn("missing gene: Si5g31340.1", result["missing_items"])

    def test_missing_population_term_fails_qa(self):
        report = COMPLETE_REPORT.replace("群体", "材料")
        result = check_flavonoid_marker_report(report)

        self.assertIs(result["passed"], False)
        self.assertIn("missing term: 群体", result["missing_items"])

    def test_missing_doi_fails_qa(self):
        report = COMPLETE_REPORT.replace("10.3390/life11060578", "no-doi")
        result = check_flavonoid_marker_report(report)

        self.assertIs(result["passed"], False)
        self.assertIn("missing DOI value", result["missing_items"])

    def test_missing_statistics_fails_qa(self):
        report = """
# 测试报告
文献查阅过程展示 DOI 10.3390/life11060578。
群体验证需要 SNP、InDel、KASP、CAPS。
Si9g04210.1
Si5g31340.1
Si9g34380.1
"""
        result = check_flavonoid_marker_report(report)

        self.assertIs(result["passed"], False)
        self.assertIn(
            "missing statistics for gene: Si9g04210.1",
            result["missing_items"],
        )

    def test_variant_calling_optional_limitations_are_checked(self):
        report = (
            COMPLETE_REPORT
            + "\n## 候选区域变异 calling 证据\n"
            + "LowQual 位点仅作为可追溯候选记录保留，不应直接优先用于 KASP/CAPS 开发。\n"
            + "KASP/CAPS 表只是 preliminary screening，不是最终引物或酶切方案。\n"
            + "该结果不能替代 WGS/GBS 群体变异检测。\n"
        )
        result = check_flavonoid_marker_report(report)

        self.assertIs(result["passed"], True)
        self.assertEqual(result["optional_variant_checks"], [])

    def test_variant_calling_missing_limitations_fails_optional_qa(self):
        report = (
            COMPLETE_REPORT
            + "\n## 候选区域变异 calling 证据\n"
            + "LowQual variant and preliminary KASP screening are shown.\n"
        )
        result = check_flavonoid_marker_report(report)

        self.assertIs(result["passed"], False)
        self.assertIn(
            "missing LowQual non-prioritization statement",
            result["missing_items"],
        )
        self.assertIn(
            "missing preliminary KASP/CAPS limitation statement",
            result["missing_items"],
        )
        self.assertIn(
            "missing WGS/GBS limitation statement",
            result["missing_items"],
        )


if __name__ == "__main__":
    unittest.main()
