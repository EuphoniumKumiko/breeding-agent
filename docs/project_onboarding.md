# breeding-agent 项目上手文档

## 1. 项目定位

`breeding-agent` 是一个面向作物多组学育种分析的可复现项目。当前项目的研究作物是谷子，已经从 RNA-seq DEG workflow 扩展到黄酮候选标记推荐、候选区域 variant calling、规则化智能体聚合、LangGraph 编排、Deep Agents POC、Gradio 展示和 Promoter Design scaffold。

当前核心定位：

- 已实现：RNA-seq 差异表达分析、结果报告、标准 transcriptomics evidence、候选基因表和第一版 recommendation report。
- 已实现：从学长谷子黄酮标记 mini 数据包生成 aggregation evidence 的 demo 转换脚本。
- 已实现：flavonoid marker aggregation CLI，采用规则版 workflow + DeepRare-like lightweight agent layer，整合 transcriptome、metabolome、annotation、genome variant 和 literature evidence，给出 SNP/InDel/KASP/CAPS 等可开发标记类型建议，并输出 QA 检查结果。
- 已实现：LangGraph 版 flavonoid marker workflow，把现有规则化 agents 作为 graph nodes 编排；LangGraph 是当前主线开源智能体编排框架，也是可选依赖，不影响旧 CLI。
- 已实现：本地 OpenAI-compatible LLM ReviewerAgent 可选增强，只接入 LangGraph workflow 的 reviewer node；默认不调用模型，失败或 guard 不通过时回退到规则版 ReviewerAgent。
- 已实现：Deep Agents POC，复用现有 evidence、context builder 和规则化 agents，输出 trace/summary/decision table；它是并行 POC，不替代 LangGraph。
- 已实现：Promoter Design scaffold，包含任务定义、schema、数据盘点、workflow/CLI 占位输出；它不训练模型，不生成真实启动子序列。
- 已实现：Genomics Candidate Variant Calling MVP，基于候选区域运行 `samtools`/`bcftools`，输出真实 VCF 中存在的 SNP/InDel、KASP preliminary screening 和 CAPS screening 表。
- 已实现：Gradio 顶部 `gr.Tab` 工作台，包含 Transcriptomics、Metabolomics、Genomics / GWAS、Integration & Recommendation 和谷子黄酮候选标记推荐 Tab；其中 Genomics / GWAS 可展示 Candidate Variant Calling MVP，黄酮 Tab 可展示 LangGraph workflow 输出。
- 禁止事项：不能伪造 SNP/InDel 位点，不能伪造 DOI，不能伪造启动子序列，不能把 `data/private/` 和 `outputs/` 中的数据加入 Git。

新人应优先阅读 `README.md`、本文档、`AGENTS.md` 和 `docs/flavonoid_marker_package_import.md`。

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
- lightweight agents：`src/breeding_agent/agents/`
- aggregator：`src/breeding_agent/integration/flavonoid_marker_aggregator.py`
- QA：`src/breeding_agent/integration/flavonoid_marker_qa.py`
- report：`src/breeding_agent/reports/flavonoid_marker_report.py`
- LangGraph workflow：`src/breeding_agent/workflows/flavonoid_marker_langgraph.py`
- LangGraph CLI：`src/breeding_agent/cli/flavonoid_markers_graph.py`
- LangGraph graph：`src/breeding_agent/graphs/flavonoid_marker_graph.py`
- LangGraph trace reports：`src/breeding_agent/reports/langgraph_trace_report.py`
- 本地 LLM adapter：`src/breeding_agent/llm/`
- Deep Agents POC CLI：`src/breeding_agent/cli/flavonoid_markers_deepagents.py`
- Deep Agents POC workflow：`src/breeding_agent/workflows/flavonoid_marker_deepagents.py`
- Deep Agents POC backend：`src/breeding_agent/deepagents/flavonoid_deepagents_poc.py`
- Promoter Design CLI：`src/breeding_agent/cli/promoter_design.py`
- Promoter Design workflow：`src/breeding_agent/workflows/promoter_design.py`
- Promoter Design schema：`src/breeding_agent/modules/promoter/promoter_task_schema.py`

已实现的 Gradio 多组学模块：

- 代谢组后端：`src/breeding_agent/modules/metabolomics/metabolomics_evidence.py`
- 代谢组 workflow：`src/breeding_agent/workflows/metabolomics_evidence.py`
- 代谢组报告：`src/breeding_agent/reports/metabolomics_report.py`
- 基因组后端：`src/breeding_agent/modules/genomics/genomics_region.py`
- 基因组 workflow：`src/breeding_agent/workflows/genomics_region.py`
- 基因组报告：`src/breeding_agent/reports/genomics_report.py`
- 候选区域变异 calling CLI：`src/breeding_agent/cli/genomics_variants.py`
- 候选区域变异 calling workflow：`src/breeding_agent/workflows/genomics_variant_calling.py`
- 候选区域变异 calling 报告：`src/breeding_agent/reports/genomics_variant_report.py`
- Gradio 使用说明：`docs/gradio_omics_modules_usage.md`

## 3. 目录结构速览

```text
src/breeding_agent/
├── agents/
│   ├── flavonoid_central_host.py
│   ├── flavonoid_literature_agent.py
│   ├── flavonoid_marker_recommendation_agent.py
│   ├── flavonoid_validation_agent.py
│   ├── flavonoid_reviewer_agent.py
│   └── flavonoid_final_qa_agent.py
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

当前状态：已实现，当前形态为规则版 workflow + DeepRare-like lightweight agent layer。

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
7. 通过 `FlavonoidLiteratureAgent` 生成文献查阅过程并原样展示 DOI
8. 通过 `FlavonoidMarkerRecommendationAgent` 输出 marker 类型建议，例如 SNP/InDel/KASP/CAPS
9. 通过 `FlavonoidValidationAgent` 输出后续 Sanger、SNP/InDel calling、KASP、CAPS/dCAPS、群体关联、qRT-PCR 和 LC-MS/MS 验证方案
10. 通过 `FlavonoidReviewerAgent` 检查过度推断、缺失统计值、缺失 DOI、缺失验证方案和疑似伪造 variant 位点
11. 通过 `FlavonoidFinalQAAgent` 复用现有规则 QA，并把结果写入 `logs/qa_check.json`

已实现文件：

```text
src/breeding_agent/agents/flavonoid_central_host.py
src/breeding_agent/agents/flavonoid_literature_agent.py
src/breeding_agent/agents/flavonoid_marker_recommendation_agent.py
src/breeding_agent/agents/flavonoid_validation_agent.py
src/breeding_agent/agents/flavonoid_reviewer_agent.py
src/breeding_agent/agents/flavonoid_final_qa_agent.py
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

- 默认 aggregation 是规则版/模板版 workflow + DeepRare-like lightweight agent layer，不调用 LLM，不调用外部 API，也不依赖 LangGraph 或 Deep Agents。
- LangGraph workflow 是当前主线开源智能体编排入口；旧 workflow 和旧 CLI 不依赖 LangGraph。
- LangGraph workflow 可选启用本地 OpenAI-compatible ReviewerAgent 审阅增强；该增强只作用于 reviewer node，失败、空响应或 guard 不通过时自动回退到规则版 ReviewerAgent。
- Deep Agents POC 已完成并可作为并行入口运行，但不替代 LangGraph。
- 文献 DOI 只来自 `literature_evidence.tsv` 或经过人工核验的输入，不伪造 DOI。
- 当前 mini 数据包没有最终 SNP/InDel calling 结果时，报告必须保留 `variant_status=not_called`。
- 不伪造 SNP/InDel 具体位点；后续应基于 BAM、`genome.fa/genome.gff` 或 `genome.bam_compatible.fa.gz` 与 `genome.original_coords.gff` 做候选区域 SNP/InDel calling，再筛选 KASP/CAPS 可转化位点。
- 如果已经运行 Genomics Candidate Variant Calling MVP，可通过 `--variant-calling-dir outputs/genomics_variant_calling` 把真实 `candidate_variants.tsv`、`kasp_candidate_sites.tsv`、`caps_candidate_sites.tsv` 可选接入黄酮推荐报告。
- 可选 variant evidence 接入后会展示 PASS/LowQual、SNP/InDel、KASP/CAPS preliminary screening 统计；LowQual 不应直接优先用于 KASP/CAPS，preliminary screening 不等同于最终标记设计。
- 当前候选区域 calling 如果基于 RNA-seq BAM，不能替代 WGS/GBS 群体变异检测。
- 后续如果需要扩展更多 LLM 节点，应通过明确 adapter 接入，并保留当前规则 fallback。

带可选 variant calling evidence 的 flavonoid marker CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package \
  --variant-calling-dir outputs/genomics_variant_calling
```

并行 LangGraph flavonoid marker CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph \
  --variant-calling-dir outputs/genomics_variant_calling
```

启用本地 LLM ReviewerAgent 审阅增强的 LangGraph CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_llm \
  --variant-calling-dir outputs/genomics_variant_calling \
  --use-llm-reviewer \
  --llm-config configs/llm.local.example.yaml
```

并行 Deep Agents POC CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_deepagents \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_deepagents \
  --variant-calling-dir outputs/genomics_variant_calling
```

Deep Agents 输出包括：

```text
outputs/flavonoid_marker_deepagents/
├── deepagents/
│   ├── deepagents_trace.json
│   ├── deepagents_summary.md
│   └── deepagents_decision_table.tsv
├── integration/flavonoid_marker_candidates.tsv
├── reports/flavonoid_marker_report.md
├── logs/qa_check.json
└── manifest.json
```

如未安装 LangGraph，安装方式：

```bash
pip install langgraph
```

LangGraph 输出包括：

```text
outputs/flavonoid_marker_langgraph/
├── graph/
│   ├── graph_trace.json
│   ├── graph_state_final.json
│   ├── node_decision_table.tsv
│   └── langgraph_summary.md
├── integration/flavonoid_marker_candidates.tsv
├── reports/flavonoid_marker_report.md
├── logs/qa_check.json
└── manifest.json
```

为什么先接 LangGraph，而不是先接开源本地大模型：当前优先稳定 node/state/trace 的可复现编排边界；真实模型会引入不可复现输出、部署依赖和伪造 DOI/SNP/InDel 风险。Deep Agents POC 已作为并行 harness 验证入口，但本地开源大模型接入仍是下一阶段。

## 11. Genomics Candidate Variant Calling MVP

当前已实现独立候选区域 SNP/InDel calling MVP：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.genomics_variants \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/genomics_variant_calling
```

该 workflow 使用已有 Python 后端调用 `samtools` 和 `bcftools`，不会在 Gradio 或文档层重新实现 calling 命令。若工具缺失，CLI/Gradio 会给出安装提示。默认输出：

```text
outputs/genomics_variant_calling/
├── tables/
│   ├── candidate_variants.tsv
│   ├── snp_candidates.tsv
│   ├── indel_candidates.tsv
│   ├── kasp_candidate_sites.tsv
│   └── caps_candidate_sites.tsv
├── reports/
│   └── genomics_variant_calling_report.md
├── logs/
│   └── run.log
└── manifest.json
```

质量分层：

- PASS variants can be prioritized for downstream marker review（PASS 位点可优先进入后续标记开发复核）。
- LowQual variants are retained for traceability but should not be directly prioritized（LowQual 位点仅作为可追溯候选记录保留，不应直接优先用于标记开发）。
- This result does not replace WGS/GBS population variant calling（当前结果不能替代 WGS/GBS 群体变异检测）。
- KASP/CAPS 表只是 preliminary screening，不是最终引物或酶切方案。

该输出可通过 `--variant-calling-dir outputs/genomics_variant_calling` 可选接入黄酮标记推荐报告。接入后报告展示三个固定基因的 `variant_evidence_status`、PASS/LowQual、SNP/InDel、KASP preliminary screening 和 CAPS screening 统计。如果某个基因是 `no_called_variant_in_current_mini_calling`，不能写成已有 called variant。

## 12. 人工校验清单

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

## 13. Gradio 页面查看谷子黄酮标记推荐结果

当前 `src/breeding_agent/web/gradio_app.py` 使用顶部 `gr.Tab` 布局，页面标题为 `Agri Multi-omics Breeding Agent Demo`。当前真实存在的 Tab 包括 `Transcriptomics DEG Module`、`Metabolomics Module`、`Genomics / GWAS Module`、`Integration & Recommendation` 和 `谷子黄酮候选标记推荐`。文档应以这个 Tab 结构为准，不再描述为左侧 sticky 导航、单页 dashboard 或 Radio 模块切换。

普通启动方式：

```bash
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

开发热重载启动方式：

```bash
GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 PYTHONPATH=src gradio src/breeding_agent/web/gradio_app.py
```

浏览器访问：

```text
http://127.0.0.1:7860
```

如果虚拟机或 shell 代理导致 localhost 502、页面加载失败或 websocket 异常，可以临时执行：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY=localhost,127.0.0.1,0.0.0.0
export no_proxy=localhost,127.0.0.1,0.0.0.0
```

从宿主机访问虚拟机服务时，也可以把虚拟机 IP 加入 `NO_PROXY/no_proxy`。

该页面保留原 RNA-seq DEG demo。`Transcriptomics DEG Module` 调用现有 RNA-seq DEG workflow，展示 significant genes、report、manifest 和 run log。

`Metabolomics Module` 默认读取 `data/private/flavonoid_marker_mini_5genes_50kb`，输出到 `outputs/gradio_metabolomics_run/metabolomics/`，展示 `candidate_metabolites.tsv`、`flavonoid_related_significant_metabolites.tsv`、`target_gene_metabolite_network_edges.tsv`、`target_gene_spls_coefficients.tsv`、`metabolomics_report.md` 和 `manifest.json`。该模块当前是基于学长数据包已有结果表的 evidence analysis，不是从 mzML/raw 或原始峰表重新做完整代谢组统计流程。

`Genomics / GWAS Module` 默认读取同一学长数据包，输出到 `outputs/gradio_genomics_run/genomics/`，展示 `target_gene_regions.tsv`、`annotation_summary.tsv`、`marker_readiness.tsv`、`genomics_report.md` 和 `manifest.json`。Region analysis 仍只做基于已有结果表的 region / annotation analysis，`marker_readiness.tsv` 中三个重点基因的 `variant_status` 固定为 `not_called`，不伪造 SNP/InDel 位点。

同一 Tab 还包含 `Candidate Variant Calling（候选区域变异检测）` 小节。默认 `dataset_dir=data/private/flavonoid_marker_mini_5genes_50kb`、`variant_calling_outdir=outputs/genomics_variant_calling`。点击 `Run Variant Calling` 会调用已有 Genomics Candidate Variant Calling workflow；点击 `Refresh Variant Results` 只读取已有 `outputs/genomics_variant_calling` 结果。页面展示 `Variant Quality Summary`、五个候选表、`genomics_variant_calling_report.md`、`manifest.json` 和 `run.log`。如果结果不存在，页面提示先运行 `Run Variant Calling`。

`Integration & Recommendation` Tab 当前主要读取 `outputs/gradio_demo_run` 下已有 DEG integration 输出，展示 standardized evidence、candidate gene table、recommendation report、current transcriptomics report 和 provenance 信息；不要把它描述为完整多组学自动整合 workflow。

`谷子黄酮候选标记推荐` Tab 支持生成 evidence、运行标记推荐、一键运行完整流程和刷新已有结果，并展示 `flavonoid_marker_candidates.tsv`、`flavonoid_marker_report.md`、`qa_check.json` 和 `manifest.json`。该 Tab 新增可选 `variant_calling_dir`，默认 `outputs/genomics_variant_calling`；目录存在时接入 candidate variant calling evidence，留空或目录不存在时保持原流程。页面只接受服务器本地路径，不上传 BAM/FASTA 大文件。

同一 Tab 还包含 `LangGraph Multi-agent Workflow（LangGraph 多智能体聚合流程）` 小节。默认 `langgraph_outdir=outputs/flavonoid_marker_langgraph`。点击 `Run LangGraph Workflow` 会调用已有 LangGraph workflow；点击 `Refresh LangGraph Results` 只读取已有 graph 输出。页面展示 `graph/langgraph_summary.md`、`graph/node_decision_table.tsv`、最终报告，以及 Details 中的 `graph_trace.json`、`graph_state_final.json`、`qa_check.json`、`manifest.json`。

该小节还包含 `Use LLM Reviewer`、`LLM Config Path` 和 `LLM Reviewer Status`。`Use LLM Reviewer` 默认关闭；勾选后只增强 ReviewerAgent，并把 `LLM Config Path` 作为路径参数传给 LangGraph workflow。Gradio 不读取或展示 LLM config 文件内容。状态框展示 `llm_reviewer_enabled`、`llm_used`、`fallback_used`、`model`、`guard_passed` 和 `fallback_reason`。本地 LLM 不直接生成 SNP/InDel/KASP/CAPS 结论；输出仍经过 output_guard 和 FinalQAAgent，不通过会 fallback 到规则版 ReviewerAgent。Deep Agents POC 已作为并行 CLI/workflow 跑通，但当前未接入 Gradio，且不替代 LangGraph。

Gradio 是展示层和本地 workflow 触发入口，不改变后端 workflow 分析逻辑。当前 candidate variant calling 和 LangGraph workflow 结果不能替代 WGS/GBS 群体变异检测；KASP/CAPS 表仍是 preliminary screening，不是最终引物或酶切方案。`data/private/` 和 `outputs/` 不应提交 Git。

## 14. Git 安全流程

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

## 15. Codex 开发注意事项

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

## 16. 常见问题

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

## Promoter Design Module 后续扩展

Promoter Design Module 是后续设计型任务扩展，用于承接“输入基因序列和基因功能，输出启动子序列及使用方法”的新任务。当前实现仅是 scaffold：定义输入/输出、数据盘点和占位 workflow，不训练模型、不调用真实大模型、不调用外部 API、不伪造启动子序列，也不输出可直接实验使用的 synthetic promoter。该模块不影响现有谷子黄酮候选标记推荐主线；未来可在高可信 promoter activity 数据集、motif annotation、activity predictor 和实验验证体系明确后，再作为独立 workflow 或 LangGraph / Deep Agents node 接入。

运行 scaffold 示例：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.promoter_design \
  --gene-id Si9g04210.1 \
  --gene-sequence ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC \
  --gene-function "flavonoid-related candidate gene" \
  --species foxtail_millet \
  --target-expression-level high \
  --outdir outputs/promoter_design_demo
```
