# Transcriptomics DEG 模块导读

## 1. 模块作用

Transcriptomics DEG 模块用于从本地 BAM 和 GFF 输入复现 mini RNA-seq 差异表达分析。它不是单纯跑 R 脚本，而是一个完整 workflow：

- 校验 BAM、GFF 和外部工具。
- 调用 `featureCounts` 生成 read count。
- 调用 limma-voom R 脚本做差异表达分析。
- 生成 DEG 报告。
- 生成标准 transcriptomics evidence。
- 生成候选基因表和 recommendation report。
- 写 manifest、run log 和 provenance 文件。

当前不要把 flavonoid marker aggregation 逻辑塞进这个 workflow。

## 2. 核心文件

| 文件 | 作用 |
| --- | --- |
| `src/breeding_agent/cli/deg.py` | CLI 入口 |
| `src/breeding_agent/workflows/rnaseq_deg.py` | Python workflow 编排 |
| `workflows/rnaseq_deg/R/differential_expression_limma_voom.R` | limma-voom 差异表达分析 |
| `src/breeding_agent/validators/bam_validator.py` | BAM 输入校验 |
| `src/breeding_agent/validators/gff_validator.py` | GFF 输入校验 |
| `src/breeding_agent/validators/tool_validator.py` | 外部工具校验 |
| `src/breeding_agent/core/command_runner.py` | 外部命令运行和日志记录 |
| `src/breeding_agent/reports/deg_report.py` | DEG Markdown 报告 |
| `src/breeding_agent/reports/deg_result_parser.py` | 解析 DEG significant genes |
| `src/breeding_agent/integration/transcriptomics_standardizer.py` | 标准化 transcriptomics evidence |
| `src/breeding_agent/integration/candidate_aggregator.py` | 生成候选基因表 |
| `src/breeding_agent/integration/recommendation_report.py` | 生成 recommendation report |
| `src/breeding_agent/core/reproducibility.py` | 写 commands 和 checksum |

## 3. 入口函数

CLI 入口：

```text
src/breeding_agent/cli/deg.py:main()
```

workflow 入口：

```text
src/breeding_agent/workflows/rnaseq_deg.py:run_rnaseq_deg_task(config)
```

核心实现：

```text
src/breeding_agent/workflows/rnaseq_deg.py:run_rnaseq_deg(config)
```

配置对象：

```text
RnaSeqDegConfig
```

## 4. 输入

命令行主要输入：

- `--bam-dir`：BAM 文件目录，优先读取 `*.mini.sorted.bam`，否则读取 `*.bam`。
- `--gff`：GFF 注释文件。
- `--contrast`：默认 `JM-LM`。
- `--prefix`：默认 `JM_vs_LM.mini`。
- `--trait`：写入标准 evidence 的性状名称。
- `--threads`：featureCounts 线程数。
- `--outdir`：输出目录。

外部工具要求：

- `featureCounts`
- `Rscript`
- R 脚本所需 R 包，例如 `limma`

## 5. 输出

典型输出目录：

```text
outputs/demo_cli_run/
├── counts/gene_counts_mini.txt
├── mini_de/JM_vs_LM.mini.significant_genes.tsv
├── reports/report.md
├── integration/standardized_evidence.tsv
├── integration/candidate_gene_table.tsv
├── integration/recommendation_report.md
├── logs/run.log
├── manifest.json
└── provenance/
    ├── commands.sh
    └── checksums.sha256
```

其中：

- `manifest.json` 记录输入、输出、命令和状态。
- `run.log` 记录运行日志。
- `provenance/commands.sh` 和 `checksums.sha256` 用于复现和归档。

## 6. 调用链

```text
python3 -m breeding_agent.cli.deg
  -> cli/deg.py:main()
  -> RnaSeqDegConfig
  -> workflows/rnaseq_deg.py:run_rnaseq_deg_task()
  -> run_rnaseq_deg()
  -> validate_bam_dir()
  -> validate_gff()
  -> validate_tools()
  -> featureCounts
  -> Rscript differential_expression_limma_voom.R
  -> generate_deg_report()
  -> standardize_transcriptomics_deg()
  -> generate_candidate_gene_table()
  -> generate_recommendation_report()
  -> write_reproducibility_bundle()
```

## 7. featureCounts 和 limma-voom 的关系

`featureCounts` 负责把 BAM 对齐结果按 GFF 注释计数，当前命令核心参数包括：

```text
featureCounts -T <threads> -p -t exon -g Parent -a <gff> -o <counts_file> <bam...>
```

重要点：

- `-g Parent` 是当前注释策略的一部分，不要随意修改。
- `featureCounts` 输出的 count table 会作为 R 脚本输入。

R 脚本负责：

- 读取 count table。
- 按 contrast 做 limma-voom 差异分析。
- 应用阈值，例如 FDR、logFC、min-count、min-samples。
- 输出 significant genes。

## 8. 报告生成

`rnaseq_deg.py` 在 R 分析后调用：

```text
generate_deg_report(DegReportConfig(...))
```

报告会读取：

- counts 文件路径。
- significant genes 文件路径。
- manifest 路径。
- run log 路径。

`deg_result_parser.py` 会解析 significant genes，并特别查看目标基因 `Si9g04210.1` 的复现情况。

## 9. 当前不要修改的部分

除非任务明确要求，不要修改：

- `src/breeding_agent/workflows/rnaseq_deg.py`
- `workflows/rnaseq_deg/R/differential_expression_limma_voom.R`
- `featureCounts -g Parent` 行为
- validators 的校验强度
- manifest / provenance 写入逻辑

## 10. 常见问题

### 为什么找不到 BAM？

workflow 先找 `*.mini.sorted.bam`，找不到才找 `*.bam`。检查 `--bam-dir` 是否指到真正的 BAM 目录。

### 为什么 featureCounts 失败？

常见原因：

- 环境中没有 `featureCounts`。
- BAM 和 GFF 的参考序列名不匹配。
- GFF 路径不对。

### 为什么 Rscript 失败？

常见原因：

- 环境中没有 `Rscript`。
- R 包缺失。
- counts 文件格式异常。

### 为什么不要直接改 R 脚本？

R 脚本是当前 DEG workflow 的核心统计逻辑。修改阈值、模型或输出列都会影响下游报告、evidence 标准化和测试预期。

## 11. 学习建议

先读 `cli/deg.py`，再读 `workflows/rnaseq_deg.py`。读 workflow 时在纸上画出输出路径，然后对照一次真实运行结果。最后再读 `reports/deg_report.py` 和 `integration/transcriptomics_standardizer.py`，理解为什么 DEG 结果要被标准化成 evidence。
