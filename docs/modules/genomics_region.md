# Genomics Region 模块导读

## 1. 模块作用

Genomics Region 模块用于读取学长 mini 数据包中的基因组区域、功能注释和目标基因相关表，生成候选区域分析和 marker readiness 输出。

当前它不做正式 SNP/InDel calling，不输出最终 SNP/InDel 坐标。它的作用是说明：

- 三个重点基因对应哪些候选区域。
- 有哪些功能注释证据。
- 是否已经具备进入候选区域 variant calling 和 marker 转化的准备条件。
- 当前 `variant_status=not_called`。

## 2. 核心文件

| 文件 | 作用 |
| --- | --- |
| `src/breeding_agent/modules/genomics/genomics_region.py` | 区域、注释和 marker readiness 处理 |
| `src/breeding_agent/workflows/genomics_region.py` | workflow 编排、manifest、report |
| `src/breeding_agent/reports/genomics_report.py` | Markdown 报告生成 |
| `src/breeding_agent/web/gradio_app.py` | Gradio 页面入口 |
| `tests/test_omics_modules.py` | 基因组模块测试 |

## 3. 入口函数

workflow 入口：

```text
src/breeding_agent/workflows/genomics_region.py:run_genomics_region_task(config)
```

核心处理函数：

```text
src/breeding_agent/modules/genomics/genomics_region.py:build_genomics_region_analysis(dataset_dir, output_dir)
```

报告入口：

```text
src/breeding_agent/reports/genomics_report.py:generate_genomics_report(output_dir, analysis_result)
```

配置对象：

```text
GenomicsRegionConfig
```

## 4. 输入

默认从 `dataset_dir` 读取：

```text
genome.fa
genome.gff
genome.original_coords.gff
genome.bam_compatible.fa.gz
regions/regions.bed
regions/regions.samtools.txt
regions/deg_features.tsv
target_genes.tsv
annotations/local_region_emapper_annotations.tsv
annotations/target_gene_emapper_annotations.tsv
annotations/target_gene_evidence_summary.tsv
```

## 5. 输出

默认输出位置：

```text
outputs/gradio_genomics_run/genomics/
├── target_gene_regions.tsv
├── annotation_summary.tsv
├── marker_readiness.tsv
├── genomics_report.md
└── manifest.json
```

### `target_gene_regions.tsv`

记录目标基因和候选区域的对应关系，包括：

- `gene_id`
- `resolved_id`
- `chrom`
- `start`
- `end`
- `region_chrom`
- `region_start`
- `region_end`
- `region_samtools`

### `annotation_summary.tsv`

记录目标基因功能注释，包括：

- `Description`
- `Preferred_name`
- `KEGG_ko`
- `KEGG_Pathway`
- `PFAMs`

### `marker_readiness.tsv`

必须包含三个重点基因：

```text
Si9g04210.1
Si5g31340.1
Si9g34380.1
```

关键字段：

- `variant_status`
- `candidate_marker_types`
- `readiness_summary`
- `required_next_step`

当前 `variant_status` 必须写：

```text
not_called
```

## 6. 调用链

```text
Gradio Genomics Region Module
  -> web/gradio_app.py:run_genomics_region_analysis_ui()
  -> workflows/genomics_region.py:run_genomics_region_task()
  -> build_genomics_region_analysis()
  -> generate_genomics_report()
  -> manifest.json
```

测试调用链：

```text
tests/test_omics_modules.py
  -> run_genomics_region_task()
  -> 检查 marker_readiness.tsv
```

## 7. 为什么必须强调 `variant_status=not_called`

当前 mini 数据包没有提供最终 SNP/InDel calling 结果表，也没有经过 KASP/CAPS 转化筛选的具体位点。因此不能写具体染色体坐标，也不能把候选区域说成已完成标记开发。

`marker_readiness.tsv` 只能表示：

- 已有候选区域。
- 已有功能注释。
- 可以进入后续变异检测设计。
- 尚不能输出正式标记位点。

## 8. 后续需要 variant calling

后续正式工作应基于：

- BAM
- `genome.fa/genome.gff`
- 或 `genome.bam_compatible.fa.gz` 与 `genome.original_coords.gff`

进行候选区域 SNP/InDel calling，再筛选：

- 高置信 SNP
- 高置信 InDel
- 可转化 KASP 位点
- 满足酶切条件的 CAPS/dCAPS 位点

## 9. 常见问题

### 为什么不直接输出 SNP/InDel 坐标？

因为当前数据包没有最终 variant calling 结果。输出坐标会变成伪造位点，违反项目规则。

### 缺少 `regions/deg_features.tsv` 会怎样？

模块会 fallback 到三个固定重点基因，并记录 warning。这样页面和测试仍能看到三个基因，但区域信息可能为空。

### `genome.fa` 和 `genome.bam_compatible.fa.gz` 有什么区别？

`genome.bam_compatible.fa.gz` 更适合后续和 BAM reference naming / indexing 对齐；`genome.original_coords.gff` 用于解释原始基因坐标和注释。

## 10. 学习建议

先读 `TARGET_GENES`、`INPUT_FILES` 和 `MARKER_READINESS_COLUMNS`，再读 `_marker_readiness()`。这个函数最能体现当前模块的边界：只做 readiness，不做 calling，不输出坐标。
