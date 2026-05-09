# breeding-agent 代码阅读指南

适用读者：第一次接手项目、需要从入口一路读到 workflow / agent / report / QA / Gradio 的同学。  
阅读目标：建立阅读顺序，避免只看零散文件；快速定位普通 workflow、LangGraph、Deep Agents POC、本地 LLM Reviewer 和 Promoter scaffold。

## 推荐阅读顺序

### 第 1 步：先读项目规则和总览

先读：

1. `AGENTS.md`
2. `docs/project_onboarding.md`
3. `docs/architecture_overview.md`
4. `docs/developer/codebase_map.md`
5. `docs/developer/business_logic_by_file.md`

重点理解：

- 研究对象是谷子。
- 当前项目已经不只是 RNA-seq DEG demo；生产主线包括 RNA-seq DEG、flavonoid marker recommendation、Genomics Candidate Variant Calling MVP、LangGraph 多智能体 workflow 和 Gradio 展示。Promoter Design 当前只是 scaffold。
- 新增方向是谷子黄酮候选标记推荐。
- 不能伪造 DOI。
- 不能伪造 SNP/InDel 位点。
- `data/private/` 和 `outputs/` 不能提交。

### 第 2 步：读主要 CLI 入口

先读：

- `src/breeding_agent/cli/deg.py`
- `src/breeding_agent/cli/flavonoid_markers.py`
- `src/breeding_agent/cli/flavonoid_markers_graph.py`
- `src/breeding_agent/cli/flavonoid_markers_deepagents.py`
- `src/breeding_agent/cli/genomics_variants.py`
- `src/breeding_agent/cli/promoter_design.py`

这两个文件最短，最适合理解参数如何进入 workflow。

阅读方法：

- 找 `build_parser()` 看命令行参数。
- 找 `main()` 看如何构造 config。
- 找 `run_*_task()` 调用，跳到对应 workflow。

### 第 3 步：读 workflow

按顺序读：

1. `src/breeding_agent/workflows/rnaseq_deg.py`
2. `src/breeding_agent/workflows/metabolomics_evidence.py`
3. `src/breeding_agent/workflows/genomics_region.py`
4. `src/breeding_agent/workflows/flavonoid_marker_aggregation.py`
5. `src/breeding_agent/workflows/flavonoid_marker_langgraph.py`
6. `src/breeding_agent/workflows/flavonoid_marker_deepagents.py`
7. `src/breeding_agent/workflows/promoter_design.py`

workflow 是项目的编排层，负责：

- 输入路径和输出路径。
- 调用核心处理函数。
- 写 manifest。
- 处理 warning / error。
- 对外暴露 `run_*_task()`。

### 第 4 步：读核心数据处理层

RNA-seq DEG 相关：

- `src/breeding_agent/validators/`
- `src/breeding_agent/core/command_runner.py`
- `src/breeding_agent/integration/transcriptomics_standardizer.py`
- `src/breeding_agent/integration/candidate_aggregator.py`
- `src/breeding_agent/integration/recommendation_report.py`

代谢组和基因组模块：

- `src/breeding_agent/modules/metabolomics/metabolomics_evidence.py`
- `src/breeding_agent/modules/genomics/genomics_region.py`
- `src/breeding_agent/modules/genomics/variant_calling.py`
- `src/breeding_agent/modules/promoter/promoter_task_schema.py`

黄酮标记推荐：

- `scripts/demo/create_flavonoid_marker_evidence_from_package.py`
- `src/breeding_agent/integration/flavonoid_marker_package_importer.py`
- `src/breeding_agent/integration/flavonoid_marker_aggregator.py`
- `src/breeding_agent/agents/`
- `src/breeding_agent/graphs/`
- `src/breeding_agent/llm/`
- `src/breeding_agent/deepagents/`

### 第 5 步：读报告和 QA

报告文件：

- `src/breeding_agent/reports/deg_report.py`
- `src/breeding_agent/reports/metabolomics_report.py`
- `src/breeding_agent/reports/genomics_report.py`
- `src/breeding_agent/reports/flavonoid_marker_report.py`

QA 文件：

- `src/breeding_agent/integration/flavonoid_marker_qa.py`
- `src/breeding_agent/agents/flavonoid_final_qa_agent.py`

阅读重点：

- 报告中哪些字段必须展示。
- QA 检查哪些关键词和统计值。
- 为什么 DOI 和 SNP/InDel 坐标不能随便写。

### 第 6 步：最后读 Gradio

最后读：

- `src/breeding_agent/web/gradio_app.py`

原因：Gradio 文件比较长，但它主要是展示层。当前页面使用顶部 `gr.Tab` 结构，包括 `Transcriptomics DEG Module`、`Metabolomics Module`、`Genomics / GWAS Module`、`Integration & Recommendation` 和 `谷子黄酮候选标记推荐`。先理解后端 workflow 后，再看每个 Tab 的按钮如何调用函数会更容易。

## 关键文件作用速查

| 文件 | 作用 |
| --- | --- |
| `src/breeding_agent/cli/deg.py` | RNA-seq DEG CLI 参数入口 |
| `src/breeding_agent/workflows/rnaseq_deg.py` | RNA-seq DEG workflow 编排 |
| `workflows/rnaseq_deg/R/differential_expression_limma_voom.R` | limma-voom 差异分析 |
| `src/breeding_agent/cli/flavonoid_markers.py` | 黄酮标记推荐 CLI 入口 |
| `src/breeding_agent/workflows/flavonoid_marker_aggregation.py` | 黄酮标记 aggregation workflow |
| `src/breeding_agent/agents/flavonoid_central_host.py` | DeepRare-like lightweight agent 编排 |
| `src/breeding_agent/graphs/flavonoid_marker_graph.py` | LangGraph 节点编排 |
| `src/breeding_agent/llm/executor.py` | 本地 LLM Reviewer 调用和 fallback |
| `src/breeding_agent/llm/output_guard.py` | LLM 输出安全检查 |
| `src/breeding_agent/integration/flavonoid_marker_aggregator.py` | 聚合 evidence 为候选标记表 |
| `src/breeding_agent/integration/flavonoid_marker_qa.py` | 规则 QA |
| `src/breeding_agent/modules/metabolomics/metabolomics_evidence.py` | 代谢组 evidence table 处理 |
| `src/breeding_agent/modules/genomics/genomics_region.py` | 基因组区域和 marker readiness 处理 |
| `src/breeding_agent/web/gradio_app.py` | Gradio 展示层 |
| `docs/developer/workflow_tracing_guide.md` | CLI 到报告的调用链 |
| `tests/` | 当前行为的安全网 |

## 从 CLI 追踪到 workflow

### RNA-seq DEG

```text
python3 -m breeding_agent.cli.deg
  -> cli/deg.py:main()
  -> RnaSeqDegConfig
  -> workflows/rnaseq_deg.py:run_rnaseq_deg_task()
  -> workflows/rnaseq_deg.py:run_rnaseq_deg()
```

继续追踪：

```text
run_rnaseq_deg()
  -> validate_bam_dir / validate_gff / validate_tools
  -> featureCounts
  -> Rscript differential_expression_limma_voom.R
  -> generate_deg_report()
  -> standardize_transcriptomics_deg()
  -> generate_candidate_gene_table()
  -> generate_recommendation_report()
  -> write_reproducibility_bundle()
```

### Flavonoid Marker

```text
python3 -m breeding_agent.cli.flavonoid_markers
  -> cli/flavonoid_markers.py:main()
  -> FlavonoidMarkerAggregationConfig
  -> workflows/flavonoid_marker_aggregation.py:run_flavonoid_marker_aggregation_task()
  -> FlavonoidCentralHost(...).run()
```

继续追踪：

```text
FlavonoidCentralHost.run()
  -> aggregate_flavonoid_marker_candidates()
  -> FlavonoidLiteratureAgent.run()
  -> FlavonoidMarkerRecommendationAgent.run()
  -> FlavonoidValidationAgent.run()
  -> render_flavonoid_marker_report()
  -> FlavonoidReviewerAgent.run()
  -> FlavonoidFinalQAAgent.run()
  -> generate_flavonoid_marker_report_from_agent_result()
  -> qa_check.json + manifest.json
```

## 从 workflow 追踪到 report / QA / manifest

### workflow 到 report

- RNA-seq DEG：`rnaseq_deg.py` 调 `reports/deg_report.py`。
- Metabolomics：`metabolomics_evidence.py` 调 `reports/metabolomics_report.py`。
- Genomics：`genomics_region.py` 调 `reports/genomics_report.py`。
- Flavonoid marker：`flavonoid_marker_aggregation.py` 调 `reports/flavonoid_marker_report.py`。

### workflow 到 QA

当前只有 flavonoid marker recommendation 有专门 QA：

```text
flavonoid_marker_aggregation.py
  -> FlavonoidCentralHost.run()
  -> FlavonoidFinalQAAgent.run()
  -> integration/flavonoid_marker_qa.py:check_flavonoid_marker_report()
  -> logs/qa_check.json
```

### workflow 到 manifest

每个 workflow 都负责写自己的 `manifest.json`：

- 记录任务名、输入、输出、warning、状态、时间。
- 失败时记录 `error_message`。
- 成功时记录输出路径。

## 哪些文件不要轻易修改

除非任务明确要求，否则不要改：

- `src/breeding_agent/workflows/rnaseq_deg.py`
- `workflows/rnaseq_deg/R/differential_expression_limma_voom.R`
- `src/breeding_agent/core/command_runner.py`
- `src/breeding_agent/validators/`
- `src/breeding_agent/integration/flavonoid_marker_qa.py`
- `src/breeding_agent/reports/flavonoid_marker_report.py` 中的核心结论和限制说明

尤其不要改：

- `featureCounts -g Parent` 行为。
- `variant_status=not_called` 的含义。
- QA 对 `群体`、DOI、SNP/InDel/KASP/CAPS 和三个固定基因的检查。

## 如何结合 tests 理解代码

先读测试，再读实现，经常更快。

### `tests/test_flavonoid_marker_qa.py`

这个文件说明 QA 最关心什么：

- 三个固定重点基因。
- `群体`。
- DOI。
- SNP/InDel/KASP/CAPS。
- 每个基因的统计值。

### `tests/test_flavonoid_agent_layer.py`

这个文件说明 agent layer 的行为边界：

- Literature agent 必须展示 DOI。
- Marker recommendation agent 在 `variant_status=not_called` 时不能伪造坐标。
- Validation agent 必须包含群体、Sanger、SNP/InDel calling、KASP、CAPS/dCAPS、qRT-PCR、LC-MS/MS。
- CLI 可以用真实 evidence 跑通，并让 QA 通过。

### `tests/test_omics_modules.py`

这个文件说明代谢组和基因组模块的最低行为：

- 用学长数据包能生成输出。
- 缺少部分输入也不会直接崩溃，而是返回 warning。
- `marker_readiness.tsv` 必须包含三个重点基因。
- `variant_status` 必须是 `not_called`。

## 学习建议

- 第一次不要直接改代码，先跑一遍 CLI 和测试。
- 每次只追一条调用链，例如先追 RNA-seq DEG，再追 flavonoid marker。
- 看到 `outputs/` 只用于理解结果，不要提交。
- 看到 `data/private/` 只用于本地输入，不要提交。
- 如果文档和代码不一致，以代码和测试为准，再更新文档。
