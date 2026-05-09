# LangGraph 版谷子黄酮候选标记推荐 workflow

## 1. 模块定位

本模块是现有 Flavonoid Marker Recommendation 的并行 LangGraph workflow。它把当前规则化 DeepRare-like lightweight agents 包装为 LangGraph nodes，用于展示开源智能体编排框架下的多步骤分析流程。

当前仍然是规则化 agent，不调用真实大模型，不调用本地开源大模型，不调用外部 API，不接入 Deep Agents。Deep Agents 仅作为后续阶段规划。

## 2. 为什么先接 LangGraph

先接 LangGraph，而不是先接开源本地大模型，是为了先稳定 workflow 编排边界：

- 明确每个 node 的输入、输出、warning 和 limitation。
- 复用现有 rule-based agents 和 LLM-ready interface。
- 保持旧 CLI 和旧 workflow 不变。
- 保持 DOI、SNP/InDel、LowQual、KASP/CAPS preliminary screening 的安全边界。
- 为后续接入本地模型或 Deep Agents 预留结构，而不引入不可复现输出。

LangGraph 在本项目中的作用是 workflow / agent graph 编排，不是模型推理层。

## 3. 安装方式

LangGraph 是可选依赖。旧 CLI 不依赖 LangGraph。

```bash
pip install langgraph
```

如果未安装，新增 graph CLI 会提示：

```text
LangGraph is not installed. Install with: pip install langgraph
```

## 4. Graph node 设计

节点顺序：

```text
START
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
-> END
```

节点职责：

- `load_evidence_node`：检查 evidence 文件是否存在。
- `aggregate_candidates_node`：调用现有 `aggregate_flavonoid_marker_candidates()`。
- `build_agent_context_node`：调用 `build_flavonoid_agent_context()`。
- `literature_agent_node`：调用 `FlavonoidLiteratureAgent.run_with_context()`。
- `marker_recommendation_agent_node`：调用 `FlavonoidMarkerRecommendationAgent.run_with_context()`。
- `validation_agent_node`：调用 `FlavonoidValidationAgent.run_with_context()`。
- `reviewer_agent_node`：渲染 draft report，调用 `FlavonoidReviewerAgent.run_with_context()` 检查过度推断。
- `final_qa_agent_node`：调用 `FlavonoidFinalQAAgent.run_with_context()`。
- `report_node`：复用现有 Markdown report renderer。
- `write_outputs_node`：写出 QA 和 manifest 相关状态。

每个 node 都会在 `graph_trace` 中记录：

- `node_name`
- `agent_name`
- `input_summary`
- `output_summary`
- `evidence_used`
- `warnings`
- `limitations`
- `passed`

## 5. State 字段

`FlavonoidGraphState` 定义在：

```text
src/breeding_agent/graphs/state.py
```

关键字段：

- `evidence_dir`
- `outdir`
- `variant_calling_dir`
- `target_genes`
- `agent_context`
- `candidate_table_path`
- `agent_outputs`
- `reviewer_warnings`
- `qa_result`
- `report_path`
- `manifest_path`
- `graph_trace`
- `errors`
- `warnings`

State 只保存 JSON 可序列化数据，不使用 pydantic。

## 6. CLI 用法

不接 variant evidence：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph
```

接入 Genomics Candidate Variant Calling MVP：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph \
  --variant-calling-dir outputs/genomics_variant_calling
```

## 7. 输出文件

```text
outputs/flavonoid_marker_langgraph/
├── graph/
│   ├── graph_trace.json
│   ├── graph_state_final.json
│   ├── node_decision_table.tsv
│   └── langgraph_summary.md
├── integration/
│   └── flavonoid_marker_candidates.tsv
├── reports/
│   └── flavonoid_marker_report.md
├── logs/
│   └── qa_check.json
└── manifest.json
```

`node_decision_table.tsv` 字段：

- `node_id`
- `node_name`
- `agent_name`
- `input_summary`
- `output_summary`
- `evidence_used`
- `warnings`
- `limitations`
- `passed`

`langgraph_summary.md` 说明 graph 流程、node 与 agent 对应关系、variant evidence 是否接入、ReviewerAgent 如何防止过度推断、FinalQAAgent 检查结果，以及当前没有接入真实 LLM。

## 8. 与旧 workflow 的关系

旧 workflow 和旧 CLI 保持不变：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package
```

旧 CLI 的 `--variant-calling-dir` 也保持可用。LangGraph 版是并行入口，不替代旧 workflow。

## 9. 当前限制

- 不调用真实大模型。
- 不调用本地开源大模型。
- 不调用 OpenAI SDK。
- 不调用外部 API。
- 不接入 Deep Agents。
- 不伪造 DOI。
- 不伪造 SNP/InDel 位点。
- LowQual 不得作为优先推荐。
- KASP/CAPS preliminary screening 不等于最终标记。
- 当前候选区域 variant calling 不能替代 WGS/GBS 群体变异检测。

## 10. 后续规划

后续可以在已有 `AgentInput` / `AgentOutput` adapter 层接入本地开源模型或 OpenAI。Deep Agents 可作为更高层规划，但应在单独阶段接入。无论接入哪类模型，都必须保留规则 fallback，并继续通过 ReviewerAgent 和 FinalQAAgent。
