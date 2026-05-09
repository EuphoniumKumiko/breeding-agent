# Metabolomics Evidence 模块导读

适用读者：维护 Metabolomics Module 或需要理解学长数据包代谢组 evidence 的同学。  
阅读目标：明确当前模块读取已有结果表，不做完整原始质谱重分析。

## 1. 模块作用

Metabolomics Evidence 模块用于读取学长 mini 数据包中已经整理好的代谢组结果表，生成适合 Gradio 展示和报告汇报的 evidence analysis 输出。

它当前不是完整原始质谱重分析，不会从峰表重新做统计建模、差异代谢物检验或 pathway enrichment。它做的是：

- 检查学长数据包中代谢组相关文件是否存在。
- 复制关键结果表到输出目录。
- 对缺失文件返回 warning，不直接崩溃。
- 汇总候选代谢物、显著黄酮相关代谢物、基因-代谢物网络和 sPLS 证据。
- 生成 `metabolomics_report.md` 和 `manifest.json`。

## 2. 核心文件

| 文件 | 作用 |
| --- | --- |
| `src/breeding_agent/modules/metabolomics/metabolomics_evidence.py` | 代谢组 evidence table 处理 |
| `src/breeding_agent/workflows/metabolomics_evidence.py` | workflow 编排、manifest、report |
| `src/breeding_agent/reports/metabolomics_report.py` | Markdown 报告生成 |
| `src/breeding_agent/web/gradio_app.py` | Gradio 页面入口 |
| `tests/test_omics_modules.py` | 代谢组模块测试 |

## 3. 入口函数

workflow 入口：

```text
src/breeding_agent/workflows/metabolomics_evidence.py:run_metabolomics_evidence_task(config)
```

核心处理函数：

```text
src/breeding_agent/modules/metabolomics/metabolomics_evidence.py:build_metabolomics_evidence(dataset_dir, output_dir)
```

报告入口：

```text
src/breeding_agent/reports/metabolomics_report.py:generate_metabolomics_report(output_dir, analysis_result)
```

配置对象：

```text
MetabolomicsEvidenceConfig
```

## 4. 输入

默认从 `dataset_dir` 读取：

```text
metabolome/metabolome_raw_3372.tsv
metabolome/candidate_metabolites.tsv
metabolome/flavonoid_related_significant_metabolites.tsv
metabolome/target_gene_metabolite_network_edges.tsv
metabolome/target_gene_spls_coefficients.tsv
metabolome/target_gene_related_metabolite_abundance.tsv
sample_metadata.tsv
annotations/target_gene_evidence_summary.tsv
```

当前真正写出到结果目录的关键表是：

- `candidate_metabolites.tsv`
- `flavonoid_related_significant_metabolites.tsv`
- `target_gene_metabolite_network_edges.tsv`
- `target_gene_spls_coefficients.tsv`

## 5. 输出

默认输出位置：

```text
outputs/gradio_metabolomics_run/metabolomics/
├── candidate_metabolites.tsv
├── flavonoid_related_significant_metabolites.tsv
├── target_gene_metabolite_network_edges.tsv
├── target_gene_spls_coefficients.tsv
├── metabolomics_report.md
└── manifest.json
```

如果某些输入表不存在，模块会写出只有表头的 TSV，方便 Gradio 表格继续渲染，并在 `warnings` 和 `manifest.json` 中记录。

## 6. 调用链

```text
Gradio Metabolomics Evidence Module
  -> web/gradio_app.py:run_metabolomics_evidence_analysis()
  -> workflows/metabolomics_evidence.py:run_metabolomics_evidence_task()
  -> build_metabolomics_evidence()
  -> generate_metabolomics_report()
  -> manifest.json
```

测试调用链：

```text
tests/test_omics_modules.py
  -> run_metabolomics_evidence_task()
```

## 7. 报告内容

`metabolomics_report.md` 主要包括：

- 输入文件存在情况。
- Warning。
- 候选黄酮代谢物预览。
- 显著黄酮相关代谢物预览。
- 目标基因-代谢物相关网络。
- sPLS 证据。
- 三个重点基因关系：
  - `Si9g04210.1`
  - `Si5g31340.1`
  - `Si9g34380.1`
- 当前限制说明：这是基于已有结果表的 evidence analysis，不是完整原始质谱重分析。

## 8. 当前限制

- 不读取或解析所有原始质谱峰表。
- 不重新做差异代谢物统计。
- 不重新做 sPLS 建模。
- 不调用外部数据库或 API。
- 不生成最终育种结论，只提供代谢组 evidence 支持。

## 9. 常见问题

### 缺文件会不会崩溃？

不会。`build_metabolomics_evidence()` 会记录 warning，并为关键输出表写空表头。

### 为什么 `metabolome_raw_3372.tsv` 不直接输出？

当前第一版只展示汇总后的候选代谢物、显著代谢物、网络边和 sPLS 系数。原始大表用于 provenance 和后续扩展，不直接复制到输出目录。

### 能否把这个模块说成完整代谢组流程？

不能。文档和报告必须明确它是基于学长数据包已有结果表的 evidence analysis。

## 10. 学习建议

先读 `INPUT_FILES`、`OUTPUT_TABLES` 和 `DEFAULT_HEADERS`，理解输入输出映射。然后读 `build_metabolomics_evidence()`，看它如何复制表、统计 row count、生成 preview。最后读 `metabolomics_report.py`，理解分析结果如何变成 Markdown 报告。
