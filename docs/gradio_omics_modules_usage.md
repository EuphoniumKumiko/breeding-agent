# Gradio 多组学模块使用说明

本文档以当前 `src/breeding_agent/web/gradio_app.py` 的实际代码为准。当前 Gradio 页面使用顶部 `gr.Tab` 布局，页面标题为：

```text
Agri Multi-omics Breeding Agent Demo
```

当前不是左侧 sticky 导航，不是单页纵向 dashboard，也不是 Radio 模块切换。

## 启动 Gradio

普通启动：

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

开发热重载启动：

```bash
cd ~/projects/breeding-agent
GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 PYTHONPATH=src gradio src/breeding_agent/web/gradio_app.py
```

浏览器访问：

```text
http://127.0.0.1:7860
```

如遇 localhost 502、页面加载失败或代理相关问题，可先在当前 shell 中执行：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY=localhost,127.0.0.1,0.0.0.0
export no_proxy=localhost,127.0.0.1,0.0.0.0
```

如果从宿主机访问虚拟机中的服务，也可以把虚拟机 IP 加入 `NO_PROXY/no_proxy`。

## 当前 Tab 列表

当前 Gradio 页面包含：

1. `Transcriptomics DEG Module`
2. `Metabolomics Module`
3. `Genomics / GWAS Module`
4. `Integration & Recommendation`
5. `谷子黄酮候选标记推荐`

以下分别说明各 Tab 的真实输入、按钮和输出。

## Transcriptomics DEG Module

该 Tab 调用现有 RNA-seq DEG workflow：

```text
src/breeding_agent/workflows/rnaseq_deg.py
```

### 输入

页面输入包括：

- `trait_selection`
- `BAM directory`
- `GFF annotation`
- `optional_file`
- `threads`

页面还显示高级默认值：

```text
contrast = JM-LM
prefix = JM_vs_LM.mini
outdir = outputs/gradio_demo_run
```

### 按钮

- `Load Demo Benchmark`
- `Run Transcriptomics Analysis`

### 输出

页面展示：

- `status`
- `significant_genes`
- `recommendation_report.md / report.md`
- `manifest.json`
- `run.log`

该 Tab 会真正调用 RNA-seq DEG workflow，因此需要本地 BAM、GFF、featureCounts、Rscript 和 R 依赖可用。

## Metabolomics Module

该 Tab 基于学长 mini 数据包中已有代谢组结果表做 evidence analysis，不是从 mzML/raw 或原始质谱峰表重新做完整代谢组统计流程。

### 输入

默认输入：

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
outdir = outputs/gradio_metabolomics_run
```

### 按钮

- `Load Demo Metabolomics`
- `Run Metabolomics Evidence Analysis`

### 默认读取文件

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

### 输出

页面展示：

- `status`
- `candidate_metabolites.tsv`
- `flavonoid_related_significant_metabolites.tsv`
- `target_gene_metabolite_network_edges.tsv`
- `target_gene_spls_coefficients.tsv`
- `metabolomics_report.md`
- `manifest.json`

默认输出目录：

```text
outputs/gradio_metabolomics_run/metabolomics/
```

## Genomics / GWAS Module

该 Tab 保留已有 genome、GFF、regions、annotation 和 target genes 表的 region / marker-readiness analysis，并新增 `Candidate Variant Calling（候选区域变异检测）` 小节用于展示 Genomics Candidate Variant Calling MVP。Gradio 只负责触发已有 workflow 或读取已有输出，不重新实现 `samtools`/`bcftools` calling 逻辑。

### 输入

默认输入：

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
outdir = outputs/gradio_genomics_run
```

### 按钮

- `Load Demo Genomics`
- `Run Genomics Region Analysis`
- `Load Demo Variant Calling`
- `Run Variant Calling`
- `Refresh Variant Results`

### 默认读取文件

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

### 输出

页面展示：

- `status`
- `target_gene_regions.tsv`
- `annotation_summary.tsv`
- `marker_readiness.tsv`
- `genomics_report.md`
- `manifest.json`

默认输出目录：

```text
outputs/gradio_genomics_run/genomics/
```

`marker_readiness.tsv` 中三个重点基因的 `variant_status` 固定为：

```text
not_called
```

含义：当前 mini 数据包未提供最终 SNP/InDel calling 结果，页面不能输出具体 SNP/InDel 坐标。后续需要基于候选区域进行 variant calling，再筛选 KASP/CAPS 可转化位点。

### Candidate Variant Calling 输入

默认输入：

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
variant_calling_outdir = outputs/genomics_variant_calling
```

`Run Variant Calling` 调用已有 `run_genomics_variant_calling_task()` workflow。若本地没有 `samtools` 或 `bcftools`，页面会在 `Run Status` 中显示清晰错误，不会 traceback 崩溃。

`Refresh Variant Results` 只读取 `outputs/genomics_variant_calling` 下已有结果，不重新运行 calling。如果结果尚不存在，页面提示：

```text
尚未生成 candidate variant calling 结果，请先运行 Run Variant Calling。
```

### Candidate Variant Calling 输出

页面展示：

- `Run Status`
- `Variant Quality Summary`
- `candidate_variants.tsv`
- `snp_candidates.tsv`
- `indel_candidates.tsv`
- `kasp_candidate_sites.tsv`
- `caps_candidate_sites.tsv`
- `genomics_variant_calling_report.md`
- `manifest.json`
- `run.log`

对应输出目录：

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

`Variant Quality Summary` 展示 `candidate_variants`、`snps`、`indels`、`pass_variants`、`lowqual_variants`、`pass_snps`、`lowqual_snps`、`pass_indels`、`lowqual_indels`、`kasp_preliminary_pass`、`kasp_low_quality_review_required`、`caps_pass_variant_requires_enzyme_screening` 和 `caps_low_quality_variant_requires_review`。

质量分层含义：

- PASS variants can be prioritized for downstream marker review（PASS 位点可优先进入后续标记开发复核）。
- LowQual variants are retained for traceability but should not be directly prioritized（LowQual 位点仅作为可追溯候选记录保留，不应直接优先用于标记开发）。
- This result does not replace WGS/GBS population variant calling（当前结果不能替代 WGS/GBS 群体变异检测）。
- KASP/CAPS 表只是 preliminary screening，不是最终引物或酶切方案。

## Integration & Recommendation

该 Tab 当前是已有 DEG integration 输出的展示/汇总入口，不是完整多组学自动整合 workflow。

按钮：

```text
Generate Recommendation
```

当前回调读取默认 DEG Gradio 输出目录：

```text
outputs/gradio_demo_run
```

页面展示：

- `standardized_evidence.tsv`
- `candidate_gene_table.tsv`
- `Recommendation Report`
- `Current Transcriptomics Report`
- `Provenance / Reproducibility`

如果还没有先运行 `Transcriptomics DEG Module`，页面会提示先生成 standardized evidence 或 candidate gene table。

## 谷子黄酮候选标记推荐

该 Tab 用于生成 flavonoid marker evidence、运行 aggregation、查看候选表、报告、QA 和 manifest。当前也可展示并触发 LangGraph 多智能体聚合流程：

- `Run LangGraph Workflow`：调用现有 LangGraph workflow。
- `Refresh LangGraph Results`：只读取 `outputs/flavonoid_marker_langgraph` 下已有输出。
- 页面展示 `graph/langgraph_summary.md`、`graph/node_decision_table.tsv`、`graph/graph_trace.json`、`graph/graph_state_final.json`、最终报告、QA 和 manifest。

LangGraph 当前只编排现有规则化 agents，不调用真实 LLM。Deep Agents POC 已作为并行 CLI/workflow 跑通，但当前未接入 Gradio，且不替代 LangGraph；本地开源大模型仍是下一阶段规划。详细说明见：

```text
docs/gradio_flavonoid_marker_usage.md
```

## 数据安全和限制

- Gradio 页面只接收服务器本地路径，不上传 BAM、FASTA 或代谢组大表。
- Gradio 是展示层和 workflow 触发入口，不改变后端 workflow 的分析逻辑。
- `data/private/` 和 `outputs/` 不应提交 Git。
- Metabolomics Module 当前不是完整原始质谱重分析。
- `variant_status=not_called` 表示没有最终变异位点，不能伪造 SNP/InDel 坐标。
- Genomics Candidate Variant Calling MVP 是候选区域 calling 展示，不替代 WGS/GBS 群体变异检测。
- LangGraph workflow 结果同样不能替代 WGS/GBS 群体变异检测；KASP/CAPS 表仍是 preliminary screening，不是最终引物或酶切方案。
- 后续仍需要更大群体基因型和黄酮含量数据验证关联。
