# breeding-agent

`breeding-agent` is a local, reproducible crop multi-omics breeding workflow project for foxtail millet. It is no longer only an RNA-seq DEG demo: the current project includes transcriptomics, metabolomics, genomics candidate variant calling, flavonoid marker recommendation, LLM-ready rule agents, a LangGraph multi-agent workflow, a Deep Agents POC, Gradio display pages, and a Promoter Design scaffold.

## Current Capabilities

- RNA-seq DEG reproduction workflow from local BAM/GFF inputs.
- Flavonoid marker recommendation for `Si9g04210.1`, `Si5g31340.1`, and `Si9g34380.1`, including `群体`, literature review, DOI evidence, statistical values, and SNP/InDel/KASP/CAPS recommendations.
- Transcriptomics / metabolomics / annotation / literature evidence aggregation.
- Genomics Candidate Variant Calling MVP with PASS / LowQual stratification and KASP/CAPS preliminary screening tables.
- Optional variant evidence integration into the flavonoid marker report.
- LLM-ready Agent Interface, prompt templates, and context builder. Current default agents are rule-based and do not call real LLMs.
- LangGraph workflow as the main open-source agent orchestration path for flavonoid marker recommendation.
- Deep Agents POC as a parallel harness demonstration. It does not replace LangGraph.
- Promoter Design scaffold for task definition, schema, placeholder workflow/CLI output, and dataset inventory. It is not a promoter generator.
- Gradio workbench using top-level `gr.Tab` pages.

## Boundaries

- No fabricated SNP/InDel positions.
- No fabricated DOI values.
- No fabricated promoter sequences.
- KASP/CAPS outputs are preliminary screening, not final primers or enzyme digestion plans.
- Candidate-region variant calling does not replace WGS/GBS population variant calling.
- The project currently does not run real LLM inference. ReviewerAgent + Ollama/Qwen or another local model adapter is a next-stage plan, not a completed capability.
- Promoter Design is only a scaffold. It does not train a model and does not output experimentally usable synthetic promoters.
- Do not commit `data/private/`, `outputs/`, BAM/BAI, FASTA/index files, or large intermediate data.

## Common Commands

Generate flavonoid evidence:

```bash
PYTHONPATH=src python3 scripts/demo/create_flavonoid_marker_evidence_from_package.py \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/flavonoid_marker_from_package/evidence
```

Run flavonoid marker recommendation:

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package \
  --variant-calling-dir outputs/genomics_variant_calling
```

Run Genomics Candidate Variant Calling MVP:

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.genomics_variants \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/genomics_variant_calling
```

Run the LangGraph workflow:

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph \
  --variant-calling-dir outputs/genomics_variant_calling
```

Run the Deep Agents POC:

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_deepagents \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_deepagents \
  --variant-calling-dir outputs/genomics_variant_calling
```

Run the Promoter Design scaffold:

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.promoter_design \
  --gene-id Si9g04210.1 \
  --gene-sequence ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC \
  --gene-function "flavonoid-related candidate gene" \
  --species foxtail_millet \
  --target-expression-level high \
  --outdir outputs/promoter_design_demo
```

Start Gradio:

```bash
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

## Outputs

- Flavonoid marker recommendation: `outputs/flavonoid_marker_from_package/`
- Genomics variant calling: `outputs/genomics_variant_calling/`
- LangGraph workflow: `outputs/flavonoid_marker_langgraph/`
- Deep Agents POC: `outputs/flavonoid_marker_deepagents/`
- Promoter Design scaffold: `outputs/promoter_design_demo/`

## Tests

Run the current test suite with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

The suite now covers the LLM-ready agent interface, flavonoid agent layer, variant evidence integration, Genomics Candidate Variant Calling MVP, LangGraph workflow behavior, Deep Agents POC behavior, omics modules, and Promoter Design scaffold.
