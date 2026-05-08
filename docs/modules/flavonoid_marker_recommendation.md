# Flavonoid Marker Recommendation 模块导读

## 1. 模块作用

Flavonoid Marker Recommendation 模块用于谷子黄酮候选标记推荐。它读取已经整理好的标准 evidence TSV，聚合三个固定重点基因的转录组、代谢组、功能注释、基因组变异状态和文献 evidence，输出：

- 候选标记表。
- Markdown 推荐报告。
- QA 检查 JSON。
- manifest。

当前模块是规则版、模板版、可复现 workflow，并带有 DeepRare-like lightweight agent layer。它不调用 LLM，不调用外部 API，不引入 Deep Agents 或 LangGraph。

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
- 中文推荐文本必须出现 `群体`。
- 每个重点基因在面向人的报告中必须展示统计值。

## 3. 核心文件

| 文件 | 作用 |
| --- | --- |
| `scripts/demo/create_flavonoid_marker_evidence_from_package.py` | 从学长数据包生成 evidence |
| `src/breeding_agent/integration/flavonoid_marker_package_importer.py` | evidence 转换核心逻辑 |
| `src/breeding_agent/cli/flavonoid_markers.py` | aggregation CLI |
| `src/breeding_agent/workflows/flavonoid_marker_aggregation.py` | aggregation workflow |
| `src/breeding_agent/integration/flavonoid_marker_aggregator.py` | 聚合 candidate table |
| `src/breeding_agent/agents/flavonoid_central_host.py` | agent 编排 |
| `src/breeding_agent/agents/flavonoid_literature_agent.py` | 文献 evidence 读取 |
| `src/breeding_agent/agents/flavonoid_marker_recommendation_agent.py` | 标记类型推荐 |
| `src/breeding_agent/agents/flavonoid_validation_agent.py` | 后续验证方案 |
| `src/breeding_agent/agents/flavonoid_reviewer_agent.py` | 规则审阅 |
| `src/breeding_agent/agents/flavonoid_final_qa_agent.py` | 最终 QA wrapper |
| `src/breeding_agent/reports/flavonoid_marker_report.py` | Markdown 报告 |
| `src/breeding_agent/integration/flavonoid_marker_qa.py` | QA 规则 |
| `tests/test_flavonoid_agent_layer.py` | agent layer 测试 |
| `tests/test_flavonoid_marker_qa.py` | QA 测试 |

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
- `marker_recommendation`。

## 7. DeepRare-like lightweight agent layer 结构

这个 agent layer 是规则版结构化编排，不是外部 Deep Agents 框架。

调用链：

```text
FlavonoidCentralHost.run()
  -> aggregate_flavonoid_marker_candidates()
  -> FlavonoidLiteratureAgent.run()
  -> FlavonoidMarkerRecommendationAgent.run()
  -> FlavonoidValidationAgent.run()
  -> render_flavonoid_marker_report()
  -> FlavonoidReviewerAgent.run()
  -> FlavonoidFinalQAAgent.run()
  -> render final report
```

### 每个 agent 的职责

- `FlavonoidCentralHost`
  - 组织所有步骤。
  - 收集 warnings。
  - 输出 agent_layer metadata。
- `FlavonoidLiteratureAgent`
  - 读取 `literature_evidence.tsv`。
  - 原样展示 DOI。
  - 不补写、猜测或生成 DOI。
- `FlavonoidMarkerRecommendationAgent`
  - 根据 `variant_status` 生成 SNP/InDel/KASP/CAPS 推荐。
  - `not_called` 时明确不能写具体位置。
- `FlavonoidValidationAgent`
  - 输出后续验证方案，包括 Sanger、SNP/InDel calling、KASP、CAPS/dCAPS、群体关联、qRT-PCR、LC-MS/MS。
- `FlavonoidReviewerAgent`
  - 检查缺失统计值、缺失 DOI、缺失验证方案、疑似伪造 variant 坐标、过度推断。
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

## 12. 常见问题

### 这是 LLM agent 吗？

不是。当前 agent layer 是规则版、轻量级、可复现结构，不调用 LLM。

### 为什么报告里没有具体 SNP 坐标？

因为 mini 数据包没有最终 SNP/InDel calling 结果。写具体坐标就是伪造位点。

### DOI 能不能从网上临时搜一个加进去？

不能直接写入报告。必须经过人工核验，并作为 evidence 输入记录。

### 为什么 QA 要查 `群体`？

因为最终建议必须强调更大群体的基因型和黄酮含量数据验证，不能把 mini evidence 当成最终育种结论。

## 13. 学习建议

先读 `flavonoid_marker_package_importer.py`，理解 evidence 从哪里来；再读 `flavonoid_marker_aggregator.py`，理解候选表如何拼出来；然后读 `flavonoid_central_host.py` 看 agent 编排；最后读 report 和 QA，理解为什么报告能通过规则检查。
