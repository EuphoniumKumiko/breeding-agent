# AGENTS.md

This repository is the `breeding-agent` project for reproducible crop multi-omics breeding workflows. The current production-quality module is a mini RNA-seq DEG workflow. The next domain task is foxtail millet flavonoid marker recommendation from a local mini data package.

## Project Scope

- Research crop: 谷子。
- Existing workflow: RNA-seq DEG reproduction and first-version transcriptomics evidence integration.
- New flavonoid marker task: 根据转录组、代谢组、基因组和功能注释数据，给出可开发标记类型建议，例如 SNP/InDel/KASP/CAPS，并说明还需要哪些验证。
- Required biological conclusion text for flavonoid marker reports and onboarding docs: 优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。

## Hard Business Requirements

- 核心输入必须按学长要求记录：
  - 转录组：`bam/` 中所有文件
  - 代谢组：`metabolome_raw_3372.tsv`
  - 基因组：`genome.fa` 和 `genome.gff`
  - 功能注释：`local_region_emapper_annotations.tsv`
- The three fixed high-priority genes are `Si9g04210.1`, `Si5g31340.1`, and `Si9g34380.1`.
- The word `群体` must appear in Chinese-facing final recommendation text.
- Each of the three gene IDs must show statistical values when producing human-facing reports.
- 文献查阅 is required for flavonoid marker recommendations. Relevant literature must show DOI values.
- Do not fabricate DOI values. Use only DOI values present in verified inputs, manually checked literature, or explicitly provided seed evidence.
- Do not fabricate SNP/InDel positions. If formal variant calling results are missing, write `variant_status=not_called`.

Current seed literature DOI values in the package-derived evidence are:

| DOI | Use |
| --- | --- |
| `10.3390/life11060578` | flavonoid biosynthesis background |
| `10.3389/fpls.2021.665530` | plant flavonoid pathway candidate interpretation |
| `10.1007/978-1-4939-0446-4_7` | flavonoid analysis / validation methods |
| `10.1134/S2079059716030114` | plant flavonoid gene evidence |

## Key Gene Statistics From Current Mini Evidence

These values are package-derived evidence, not final breeding validation.

| gene_id | baseMean | log2FC | pvalue | padj | Green_mean | Golden_mean | Direction | n_network_edges | max_abs_pearson | top_correlated_metabolite | top_pearson_r |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | ---: |
| `Si9g04210.1` | 3234.583184 | -6.542585349 | 2.5e-162 | 5.62e-158 | 6401.01352933333 | 68.1528381033333 | Higher_in_Green | 30 | 0.995767042374107 | 4,2',3',4'-Tetrahydroxychalcone* | -0.995767042374107 |
| `Si5g31340.1` | 173.0025915 | 1.574439128 | 5.86e-10 | 4.71e-07 | 86.8450925466667 | 259.1600905 | Higher_in_Golden | 30 | 0.988799901881308 | Epicatechin 3-glucoside | 0.988799901881308 |
| `Si9g34380.1` | 73.04607021 | 3.204977856 | 3.18e-17 | 8.95e-14 | 14.38107137 | 131.711069033333 | Higher_in_Golden | 30 | 0.995505738552351 | 4'-Hydroxy-5,7-dimethoxyflavanone | 0.995505738552351 |

## Important Existing Files

- RNA-seq DEG CLI: `src/breeding_agent/cli/deg.py`
- RNA-seq DEG workflow: `src/breeding_agent/workflows/rnaseq_deg.py`
- External command wrapper: `src/breeding_agent/core/command_runner.py`
- Validators: `src/breeding_agent/validators/`
- Reports: `src/breeding_agent/reports/`
- Integration: `src/breeding_agent/integration/`
- Flavonoid package evidence converter: `scripts/demo/create_flavonoid_marker_evidence_from_package.py`
- Flavonoid marker aggregation CLI: `src/breeding_agent/cli/flavonoid_markers.py`
- Flavonoid marker aggregation workflow: `src/breeding_agent/workflows/flavonoid_marker_aggregation.py`
- Flavonoid marker aggregator: `src/breeding_agent/integration/flavonoid_marker_aggregator.py`
- Flavonoid marker QA: `src/breeding_agent/integration/flavonoid_marker_qa.py`
- Flavonoid marker report: `src/breeding_agent/reports/flavonoid_marker_report.py`
- Flavonoid package import doc: `docs/flavonoid_marker_package_import.md`

## Do Not Modify Without Explicit Request

- Do not modify the existing RNA-seq DEG workflow unless the task explicitly asks for it.
- Do not modify `workflows/rnaseq_deg/R/differential_expression_limma_voom.R` unless the task explicitly asks for R workflow changes.
- Do not change `featureCounts -g Parent` behavior unless the annotation strategy is explicitly changed.
- Do not weaken validation, provenance, or reproducibility behavior.

## Where To Add Flavonoid Marker Work

Prefer these areas:

- `src/breeding_agent/integration/`
- `src/breeding_agent/reports/`
- `src/breeding_agent/workflows/`
- `src/breeding_agent/cli/`
- `scripts/demo/`
- `docs/`

Do not put flavonoid marker aggregation logic inside the RNA-seq DEG workflow.

## Data And Git Safety

Never commit or intentionally stage:

- `data/private/`
- `outputs/`
- BAM files: `*.bam`, `*.bai`
- FASTA files and indexes: `*.fa`, `*.fasta`, `*.fa.gz`, `*.fai`, `*.gzi`
- large metabolome/genome/intermediate data files

The current `.gitignore` may not protect every private data path. Always inspect `git status --short` before staging anything.

## Implemented Commands

Generate flavonoid marker package evidence:

```bash
PYTHONPATH=src python3 scripts/demo/create_flavonoid_marker_evidence_from_package.py \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/flavonoid_marker_from_package/evidence
```

Run the existing RNA-seq DEG CLI:

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.deg \
  --bam-dir data/private/flavonoid_marker_mini_5genes_50kb/bam \
  --gff data/private/flavonoid_marker_mini_5genes_50kb/genome.original_coords.gff \
  --trait 黄酮 \
  --threads 4
```

Run the implemented flavonoid marker aggregation CLI:

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package
```

Expected aggregation outputs:

```text
outputs/flavonoid_marker_from_package/
├── integration/
│   └── flavonoid_marker_candidates.tsv
├── reports/
│   └── flavonoid_marker_report.md
├── logs/
│   └── qa_check.json
└── manifest.json
```

Check the QA result:

```bash
cat outputs/flavonoid_marker_from_package/logs/qa_check.json
```

Current flavonoid marker aggregation limits:

- It is a rule-based/template workflow; it does not call external APIs, Deep Agents, or LangGraph.
- It reads DOI values from `literature_evidence.tsv` and must not fabricate DOI values.
- If `genome_variant_evidence.tsv` has `variant_status=not_called`, the report must state that the mini package does not provide final SNP/InDel positions.
- Do not fabricate SNP/InDel positions. Recommend follow-up candidate-region SNP/InDel calling from BAM plus `genome.fa/genome.gff` or `genome.bam_compatible.fa.gz` with `genome.original_coords.gff`, then screen KASP/CAPS-convertible loci.

## Required Checks After Codex Changes

After each Codex change, run:

```bash
git status --short
git diff --stat
python3 -m py_compile <changed_python_files>
```

If only Markdown files changed, state that `py_compile` is not applicable because no Python files changed.
