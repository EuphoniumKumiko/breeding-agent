import json
import tempfile
import unittest
from pathlib import Path

from breeding_agent.literature.query_builder import build_literature_query_plan
from breeding_agent.literature.query_plan import write_literature_query_plan


class LiteratureQueryPlanTest(unittest.TestCase):
    def test_query_plan_is_deduplicated_and_contains_required_terms(self) -> None:
        plan = build_literature_query_plan(_context_with_duplicate_rows())
        queries = [row.query for row in plan]
        joined = " ".join(queries)

        self.assertLessEqual(len(plan), 20)
        self.assertEqual(len(queries), len({query.lower() for query in queries}))
        for gene_id in ["Si9g04210.1", "Si5g31340.1", "Si9g34380.1"]:
            self.assertIn(gene_id, joined)
        for term in ["Setaria italica", "foxtail millet", "millet"]:
            self.assertIn(term, joined)
        for term in ["flavonoid", "biosynthesis", "SNP", "InDel", "KASP", "CAPS", "marker", "breeding"]:
            self.assertIn(term, joined)

    def test_query_plan_writer_outputs_jsonl_and_tsv_offline(self) -> None:
        plan = build_literature_query_plan(_context_with_duplicate_rows())
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_literature_query_plan(outdir=Path(tmpdir), query_plan=plan)
            jsonl_path = paths["jsonl"]
            tsv_path = paths["tsv"]

            self.assertTrue(jsonl_path.exists())
            self.assertTrue(tsv_path.exists())
            jsonl_rows = [
                json.loads(line)
                for line in jsonl_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            tsv_text = tsv_path.read_text(encoding="utf-8")

        self.assertEqual(len(jsonl_rows), len(plan))
        self.assertEqual(jsonl_rows[0]["query_id"], "Q001")
        self.assertIn("query_id\tquery\tcrop\ttrait\tgene_id\tquery_type\tkeywords\tsource_terms", tsv_text)
        self.assertIn("Setaria italica flavonoid biosynthesis", tsv_text)


def _context_with_duplicate_rows() -> dict[str, object]:
    return {
        "candidate_rows": [
            {
                "gene_id": "Si9g04210.1",
                "function_annotation": "Belongs to the chalcone isomerase family",
                "PFAMs": "Chalcone",
                "top_correlated_metabolite": "4,2',3',4'-Tetrahydroxychalcone*",
            },
            {
                "gene_id": "Si5g31340.1",
                "function_annotation": "Belongs to the UDP-glycosyltransferase family",
                "PFAMs": "UDPGT",
                "top_correlated_metabolite": "Epicatechin 3-glucoside",
            },
            {
                "gene_id": "Si9g34380.1",
                "function_annotation": "Belongs to the GST superfamily",
                "PFAMs": "GST_C,GST_C_2,GST_N",
                "top_correlated_metabolite": "4'-Hydroxy-5,7-dimethoxyflavanone",
            },
            {
                "gene_id": "Si9g34380.1",
                "function_annotation": "Belongs to the GST superfamily",
            },
        ],
        "annotation_evidence": [
            {
                "gene_id": "Si9g04210.1",
                "Description": "Belongs to the chalcone isomerase family",
            }
        ],
        "metabolomics_evidence": [
            {
                "gene_id": "Si9g04210.1",
                "top_spls_metabolite": "2-(4-hydroxyphenyl)-2H-chromene-3,5,7-triol",
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
