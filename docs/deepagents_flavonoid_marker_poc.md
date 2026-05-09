# Deep Agents Flavonoid Marker POC

## Purpose

This POC validates that `breeding-agent` can expose the flavonoid marker recommendation task through a Deep Agents-style harness. It is intentionally parallel to the existing rule-based workflow and the LangGraph workflow.

LangGraph remains the main graph workflow. Deep Agents is treated as a future higher-level agent harness for teacher-facing demonstrations and later experiments.

## Current Boundary

- The POC reuses the existing local evidence package, `build_flavonoid_agent_context`, `AgentInput` / `AgentOutput` compatible structures, and the existing rule-based agents.
- It does not call a real LLM.
- It does not call a local open-source model.
- It does not call external APIs.
- It does not replace the old flavonoid marker CLI.
- It does not replace the LangGraph workflow.
- Deep Agents is an optional dependency.

If `deepagents` is not installed, the CLI exits with:

```text
Deep Agents is not installed. Install according to project docs.
```

## Installation

Install Deep Agents only in an environment where optional agent-framework experiments are desired. The core project workflows do not require it.

```bash
pip install deepagents
```

## Run

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_deepagents \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_deepagents \
  --variant-calling-dir outputs/genomics_variant_calling
```

The `--variant-calling-dir` argument is optional. If it is omitted, the POC keeps the same fallback behavior as the existing marker recommendation workflow.

## Outputs

```text
outputs/flavonoid_marker_deepagents/
├── deepagents/
│   ├── deepagents_trace.json
│   ├── deepagents_summary.md
│   └── deepagents_decision_table.tsv
├── integration/
│   └── flavonoid_marker_candidates.tsv
├── reports/
│   └── flavonoid_marker_report.md
├── logs/
│   └── qa_check.json
└── manifest.json
```

`deepagents_trace.json` records the deterministic harness steps, context construction, rule-agent outputs, warnings, and limitations. `deepagents_decision_table.tsv` is a tabular view of the same decisions. `deepagents_summary.md` explains that the POC is not yet an LLM-powered agent run.

## Variant Evidence Display

When `--variant-calling-dir` is provided and the directory exists, the POC summary and decision table report:

- `variant_calling_enabled=true`
- `variant_calling_dir=<provided directory>`
- `gene_level_variant_evidence_integrated=true` when gene-level variant evidence has been passed into the marker recommendation layer
- `candidate_variant_rows`, `kasp_candidate_rows`, and `caps_candidate_rows` from the small TSV tables under `variant_calling_dir/tables/`

The POC trace does not expand raw candidate variant rows. It records the raw table row counts and states that gene-level variant evidence is used by the marker recommendation layer. PASS / LowQual interpretation remains constrained by the upstream variant calling and marker recommendation code.

The decision table intentionally shows `final_qa_agent` only once. The underlying rule workflow may check the final rendered report, but the POC display presents a single final QA decision so the flow remains easy to read.

## Evidence Rules

- Do not fabricate SNP/InDel positions.
- Do not fabricate DOI values.
- LowQual variants must not be prioritized for KASP/CAPS development.
- Preliminary KASP/CAPS screening is not a final marker, primer design, or enzyme digestion plan.
- Candidate-region variant calling does not replace WGS/GBS population variant calling.
- The final report must keep the fixed conclusion: 优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。

## Relationship To Other Workflows

- Old flavonoid marker CLI: production-compatible deterministic workflow.
- LangGraph CLI: main graph orchestration workflow for existing rule-based agents.
- Deep Agents CLI: optional POC harness for future framework integration.

The POC is useful for showing how a future Deep Agents layer could wrap the same context and agent outputs. Later work can add a local open-source model adapter or a Deep Agents planner, but that is outside the current boundary.

## Git Safety

Do not commit `data/private/` or `outputs/`. The generated POC artifacts are runtime outputs only.
