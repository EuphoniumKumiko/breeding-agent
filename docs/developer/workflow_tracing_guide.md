# Workflow 调用链追踪指南

适用读者：需要从 CLI、LangGraph、Deep Agents、Gradio 追踪到最终报告的新同学。  
阅读目标：明确每条主链路的入口、关键函数、输出文件和安全边界。

## 1. 普通黄酮候选标记推荐

命令：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package \
  --variant-calling-dir outputs/genomics_variant_calling
```

调用链：

```text
cli/flavonoid_markers.py
-> FlavonoidMarkerAggregationConfig
-> workflows/flavonoid_marker_aggregation.py
-> FlavonoidCentralHost.run()
-> integration/flavonoid_marker_aggregator.py
-> agents/context_builder.py
-> LiteratureAgent
-> MarkerRecommendationAgent
-> ValidationAgent
-> ReviewerAgent
-> FinalQAAgent
-> reports/flavonoid_marker_report.py
-> integration/flavonoid_marker_qa.py
-> qa_check.json + manifest.json
```

主要输入：

- `transcriptome_evidence.tsv`
- `metabolome_evidence.tsv`
- `annotation_evidence.tsv`
- `genome_variant_evidence.tsv`
- `literature_evidence.tsv`
- 可选 `outputs/genomics_variant_calling/tables/*.tsv`

主要输出：

```text
outputs/flavonoid_marker_from_package/
├── integration/flavonoid_marker_candidates.tsv
├── reports/flavonoid_marker_report.md
├── logs/qa_check.json
└── manifest.json
```

边界：普通 workflow 是规则化实现，不调用 LLM；不伪造 DOI、不伪造 SNP/InDel；LowQual 不直接优先推荐。

## 2. LangGraph 黄酮候选标记推荐

命令：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph \
  --variant-calling-dir outputs/genomics_variant_calling
```

调用链：

```text
cli/flavonoid_markers_graph.py
-> FlavonoidMarkerLangGraphConfig
-> workflows/flavonoid_marker_langgraph.py
-> initial_graph_state()
-> build_flavonoid_marker_graph()
-> load_evidence_node
-> aggregate_candidates_node
-> build_agent_context_node
-> literature_agent_node
-> marker_recommendation_agent_node
-> validation_agent_node
-> reviewer_agent_node
-> final_qa_agent_node
-> report_node
-> write_outputs_node
-> reports/langgraph_trace_report.py
```

主要输出：

```text
outputs/flavonoid_marker_langgraph/
├── graph/graph_trace.json
├── graph/graph_state_final.json
├── graph/node_decision_table.tsv
├── graph/langgraph_summary.md
├── integration/flavonoid_marker_candidates.tsv
├── reports/flavonoid_marker_report.md
├── logs/qa_check.json
└── manifest.json
```

LangGraph 的作用是编排，不是模型推理。未安装 `langgraph` 时，该 CLI 应给出清晰提示，不影响旧 CLI。

## 3. LangGraph + 本地 LLM Reviewer

命令：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_llm_real \
  --variant-calling-dir outputs/genomics_variant_calling \
  --use-llm-reviewer \
  --llm-config configs/llm.local.yaml
```

调用链：

```text
CLI args
-> workflow config: use_llm_reviewer=True, llm_config=...
-> graph state / agent_context
-> reviewer_agent_node
-> rule ReviewerAgent first
-> llm/executor.py
-> llm/openai_compatible_adapter.py
-> LM Studio / Qwen3.5-9B
-> llm/output_guard.py
-> ReviewerAgent merges guarded review
-> FinalQAAgent
-> graph_trace / node_decision_table / qa_check.json
```

当前真实运行状态已验证：

- `llm_reviewer_enabled=true`
- `llm_used=true`
- `fallback_used=false`
- `model=qwen/qwen3.5-9b`
- `guard_passed=true`
- `qa_check.json passed=true`

fallback 情况：

- 配置未启用：`llm_config_disabled`
- 本地服务不可达：`llm_request_failed...`
- 返回空内容：`empty_final_content`
- guard 不通过：`guard_failed...`

边界：LLM 只增强 ReviewerAgent，不直接生成 SNP/InDel/KASP/CAPS 结论。输出仍要经过 output_guard 和 FinalQAAgent。

## 4. Deep Agents POC

命令：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_deepagents \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_deepagents \
  --variant-calling-dir outputs/genomics_variant_calling
```

调用链：

```text
cli/flavonoid_markers_deepagents.py
-> workflows/flavonoid_marker_deepagents.py
-> deepagents/flavonoid_deepagents_poc.py
-> context_builder
-> rule agents
-> report / qa / manifest
```

Deep Agents POC 是并行 harness 验证，不替代 LangGraph 主线，不调用真实 LLM。

## 5. Genomics Candidate Variant Calling MVP

命令：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.genomics_variants \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/genomics_variant_calling
```

调用链：

```text
cli/genomics_variants.py
-> workflows/genomics_variant_calling.py
-> modules/genomics/variant_calling.py
-> reports/genomics_variant_report.py
```

输出包括：

- `candidate_variants.tsv`
- `snp_candidates.tsv`
- `indel_candidates.tsv`
- `kasp_candidate_sites.tsv`
- `caps_candidate_sites.tsv`
- `PASS / LowQual` 统计

边界：当前结果不能替代 WGS/GBS 群体变异检测；KASP/CAPS 只是 preliminary screening。

## 6. Promoter Design scaffold

命令：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.promoter_design \
  --gene-id Si9g04210.1 \
  --gene-sequence ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC \
  --gene-function "flavonoid-related candidate gene" \
  --species foxtail_millet \
  --target-expression-level high \
  --outdir outputs/promoter_design_demo
```

调用链：

```text
cli/promoter_design.py
-> workflows/promoter_design.py
-> modules/promoter/promoter_task_schema.py
-> promoter_candidate_table.tsv
-> promoter_design_report.md
-> promoter_validation_plan.md
-> manifest.json
```

边界：当前只是 scaffold，不训练模型、不调用真实 LLM、不生成真实启动子序列。

## 7. Gradio 触发链

Gradio 入口：

```bash
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

Gradio 只做：

- 调用已有 workflow。
- 读取已有 output 文件。
- 展示表格、Markdown、JSON、run log。

Gradio 不应该承载核心业务逻辑；核心逻辑仍应在 `workflows/`、`modules/`、`integration/`、`agents/`、`graphs/` 中。
