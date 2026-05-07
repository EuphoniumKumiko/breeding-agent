# Transcriptomics DEG Skill

## Purpose

This Skill defines the laboratory-standard RNA-seq DEG workflow for the Agri Multi-omics Breeding Agent project.

Use this Skill to convert RNA-seq BAM/GFF inputs into DEG result tables, reports, logs, manifests, and standardized transcriptomics evidence for downstream multi-omics integration.

This Skill is not the full breeding agent. It is the Transcriptomics DEG Module / skill inside the larger multi-omics breeding agent demo.

## Inputs

- BAM directory
- GFF annotation file
- trait
- optional_file
- threads

Expected runtime inputs are provided through the CLI or Gradio page. The end user should normally only see biological/demo-level inputs such as BAM directory, GFF annotation, trait, optional_file, and threads.

Do not expose low-level workflow defaults such as `prefix`, `contrast`, or `outdir` to final demo users unless the user explicitly asks for advanced controls.

## Fixed Tools

- `featureCounts`
- `Rscript`
- `limma-voom`

The workflow should call deterministic scientific tools. Do not ask the LLM to generate a new DEG script during normal execution.

## Fixed Rules

1. `featureCounts` parameters are fixed:

```bash
featureCounts -T {threads} -p -t exon -g Parent
```

The `-g Parent` parameter is required for the current GFF structure. Do not change it to `gene_id`, `ID`, or another attribute unless the user explicitly requests a different annotation strategy.

2. `Rscript` must use named parameters:

```bash
Rscript workflows/rnaseq_deg/R/differential_expression_limma_voom.R \
  --counts {counts_file} \
  --outdir {de_dir} \
  --prefix {prefix} \
  --contrast {contrast} \
  --fdr 0.05 \
  --lfc 1 \
  --min-count 10 \
  --min-samples 3
```

Required named parameters:

- `--counts`
- `--outdir`
- `--prefix`
- `--contrast`
- `--fdr`
- `--lfc`
- `--min-count`
- `--min-samples`

Do not rewrite these as positional parameters.

3. Do not modify `workflows/rnaseq_deg/R/differential_expression_limma_voom.R` unless the user explicitly asks for R workflow changes.

4. For `contrast=JM-LM`:

- `logFC < 0` means LM higher expression.
- `logFC > 0` means JM higher expression.

This interpretation must be preserved in reports, standardized evidence, and recommendation text.

## Outputs

The workflow should generate or preserve these outputs:

- `gene_counts_mini.txt`
- `JM_vs_LM.mini.significant_genes.tsv`
- `report.md`
- `run.log`
- `manifest.json`
- `standardized_evidence.tsv`
- `recommendation_report.md`

Expected default locations:

- `{outdir}/counts/gene_counts_mini.txt`
- `{outdir}/mini_de/JM_vs_LM.mini.significant_genes.tsv`
- `{outdir}/reports/report.md`
- `{outdir}/logs/run.log`
- `{outdir}/manifest.json`
- `{outdir}/integration/standardized_evidence.tsv`
- `{outdir}/integration/recommendation_report.md`

## Benchmark

Target benchmark gene:

```text
Si9g04210.1
```

For the current JM-LM benchmark, this gene is expected to appear as a transcriptomics candidate. If `logFC < 0`, explain that LM has higher expression than JM.

The benchmark explanation should remain conservative: this is candidate DEG evidence, not a final breeding recommendation.

## Common Mistakes

- Forgetting `PYTHONPATH=src` when running CLI, py_compile, or Gradio commands.
- Writing `Rscript` inputs as positional parameters instead of named parameters.
- Exposing `prefix`, `contrast`, or `outdir` to final demo users.
- Calling the DEG Module a complete multi-omics intelligent agent. It is only the first working skill/module.
- Modifying `featureCounts -g Parent`.
- Letting HTTP proxy variables affect Gradio localhost startup. If localhost cannot be reached, try clearing proxy variables for the launch command.

Example proxy-safe launch:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  PYTHONPATH=src python3 src/breeding_agent/web/gradio_app.py
```

## Test Commands

Compile check:

```bash
PYTHONPATH=src python3 -m py_compile \
  src/breeding_agent/workflows/rnaseq_deg.py \
  src/breeding_agent/cli/deg.py \
  src/breeding_agent/web/gradio_app.py \
  src/breeding_agent/integration/evidence_schema.py \
  src/breeding_agent/integration/transcriptomics_standardizer.py \
  src/breeding_agent/integration/recommendation_report.py
```

CLI workflow test:

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.deg \
  --bam-dir /home/li/projects/TG5_101_mini_deg_50kb_reproduction_package/mini_deg_pipeline/bam \
  --gff /home/li/projects/TG5_101_mini_deg_50kb_reproduction_package/mini_deg_pipeline/genome.original_coords.gff \
  --trait 高产 \
  --threads 4
```

Gradio test:

```bash
PYTHONPATH=src python3 src/breeding_agent/web/gradio_app.py
```

Gradio proxy-safe test:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  PYTHONPATH=src python3 src/breeding_agent/web/gradio_app.py
```

Expected demo artifacts after a successful run:

```text
outputs/gradio_demo_run/mini_de/JM_vs_LM.mini.significant_genes.tsv
outputs/gradio_demo_run/reports/report.md
outputs/gradio_demo_run/manifest.json
outputs/gradio_demo_run/logs/run.log
outputs/gradio_demo_run/integration/standardized_evidence.tsv
outputs/gradio_demo_run/integration/recommendation_report.md
```

