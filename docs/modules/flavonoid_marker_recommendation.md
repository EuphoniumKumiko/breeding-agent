# Flavonoid Marker Recommendation 模块导读

适用读者：维护黄酮候选标记推荐、LangGraph、Deep Agents POC 或本地 LLM Reviewer 的同学。  
阅读目标：理解该模块的业务职责、输入输出、Agent 边界、variant evidence 和 LLM Reviewer 状态。

## 1. 模块作用

Flavonoid Marker Recommendation 模块用于谷子黄酮候选标记推荐。它读取已经整理好的标准 evidence TSV，聚合三个固定重点基因的转录组、代谢组、功能注释、基因组变异状态和文献 evidence，输出：

- 候选标记表。
- Markdown 推荐报告。
- QA 检查 JSON。
- manifest。

当前默认模块是规则版、模板版、可复现 workflow，并带有 DeepRare-like lightweight agent layer。普通 CLI 不调用 LLM，不调用外部 API；LangGraph CLI 可显式启用本地 LLM ReviewerAgent 审阅增强。

项目已新增 LangGraph workflow，用于把现有规则 agents 作为 graph nodes 编排。LangGraph 是当前主线开源智能体编排框架，也是可选依赖；旧 workflow 和旧 CLI 不依赖 LangGraph。

项目还新增了 Deep Agents POC，用于验证未来更高层 agent harness 接入。Deep Agents POC 复用现有 evidence、context builder 和规则 agents，不替代 LangGraph，也不调用真实 LLM。

当前还支持可选接入 Genomics Candidate Variant Calling MVP 的真实 TSV 输出。传入 `--variant-calling-dir` 后，报告会展示每个目标基因的候选区域变异 calling 证据、PASS/LowQual 质量分层和 KASP/CAPS preliminary screening 状态。不传该参数时保持旧行为。

当前 agent layer 已新增 LLM-ready interface。它定义统一输入/输出、prompt templates、context builder 和规则 fallback。LangGraph workflow 现支持可选本地 OpenAI-compatible ReviewerAgent 审阅增强；默认不调用模型，且只允许 reviewer node 调用本地后端。

## 2. 学长硬性要求

核心输入必须记录：

- 转录组：`bam/` 中所有文件。
- 代谢组：`metabolome_raw_3372.tsv`。
- 基因组：`genome.fa` 和 `genome.gff`。
- 功能注释：`local_region_emapper_annotations.tsv`。

固定高优先级基因：

```text
Si9g04210.1
Si5g31340.1
Si9g34380.1
```

报告必须保留核心结论：

```text
优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。
```

硬性限制：

- 不伪造 DOI。
- 不伪造 SNP/InDel 位点。
- 如果没有正式 variant calling 结果，写 `variant_status=not_called`。
- 如果接入 candidate-region variant calling 输出，只能读取真实 TSV 记录，不能补造 SNP/InDel。
- LowQual 位点不能写成优先开发位点。
- KASP/CAPS preliminary screening 不能写成最终标记设计结果。
- 当前 mini BAM calling 不能写成 WGS/GBS 群体变异检测。
- 中文推荐文本必须出现 `群体`。
- 每个重点基因在面向人的报告中必须展示统计值。

## 3. 核心文件

| 文件 | 作用 |
| --- | --- |
| `scripts/demo/create_flavonoid_marker_evidence_from_package.py` | 从学长数据包生成 evidence |
| `src/breeding_agent/integration/flavonoid_marker_package_importer.py` | evidence 转换核心逻辑 |
| `src/breeding_agent/cli/flavonoid_markers.py` | aggregation CLI |
| `src/breeding_agent/workflows/flavonoid_marker_aggregation.py` | aggregation workflow |
| `src/breeding_agent/workflows/flavonoid_marker_langgraph.py` | 可选 LangGraph workflow |
| `src/breeding_agent/integration/flavonoid_marker_aggregator.py` | 聚合 candidate table |
| `src/breeding_agent/integration/flavonoid_variant_evidence.py` | 可选读取 variant calling TSV 并按目标基因聚合 |
| `src/breeding_agent/agents/base.py` | LLM-ready agent base interface |
| `src/breeding_agent/agents/context_builder.py` | 汇总 evidence 为 agent context |
| `src/breeding_agent/agents/prompt_templates.py` | 未来 LLM adapter 可使用的 prompt 模板 |
| `src/breeding_agent/graphs/state.py` | LangGraph state schema |
| `src/breeding_agent/graphs/flavonoid_marker_graph.py` | LangGraph nodes and graph builder |
| `src/breeding_agent/cli/flavonoid_markers_graph.py` | LangGraph workflow CLI |
| `src/breeding_agent/reports/langgraph_trace_report.py` | graph trace / node decision reports |
| `src/breeding_agent/llm/` | 本地 OpenAI-compatible LLM adapter、executor 和 output guard |
| `src/breeding_agent/deepagents/flavonoid_deepagents_poc.py` | Deep Agents POC trace / summary 生成 |
| `src/breeding_agent/workflows/flavonoid_marker_deepagents.py` | Deep Agents POC workflow wrapper |
| `src/breeding_agent/cli/flavonoid_markers_deepagents.py` | Deep Agents POC CLI |
| `src/breeding_agent/agents/flavonoid_central_host.py` | agent 编排 |
| `src/breeding_agent/agents/flavonoid_literature_agent.py` | 文献 evidence 读取 |
| `src/breeding_agent/agents/flavonoid_marker_recommendation_agent.py` | 标记类型推荐 |
| `src/breeding_agent/agents/flavonoid_validation_agent.py` | 后续验证方案 |
| `src/breeding_agent/agents/flavonoid_reviewer_agent.py` | 规则审阅 |
| `src/breeding_agent/agents/flavonoid_final_qa_agent.py` | 最终 QA wrapper |
| `src/breeding_agent/reports/flavonoid_marker_report.py` | Markdown 报告 |
| `src/breeding_agent/integration/flavonoid_marker_qa.py` | QA 规则 |
| `docs/agent_interface_design.md` | agent interface 设计说明 |
| `docs/langgraph_flavonoid_marker_workflow.md` | LangGraph workflow 使用说明 |
| `tests/test_agent_interface.py` | LLM-ready interface 测试 |
| `tests/test_langgraph_flavonoid_workflow.py` | LangGraph workflow 测试 |
| `tests/test_flavonoid_agent_layer.py` | agent layer 测试 |
| `tests/test_flavonoid_marker_qa.py` | QA 测试 |
| `tests/test_flavonoid_variant_evidence.py` | 可选 variant evidence 聚合测试 |

## 4. 入口函数

生成 evidence：

```text
scripts/demo/create_flavonoid_marker_evidence_from_package.py:main()
  -> create_evidence_from_package()
```

aggregation CLI：

```text
src/breeding_agent/cli/flavonoid_markers.py:main()
```

workflow 入口：

```text
src/breeding_agent/workflows/flavonoid_marker_aggregation.py:run_flavonoid_marker_aggregation_task(config)
```

带可选 variant calling evidence 的 CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package \
  --variant-calling-dir outputs/genomics_variant_calling
```

并行 LangGraph CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph \
  --variant-calling-dir outputs/genomics_variant_calling
```

可选本地 LLM ReviewerAgent 增强：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_llm \
  --variant-calling-dir outputs/genomics_variant_calling \
  --use-llm-reviewer \
  --llm-config configs/llm.local.example.yaml
```

该功能使用 OpenAI-compatible 本地后端，只增强 `ReviewerAgent`。请求体传递 `chat_template_kwargs.enable_thinking=false`。如果模型请求失败、返回空内容或 output guard 不通过，会回退到规则版 ReviewerAgent。

并行 Deep Agents POC CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_deepagents \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_deepagents \
  --variant-calling-dir outputs/genomics_variant_calling
```

如果未安装 Deep Agents，会提示：

```text
Deep Agents is not installed. Install according to project docs.
```

如果未安装 LangGraph，会提示：

```text
LangGraph is not installed. Install with: pip install langgraph
```

agent 入口：

```text
src/breeding_agent/agents/flavonoid_central_host.py:FlavonoidCentralHost.run()
```

## 5. evidence 输入

标准 evidence 目录包含：

```text
outputs/flavonoid_marker_from_package/evidence/
├── transcriptome_evidence.tsv
├── metabolome_evidence.tsv
├── annotation_evidence.tsv
├── genome_variant_evidence.tsv
└── literature_evidence.tsv
```

这些文件由：

```text
src/breeding_agent/integration/flavonoid_marker_package_importer.py:create_evidence_from_package()
```

从 `annotations/target_gene_evidence_summary.tsv` 和固定模板 evidence 生成。

其中 `genome_variant_evidence.tsv` 当前写：

```text
variant_status=not_called
```

可选 variant calling evidence 目录：

```text
outputs/genomics_variant_calling/
└── tables/
    ├── candidate_variants.tsv
    ├── kasp_candidate_sites.tsv
    └── caps_candidate_sites.tsv
```

该目录不存在或文件缺失时 workflow 只记录 warning，不失败。不传 `--variant-calling-dir` 时保持原行为。

## 6. aggregation 输出

默认输出：

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

`flavonoid_marker_candidates.tsv` 包括：

- 转录组统计值：`baseMean`、`log2FC`、`pvalue`、`padj`。
- 代谢物相关证据：top correlated metabolite、Pearson r、sPLS metabolite。
- 功能注释：Description、KEGG、PFAM。
- `variant_status`。
- 可选 variant calling 统计：`variant_evidence_status`、`pass_variants`、`lowqual_variants`、`pass_snp_count`、`kasp_preliminary_pass_count`、`caps_pass_variant_requires_enzyme_screening_count` 等。
- `marker_recommendation`。

## 7. DeepRare-like lightweight agent layer 结构

这个 agent layer 是规则版结构化编排，不是外部 Deep Agents 框架。

调用链：

```text
FlavonoidCentralHost.run()
  -> aggregate_flavonoid_marker_candidates()
  -> build_flavonoid_agent_context()
  -> FlavonoidLiteratureAgent.run()
  -> FlavonoidMarkerRecommendationAgent.run()
  -> FlavonoidValidationAgent.run()
  -> render_flavonoid_marker_report()
  -> FlavonoidReviewerAgent.run()
  -> FlavonoidFinalQAAgent.run()
  -> render final report
```

### Agent interface

统一接口定义在：

```text
src/breeding_agent/agents/base.py
```

核心对象：

- `AgentInput`：agent name、context、prompt template 和参数。
- `AgentOutput`：统一结构，包含 `agent_name`、`summary`、`evidence_used`、`warnings`、`limitations`、`structured_payload`。
- `AgentResult`：保留输入、输出、fallback 和 LLM 标记。
- `BaseAgent`：定义 `run_with_context(context)`。
- `RuleBasedAgent`：当前 deterministic fallback。
- `LLMReadyAgentMixin`：只提供 prompt 构建 hook，不调用任何 LLM SDK。

旧 `run()` 调用继续可用；新增 `run_with_context(context)` 返回 `AgentOutput`。旧返回值会额外包含 `agent_output`，但原有字段保持不变。

### Context builder

统一 context 构建位于：

```text
src/breeding_agent/agents/context_builder.py
```

`build_flavonoid_agent_context()` 汇总：

- transcriptomics evidence
- metabolomics evidence
- annotation evidence
- genome variant evidence
- literature evidence
- optional variant calling evidence
- aggregation 后的 candidate rows
- 学长硬性要求和安全边界

context 只读取已整理的小型 evidence TSV 和候选表，不读取 `data/private/` 大文件进入 prompt，也不做 LLM 调用。

### Prompt templates

Prompt 模板位于：

```text
src/breeding_agent/agents/prompt_templates.py
```

包括：

- `literature_agent_prompt`
- `marker_recommendation_agent_prompt`
- `validation_agent_prompt`
- `reviewer_agent_prompt`
- `final_qa_agent_prompt`

模板统一强调：不伪造 SNP/InDel、不伪造 DOI、LowQual 不得优先推荐、preliminary KASP/CAPS 不是最终标记、当前 variant calling 不能替代 WGS/GBS 群体变异检测，并保留学长硬性要求。

### 每个 agent 的职责

- `FlavonoidCentralHost`
  - 组织所有步骤。
  - 构建 agent context。
  - 收集 warnings。
  - 输出 agent_layer metadata，包括 `interface=llm_ready_rule_based_fallback`。
- `FlavonoidLiteratureAgent`
  - 读取 `literature_evidence.tsv`。
  - 原样展示 DOI。
  - 不补写、猜测或生成 DOI。
- `FlavonoidMarkerRecommendationAgent`
  - 根据 `variant_status` 和可选 `variant_evidence_status` 生成 SNP/InDel/KASP/CAPS 推荐。
  - `not_called` 时明确不能写具体位置。
  - 有 `preliminary_pass_variants_detected` 时，可建议优先复核 PASS SNP 的 KASP 转化潜力。
  - 只有 LowQual 时，必须说明不应优先用于 KASP/CAPS，需要人工复核。
  - 当前 mini calling 无 called variant 时，必须说明不能写成已有候选位点。
- `FlavonoidValidationAgent`
  - 输出后续验证方案，包括 Sanger、SNP/InDel calling、KASP、CAPS/dCAPS、群体关联、qRT-PCR、LC-MS/MS。
- `FlavonoidReviewerAgent`
  - 检查缺失统计值、缺失 DOI、缺失验证方案、疑似伪造 variant 坐标、过度推断。
  - 检查 LowQual 是否被错误写成优先推荐。
  - 检查 preliminary KASP/CAPS 是否被错误写成最终标记。
  - 检查 RNA-seq BAM candidate calling 是否被错误写成 WGS/GBS 群体变异检测。
- `FlavonoidFinalQAAgent`
  - 调用 `check_flavonoid_marker_report()`，避免重复实现 QA。

## 8. 报告生成逻辑

报告由 `src/breeding_agent/reports/flavonoid_marker_report.py` 生成。核心函数：

```text
render_flavonoid_marker_report(...)
generate_flavonoid_marker_report_from_agent_result(...)
```

报告包括：

- 任务概述。
- 输入数据。
- 三个目标候选基因。
- 转录组证据表。
- 代谢组证据表。
- 基因组/变异证据。
- 候选区域变异 calling 证据。如果传入 `--variant-calling-dir`，该节会展示每个目标基因的 PASS/LowQual、SNP/InDel、KASP/CAPS 初筛统计。
- 功能注释证据。
- 文献查阅过程和 DOI。
- SNP/InDel/KASP/CAPS 标记类型推荐。
- 后续验证方案。
- 不确定性与限制。
- QA 检查结果。

## 9. QA 检查逻辑

QA 文件：

```text
src/breeding_agent/integration/flavonoid_marker_qa.py
```

检查内容：

- 三个固定重点基因是否出现。
- 是否包含 `群体`、`文献查阅`、`DOI`、`SNP`、`InDel`、`KASP`、`CAPS`。
- 每个重点基因是否有统计值。
- 是否有 DOI。
- 是否有标记类型建议。
- 如果报告包含 LowQual，则必须说明 LowQual 不应直接优先用于 KASP/CAPS。
- 如果报告包含 KASP/CAPS preliminary screening，则必须说明它不是最终标记设计结果。
- 如果报告包含 variant calling，则必须说明不能替代 WGS/GBS 群体变异检测。

输出：

```text
outputs/flavonoid_marker_from_package/logs/qa_check.json
```

常见通过结果：

```text
passed=true
```

## 10. DOI 和文献查阅要求

当前 DOI 来自 `literature_evidence.tsv`。可以使用已有 seed evidence 中的 DOI，但不能编造新的 DOI。

如果要加入新文献：

- 必须人工核验 DOI。
- 必须把 DOI 写入 evidence 文件。
- 报告只能读取或展示已核验 DOI。

不要让报告生成代码自动“猜测” DOI。

## 11. SNP/InDel/KASP/CAPS 推荐逻辑

当前逻辑：

- 如果 `variant_status=not_called`：
  - 不能写具体 SNP/InDel 坐标。
  - 推荐先做候选区域 SNP/InDel calling。
  - 获得高置信多态后优先转 KASP。
  - 如果变异影响限制性内切酶识别位点，再考虑 CAPS/dCAPS。
- 如果未来有正式 called variants：
  - 才能基于真实坐标筛选 SNP/InDel。
  - 才能进一步设计 KASP/CAPS marker。
- 如果传入 `--variant-calling-dir`：
  - `preliminary_pass_variants_detected` 表示候选区域已有真实 VCF PASS variant，可优先复核 PASS SNP 的 KASP 转化潜力。
  - `only_low_quality_variants_detected` 表示只有 LowQual variant，不应直接优先开发。
  - `no_called_variant_in_current_mini_calling` 表示当前 mini calling 未检出 called variant，不能写成已有候选位点。
  - `variant_calling_output_missing` 表示指定输出目录或 TSV 缺失，只保留 warning。

## 12. 常见问题

### 这是 LLM agent 吗？

默认不是。当前 agent layer 是规则版、轻量级、可复现结构。现在已有 LLM-ready interface、prompt templates 和 context builder；LangGraph workflow 可选启用本地 OpenAI-compatible LLM，只增强 ReviewerAgent。

### 未来如何接 OpenAI 或本地模型？

当前已有本地 OpenAI-compatible adapter 服务 ReviewerAgent。未来扩展到 ValidationAgent 或 LiteratureAgent 时，仍应把 `AgentInput` 转成模型请求，把模型输出解析为 `AgentOutput`。模型失败、输出缺字段或违反“不伪造 DOI / SNP/InDel”等硬性限制时，必须丢弃模型输出并 fallback 到规则版。模型输出进入报告前仍要经过 ReviewerAgent / output_guard / FinalQAAgent。

### 当前 LangGraph workflow 是什么？

当前已经有 LangGraph workflow。它把现有 agents 节点化，不改变旧 evidence schema、旧 CLI、报告 QA 和规则 fallback。默认不调用 LLM；显式传入 `--use-llm-reviewer` 和本地 config 时，只允许 ReviewerAgent 调用本地 OpenAI-compatible LLM。Deep Agents 不嵌入 LangGraph 主流程。

LangGraph state 记录 `evidence_dir`、`outdir`、`variant_calling_dir`、`agent_context`、`agent_outputs`、`qa_result` 和 `graph_trace` 等字段。输出包括 `graph_trace.json`、`graph_state_final.json`、`node_decision_table.tsv` 和 `langgraph_summary.md`。

### 当前 Deep Agents POC 是什么？

Deep Agents POC 是并行演示入口，输出 `deepagents_trace.json`、`deepagents_summary.md` 和 `deepagents_decision_table.tsv`。它已经跑通，但只证明本项目可接入 Deep Agents 这类 harness；它不替代 LangGraph，不调用真实大模型，不调用外部 API。

### 为什么报告里没有具体 SNP 坐标？

因为 mini 数据包没有最终 SNP/InDel calling 结果。写具体坐标就是伪造位点。

### DOI 能不能从网上临时搜一个加进去？

不能直接写入报告。必须经过人工核验，并作为 evidence 输入记录。

### 为什么 QA 要查 `群体`？

因为最终建议必须强调更大群体的基因型和黄酮含量数据验证，不能把 mini evidence 当成最终育种结论。

## 13. 学习建议

先读 `flavonoid_marker_package_importer.py`，理解 evidence 从哪里来；再读 `flavonoid_marker_aggregator.py`，理解候选表如何拼出来；然后读 `flavonoid_central_host.py` 看 agent 编排；最后读 report 和 QA，理解为什么报告能通过规则检查。
