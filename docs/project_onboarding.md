# breeding-agent 项目上手文档

## 1. 项目定位

`breeding-agent` 是一个面向作物多组学育种分析的可复现项目。当前项目的研究作物是谷子，已经有一个可运行的 RNA-seq DEG workflow，并开始扩展谷子黄酮标记推荐任务。

当前核心定位：

- 已实现：RNA-seq 差异表达分析、结果报告、标准 transcriptomics evidence、候选基因表和第一版 recommendation report。
- 已实现：从学长谷子黄酮标记 mini 数据包生成 aggregation evidence 的 demo 转换脚本。
- 已实现：flavonoid marker aggregation CLI，用于整合 transcriptome、metabolome、annotation、genome variant 和 literature evidence，给出 SNP/InDel/KASP/CAPS 等可开发标记类型建议，并输出 QA 检查结果。
- 禁止事项：不能伪造 SNP/InDel 位点，不能伪造 DOI，不能把 `data/private/` 和 `outputs/` 中的数据加入 Git。

当前项目根目录未发现 `README.md`，因此新人应优先阅读本文档、`AGENTS.md` 和 `docs/flavonoid_marker_package_import.md`。

## 2. 当前已有能力

已实现的 RNA-seq DEG workflow：

- CLI 入口：`src/breeding_agent/cli/deg.py`
- workflow 编排：`src/breeding_agent/workflows/rnaseq_deg.py`
- 外部命令执行：`src/breeding_agent/core/command_runner.py`
- 输入校验：`src/breeding_agent/validators/`
- DEG 报告：`src/breeding_agent/reports/`
- evidence 标准化和聚合：`src/breeding_agent/integration/`
- R 脚本：`workflows/rnaseq_deg/R/differential_expression_limma_voom.R`

已实现的黄酮标记数据包 evidence 转换：

- 脚本：`scripts/demo/create_flavonoid_marker_evidence_from_package.py`
- 文档：`docs/flavonoid_marker_package_import.md`
- 已验证命令使用 `python3` 可以运行，输出 5 个 evidence TSV 文件。

已实现的黄酮标记 aggregation：

- CLI：`src/breeding_agent/cli/flavonoid_markers.py`
- workflow：`src/breeding_agent/workflows/flavonoid_marker_aggregation.py`
- aggregator：`src/breeding_agent/integration/flavonoid_marker_aggregator.py`
- QA：`src/breeding_agent/integration/flavonoid_marker_qa.py`
- report：`src/breeding_agent/reports/flavonoid_marker_report.py`

## 3. 目录结构速览

```text
src/breeding_agent/
├── cli/
│   ├── deg.py
│   └── flavonoid_markers.py
├── core/
│   ├── command_runner.py
│   └── reproducibility.py
├── integration/
│   ├── evidence_schema.py
│   ├── transcriptomics_standardizer.py
│   ├── candidate_aggregator.py
│   ├── recommendation_report.py
│   ├── flavonoid_marker_aggregator.py
│   └── flavonoid_marker_qa.py
├── reports/
│   ├── deg_result_parser.py
│   ├── deg_report.py
│   └── flavonoid_marker_report.py
├── validators/
│   ├── bam_validator.py
│   ├── gff_validator.py
│   ├── tool_validator.py
│   └── validation_result.py
├── web/
│   └── gradio_app.py
└── workflows/
    ├── rnaseq_deg.py
    └── flavonoid_marker_aggregation.py

scripts/demo/
└── create_flavonoid_marker_evidence_from_package.py

workflows/rnaseq_deg/R/
└── differential_expression_limma_voom.R
```

重要说明：

- `src/breeding_agent/workflows/rnaseq_deg.py` 是 Python workflow 编排层。
- `workflows/rnaseq_deg/R/differential_expression_limma_voom.R` 是 R 差异分析脚本。
- `scripts/demo/` 适合放数据包转换、demo 输入整理等一次性或演示型脚本。
- `data/private/` 用于本地私有数据，不应提交。
- `outputs/` 用于运行结果，不应提交。

## 4. RNA-seq DEG workflow 如何运行

运行前需要环境中有：

- `python3`
- `featureCounts`
- `Rscript`
- R 脚本依赖的 R 包，例如 `limma`

示例命令：

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 -m breeding_agent.cli.deg \
  --bam-dir data/private/flavonoid_marker_mini_5genes_50kb/bam \
  --gff data/private/flavonoid_marker_mini_5genes_50kb/genome.original_coords.gff \
  --trait 黄酮 \
  --threads 4
```

该命令会调用：

1. `validate_bam_dir`
2. `validate_gff`
3. `validate_tools`
4. `featureCounts -T <threads> -p -t exon -g Parent`
5. `Rscript workflows/rnaseq_deg/R/differential_expression_limma_voom.R`
6. `generate_deg_report`
7. `standardize_transcriptomics_deg`
8. `generate_candidate_gene_table`
9. `generate_recommendation_report`
10. `write_reproducibility_bundle`

典型输出：

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

不要修改现有 RNA-seq DEG workflow，除非任务明确要求。

## 5. 谷子黄酮标记推荐任务说明

学长要求的核心输入：

- 转录组：`bam/` 中所有文件
- 代谢组：`metabolome_raw_3372.tsv`
- 基因组：`genome.fa` 和 `genome.gff`
- 功能注释：`local_region_emapper_annotations.tsv`

任务目标是基于这些数据给出可开发标记类型建议，例如 SNP/InDel/KASP/CAPS，并说明还需要哪些验证。当前 mini 数据包已经提供预处理 evidence summary，可以先用于生成 aggregation evidence；正式 marker 开发仍需要后续 variant calling、群体验证、黄酮含量表型验证和文献查阅。

固定重点基因：

- `Si9g04210.1`
- `Si5g31340.1`
- `Si9g34380.1`

必须保留的结论句：

```text
优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。
```

当前每个目标基因的统计学数值如下，来自 `outputs/flavonoid_marker_from_package/evidence/` 中已生成的 evidence：

| gene_id | baseMean | log2FC | pvalue | padj | Green_mean | Golden_mean | Direction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Si9g04210.1` | 3234.583184 | -6.542585349 | 2.5e-162 | 5.62e-158 | 6401.01352933333 | 68.1528381033333 | Higher_in_Green |
| `Si5g31340.1` | 173.0025915 | 1.574439128 | 5.86e-10 | 4.71e-07 | 86.8450925466667 | 259.1600905 | Higher_in_Golden |
| `Si9g34380.1` | 73.04607021 | 3.204977856 | 3.18e-17 | 8.95e-14 | 14.38107137 | 131.711069033333 | Higher_in_Golden |

代谢组相关统计：

| gene_id | n_network_edges | max_abs_pearson | top_correlated_metabolite | top_pearson_r | n_spls_coefficients | max_abs_spls_coefficient | top_spls_metabolite |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `Si9g04210.1` | 30 | 0.995767042374107 | 4,2',3',4'-Tetrahydroxychalcone* | -0.995767042374107 | 17 | 0.130083621782761 | 2-(4-hydroxyphenyl)-2H-chromene-3,5,7-triol |
| `Si5g31340.1` | 30 | 0.988799901881308 | Epicatechin 3-glucoside | 0.988799901881308 |  |  |  |
| `Si9g34380.1` | 30 | 0.995505738552351 | 4'-Hydroxy-5,7-dimethoxyflavanone | 0.995505738552351 |  |  |  |

功能注释摘要：

| gene_id | Description | KEGG_ko | KEGG_Pathway | PFAMs |
| --- | --- | --- | --- | --- |
| `Si9g04210.1` | Belongs to the chalcone isomerase family | ko:K01859 | ko00941, ko01100, ko01110, map00941, map01100, map01110 | Chalcone |
| `Si5g31340.1` | Belongs to the UDP-glycosyltransferase family | ko:K12938 | ko00942, map00942 | UDPGT |
| `Si9g34380.1` | Belongs to the GST superfamily | ko:K00799 | ko00480, ko00980, ko00982, ko00983, ko01524, ko05200, ko05204, ko05225, ko05418, map00480, map00980, map00982, map00983, map01524, map05200, map05204, map05225, map05418 | GST_C, GST_C_2, GST_N, GST_N_3 |

## 6. 学长数据包结构说明

学长数据包是 mini 数据和预处理结果包，不是脚本包，也不是完整自动分析 pipeline。

关键文件包括：

```text
flavonoid_marker_mini_5genes_50kb/
├── bam/
│   ├── TG5_101_JM_1.mini.sorted.bam
│   ├── TG5_101_JM_2.mini.sorted.bam
│   ├── TG5_101_JM_3.mini.sorted.bam
│   ├── TG5_101_LM_1.mini.sorted.bam
│   ├── TG5_101_LM_2.mini.sorted.bam
│   └── TG5_101_LM_3.mini.sorted.bam
├── metabolome/
│   ├── metabolome_raw_3372.tsv
│   ├── target_gene_metabolite_network_edges.tsv
│   └── target_gene_spls_coefficients.tsv
├── annotations/
│   ├── local_region_emapper_annotations.tsv
│   ├── target_gene_evidence_summary.tsv
│   └── target_gene_emapper_annotations.tsv
├── transcriptome/
│   └── target_gene_expression_and_de.tsv
├── genome.fa
├── genome.gff
├── genome.original_coords.gff
├── genome.bam_compatible.fa.gz
├── sample_metadata.tsv
└── target_genes.tsv
```

其中 `annotations/target_gene_evidence_summary.tsv` 是当前转换脚本唯一直接读取的必需输入。其他文件用于人工复核、后续变异 calling、报告说明和 provenance。

## 7. 数据包迁移位置

当前本地迁移位置：

```text
data/private/flavonoid_marker_mini_5genes_50kb/
```

解压示例：

```bash
cd ~/projects/breeding-agent
mkdir -p data/private
tar -xf /path/to/flavonoid_marker_mini_5genes_50kb.tar.gz -C data/private/
```

注意：

- `data/private/` 不提交 Git。
- 不要复制 BAM、FASTA、代谢组大表到 `docs/` 或 `src/`。
- 文档中可以写必要字段、路径和小规模统计摘要，但不要把原始私有数据表完整写进仓库。

## 8. evidence 转换流程

已实现脚本：

```text
scripts/demo/create_flavonoid_marker_evidence_from_package.py
```

运行命令：

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 scripts/demo/create_flavonoid_marker_evidence_from_package.py \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/flavonoid_marker_from_package/evidence
```

脚本行为：

- 必须存在：`annotations/target_gene_evidence_summary.tsv`
- 其他文件缺失：只打印 warning
- 固定输出三个重点基因：`Si9g04210.1`、`Si5g31340.1`、`Si9g34380.1`
- 不伪造 SNP/InDel 位点
- 没有正式 variant calling 表时，`genome_variant_evidence.tsv` 写 `variant_status=not_called`
- 输出后打印每个 evidence 文件路径、行数和目标基因存在性

已验证输出行数：

| 文件 | 行数 |
| --- | ---: |
| `transcriptome_evidence.tsv` | 3 |
| `metabolome_evidence.tsv` | 3 |
| `annotation_evidence.tsv` | 3 |
| `genome_variant_evidence.tsv` | 3 |
| `literature_evidence.tsv` | 4 |

## 9. flavonoid marker aggregation workflow

当前状态：已实现。

运行 CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package
```

处理逻辑：

1. 读取 `transcriptome_evidence.tsv`
2. 读取 `metabolome_evidence.tsv`
3. 读取 `annotation_evidence.tsv`
4. 读取 `genome_variant_evidence.tsv`
5. 读取 `literature_evidence.tsv`
6. 聚合每个目标基因的转录组、代谢组、注释、变异状态和文献证据
7. 输出 marker 类型建议，例如 SNP/InDel/KASP/CAPS
8. 明确说明当前是否已有 variant calling 结果
9. 明确说明后续需要更大群体的基因型和黄酮含量数据验证关联
10. 运行规则 QA，并把结果写入 `logs/qa_check.json`

已实现文件：

```text
src/breeding_agent/cli/flavonoid_markers.py
src/breeding_agent/workflows/flavonoid_marker_aggregation.py
src/breeding_agent/integration/flavonoid_marker_aggregator.py
src/breeding_agent/integration/flavonoid_marker_qa.py
src/breeding_agent/reports/flavonoid_marker_report.py
```

输出文件：

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

查看 QA 检查：

```bash
cat outputs/flavonoid_marker_from_package/logs/qa_check.json
```

QA 会检查三个固定基因、`群体`、`文献查阅`、`DOI`、`SNP`、`InDel`、`KASP`、`CAPS`、每个基因的统计学数值、文献 DOI 和标记类型推荐是否齐全。

## 10. 输出文件说明

package evidence 输出目录：

```text
outputs/flavonoid_marker_from_package/evidence/
```

已实现输出：

- `transcriptome_evidence.tsv`：目标基因表达和差异统计，包括 `baseMean`、`log2FC`、`pvalue`、`padj`、组均值和方向。
- `metabolome_evidence.tsv`：目标基因与代谢物网络和 sPLS 相关指标。
- `annotation_evidence.tsv`：Description、Preferred_name、KEGG、PFAM 等功能注释。
- `genome_variant_evidence.tsv`：第一版只写 `variant_status=not_called`，不写具体 SNP/InDel 位点。
- `literature_evidence.tsv`：文献查阅 seed evidence，包含 DOI。

文献查阅 seed DOI：

| DOI | relevance |
| --- | --- |
| `10.3390/life11060578` | flavonoid biosynthesis background and pathway interpretation |
| `10.3389/fpls.2021.665530` | candidate gene interpretation for flavonoid-related traits |
| `10.1007/978-1-4939-0446-4_7` | method reference for downstream flavonoid validation |
| `10.1134/S2079059716030114` | literature support for flavonoid candidate marker discussion |

文献查阅过程要求：

1. 先读取 `literature_evidence.tsv` 中的 seed DOI。
2. 人工或通过可靠文献数据库核验 DOI、题名、年份和研究内容。
3. 把核验后的文献与候选基因功能、通路和 marker 设计建议关联。
4. 未核验的 DOI 不得写成最终报告依据。
5. 不允许编造 DOI、题名或结论。

aggregation 输出目录：

```text
outputs/flavonoid_marker_from_package/
```

已实现 aggregation 输出：

- `integration/flavonoid_marker_candidates.tsv`：聚合三个重点基因的转录组统计值、代谢组相关性、功能注释、KEGG/pathway、variant_status 和 SNP/InDel/KASP/CAPS 推荐。
- `reports/flavonoid_marker_report.md`：中文 Markdown 推荐报告，包含固定核心结论、统计学数值、文献查阅 DOI、标记类型建议、后续验证方案和当前限制。
- `logs/qa_check.json`：纯规则 QA 结果。
- `manifest.json`：workflow 输入、输出、状态和 warning 摘要。

当前限制：

- aggregation 是规则版/模板版 workflow，不调用外部 API，不引入 Deep Agents 或 LangGraph。
- 文献 DOI 只来自 `literature_evidence.tsv` 或经过人工核验的输入，不伪造 DOI。
- 当前 mini 数据包没有最终 SNP/InDel calling 结果时，报告必须保留 `variant_status=not_called`。
- 不伪造 SNP/InDel 具体位点；后续应基于 BAM、`genome.fa/genome.gff` 或 `genome.bam_compatible.fa.gz` 与 `genome.original_coords.gff` 做候选区域 SNP/InDel calling，再筛选 KASP/CAPS 可转化位点。

## 11. 人工校验清单

运行 evidence 转换后，人工检查：

- `target_gene_evidence_summary.tsv` 是否存在。
- 三个目标基因是否都出现：`Si9g04210.1`、`Si5g31340.1`、`Si9g34380.1`。
- `transcriptome_evidence.tsv` 是否每个基因都有 `baseMean`、`log2FC`、`pvalue`、`padj`。
- `metabolome_evidence.tsv` 是否保留 top correlated metabolite 和 pearson r。
- `annotation_evidence.tsv` 是否保留 KEGG 和 PFAM。
- `genome_variant_evidence.tsv` 是否为 `variant_status=not_called`，且没有伪造 SNP/InDel 位点。
- `literature_evidence.tsv` 是否包含 DOI，且后续报告只使用核验过的 DOI。
- `logs/qa_check.json` 中 `passed` 是否为 `true`；如为 `false`，根据 `missing_items` 补齐报告或 evidence。
- 最终文本是否包含固定结论句：

```text
优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。
```

## 12. Git 安全流程

每次提交前运行：

```bash
git status --short
git diff --stat
```

如果改了 Python 文件，运行：

```bash
python3 -m py_compile <changed_python_files>
```

禁止提交：

- `data/private/`
- `outputs/`
- `*.bam`
- `*.bai`
- `*.fa`
- `*.fasta`
- `*.fa.gz`
- `*.fai`
- `*.gzi`
- 大型代谢组、基因组和中间结果文件

如果看到 `git status --short` 里出现 `data/` 或 `outputs/`，不要直接 `git add .`。应只选择需要提交的文档或代码文件。

## 13. Codex 开发注意事项

Codex 后续开发必须遵守：

- 不要修改现有 RNA-seq DEG workflow，除非任务明确要求。
- 不要修改 R 脚本，除非任务明确要求。
- 新增黄酮标记功能优先放在 `integration`、`reports`、`workflows`、`cli`、`scripts/demo`、`docs`。
- 不要把 flavonoid marker aggregation 逻辑塞进 `rnaseq_deg.py`。
- 不要伪造 SNP/InDel 位点。
- 不要伪造 DOI。
- 没有 variant calling 结果时，保持 `variant_status=not_called`。
- 已实现的 CLI 可以写“已实现”；没有实现的 CLI 必须写“计划中”或“待实现”。
- 修改后必须运行 `git status --short` 和 `git diff --stat`；如果修改 Python 文件，再运行 `python3 -m py_compile <changed_python_files>`。

## 14. 常见问题

### 为什么运行命令要写 `PYTHONPATH=src`？

当前项目没有发现 `pyproject.toml`、`setup.py` 或安装配置。直接运行模块时需要让 Python 找到 `src/breeding_agent`。

### 为什么用 `python3`？

当前环境里 `python` 命令可能不存在，`python3` 可用。文档和 AGENTS 中优先使用 `python3`。

### 为什么 `genome_variant_evidence.tsv` 不给 SNP/InDel 位点？

当前 mini 数据包没有最终 SNP/InDel call 结果表，也没有已筛选的 KASP/CAPS marker 位点。为保持可复现和诚实边界，第一版写 `variant_status=not_called`，后续再基于 BAM、`genome.bam_compatible.fa.gz` 和 `genome.original_coords.gff` 做候选区域 variant calling。

### 为什么 BAM 要配合 GFF 或 bam-compatible FASTA 使用？

BAM 的 reference naming 和坐标系统必须和 FASTA/GFF 兼容。`genome.bam_compatible.fa.gz` 更适合后续 BAM-based variant calling；`genome.original_coords.gff` 更适合解释原始基因注释和候选区域。坐标不一致会导致候选位点定位错误。

### flavonoid marker aggregation CLI 现在能运行吗？

能。先生成 evidence，再运行：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package
```

报告输出到 `outputs/flavonoid_marker_from_package/reports/flavonoid_marker_report.md`，QA 输出到 `outputs/flavonoid_marker_from_package/logs/qa_check.json`。

### 文献查阅现在完成了吗？

当前 evidence 中已有 seed DOI，并写入 `literature_evidence.tsv`。aggregation 报告会展示这些 DOI，并说明 workflow 不调用外部 API、不补写未核对 DOI。正式报告扩展时仍需要人工或可靠数据库核验 DOI、题名、年份和具体相关性，不能把未核验信息写成最终结论。
