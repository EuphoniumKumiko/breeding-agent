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

该 Tab 基于已有 genome、GFF、regions、annotation 和 target genes 表做 region / marker-readiness analysis。它不做正式 SNP/InDel calling，不输出最终 SNP/InDel 坐标。

### 输入

默认输入：

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
outdir = outputs/gradio_genomics_run
```

### 按钮

- `Load Demo Genomics`
- `Run Genomics Region Analysis`

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

该 Tab 用于生成 flavonoid marker evidence、运行 aggregation、查看候选表、报告、QA 和 manifest。详细说明见：

```text
docs/gradio_flavonoid_marker_usage.md
```

## 数据安全和限制

- Gradio 页面只接收服务器本地路径，不上传 BAM、FASTA 或代谢组大表。
- Gradio 是展示层和 workflow 触发入口，不改变后端 workflow 的分析逻辑。
- `data/private/` 和 `outputs/` 不应提交 Git。
- Metabolomics Module 当前不是完整原始质谱重分析。
- Genomics / GWAS Module 当前不做正式 SNP/InDel calling。
- `variant_status=not_called` 表示没有最终变异位点，不能伪造 SNP/InDel 坐标。
- 后续仍需要候选区域 variant calling 和更大群体验证。
