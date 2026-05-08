# Gradio 多组学模块使用说明

## 当前状态

Gradio 页面中的以下模块已不再是 placeholder：

- `Metabolomics Module`
- `Genomics / GWAS Module`

当前第一版只读取学长 mini 数据包中已有结果表，做 evidence analysis / region analysis。它不做完整原始代谢组统计流程，不做正式 SNP/InDel calling，不伪造 SNP/InDel 位点，也不调用外部 API。

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

## Metabolomics Module

默认输入：

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
outdir = outputs/gradio_metabolomics_run
```

页面按钮：

- `Load Demo Metabolomics`：填入默认本地路径。
- `Run Metabolomics Evidence Analysis`：读取数据包内已有代谢组结果表并生成报告。

默认读取：

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

输出：

```text
outputs/gradio_metabolomics_run/metabolomics/
├── candidate_metabolites.tsv
├── flavonoid_related_significant_metabolites.tsv
├── target_gene_metabolite_network_edges.tsv
├── target_gene_spls_coefficients.tsv
├── metabolomics_report.md
└── manifest.json
```

报告会说明候选黄酮代谢物、显著黄酮相关代谢物、目标基因-代谢物相关网络、sPLS 证据，以及与 `Si9g04210.1`、`Si5g31340.1`、`Si9g34380.1` 的关系。

## Genomics / GWAS Module

默认输入：

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
outdir = outputs/gradio_genomics_run
```

页面按钮：

- `Load Demo Genomics`：填入默认本地路径。
- `Run Genomics Region Analysis`：读取数据包内已有区域、注释和目标基因表并生成报告。

默认读取：

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

输出：

```text
outputs/gradio_genomics_run/genomics/
├── target_gene_regions.tsv
├── annotation_summary.tsv
├── marker_readiness.tsv
├── genomics_report.md
└── manifest.json
```

`marker_readiness.tsv` 固定包含三个重点基因：

```text
Si9g04210.1
Si5g31340.1
Si9g34380.1
```

第一版不输出具体 SNP/InDel 坐标，`variant_status` 必须为：

```text
not_called
```

报告会明确说明：当前 mini 数据包未提供最终 SNP/InDel 位点；后续需要基于 BAM、`genome.fa/genome.gff` 或 `genome.bam_compatible.fa.gz` 与 `genome.original_coords.gff` 进行候选区域 SNP/InDel calling，再筛选 KASP/CAPS 可转化位点。

## 缺文件行为

两个模块遇到部分输入文件缺失时不会直接崩溃。workflow 会：

- 在 `manifest.json` 中记录 warning。
- 在页面 status 中展示 warning。
- 对缺失的输出表写出只有表头的 TSV，方便页面继续渲染。

## 数据安全

页面只接收服务器本地路径，不上传 BAM、FASTA、代谢组大表或其他私有数据。不要把 `data/private/` 或 `outputs/` 加入 Git。
