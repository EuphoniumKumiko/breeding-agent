# 谷子黄酮标记 mini 数据包导入说明

## 数据包是什么

学长提供的 `flavonoid_marker_mini_5genes_50kb` 是一个谷子黄酮标记 mini 数据和预处理结果包。它用于演示如何把转录组、代谢组、注释和候选变异相关输入整理成 flavonoid marker aggregation 可以读取的 evidence 文件。

这个包不是脚本包，也不是完整自动分析 pipeline。包内主要包含：

- mini BAM 文件
- genome FASTA / GFF 注释
- 目标基因列表
- 代谢组原始表和目标基因相关代谢物结果
- eggNOG / KEGG / PFAM 等注释结果
- 已整理的 `annotations/target_gene_evidence_summary.tsv`

当前转换脚本只读取 `annotations/target_gene_evidence_summary.tsv`，其他文件用于 provenance、后续 SNP/InDel calling 或人工复核。

## 解压到 data/private

建议把压缩包解压到项目内的私有数据目录：

```bash
cd ~/projects/breeding-agent
mkdir -p data/private
tar -xf /path/to/flavonoid_marker_mini_5genes_50kb.tar.gz -C data/private/
```

解压后目录应类似：

```text
data/private/flavonoid_marker_mini_5genes_50kb/
├── bam/
├── metabolome/
├── transcriptome/
├── annotations/
├── genome.fa
├── genome.gff
├── genome.original_coords.gff
├── genome.bam_compatible.fa.gz
├── sample_metadata.tsv
└── target_genes.tsv
```

不要把 `data/private/` 下的数据加入 Git。该目录用于本地私有数据和较大的 demo 输入文件。

## 生成 aggregation evidence

运行转换脚本：

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python scripts/demo/create_flavonoid_marker_evidence_from_package.py \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/flavonoid_marker_from_package/evidence
```

脚本会读取：

```text
data/private/flavonoid_marker_mini_5genes_50kb/annotations/target_gene_evidence_summary.tsv
```

并固定输出三个重点基因：

```text
Si9g04210.1
Si5g31340.1
Si9g34380.1
```

输出文件：

```text
outputs/flavonoid_marker_from_package/evidence/
├── transcriptome_evidence.tsv
├── metabolome_evidence.tsv
├── annotation_evidence.tsv
├── genome_variant_evidence.tsv
└── literature_evidence.tsv
```

如果 `target_gene_evidence_summary.tsv` 不存在，脚本会直接报错并退出。其他包内文件缺失时只打印 warning，因为第一版 evidence 转换不直接读取这些文件。

## 接着运行 flavonoid marker aggregation CLI

转换完成后，后续 flavonoid marker aggregation CLI 应读取上一步生成的 evidence 目录。例如建议的调用形式：

```bash
PYTHONPATH=src python -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package/aggregation
```

如果当前分支尚未实现 `breeding_agent.cli.flavonoid_markers`，请先实现 aggregation CLI，再使用上述 evidence 文件作为标准输入。

## BAM、GFF 和 bam-compatible FASTA 的关系

BAM 文件中的参考序列名称必须和后续调用使用的参考 FASTA / 注释坐标系统兼容。这个 mini 包同时提供：

- `genome.original_coords.gff`
- `genome.bam_compatible.fa.gz`
- `bam/*.mini.sorted.bam`

`genome.original_coords.gff` 保留原始注释坐标，适合解释目标基因、区域和注释来源。`genome.bam_compatible.fa.gz` 用于和 BAM 的 reference naming / indexing 保持一致，适合后续基于 BAM 的候选区域 SNP/InDel calling。

如果 BAM、FASTA 和 GFF 的染色体名称或坐标系统不一致，变异检测、候选区域筛选和 marker 转化都会产生错误定位。因此后续做 SNP/InDel calling 时，应明确使用与 BAM 兼容的参考序列，并用原始坐标 GFF 做基因和区域解释。

## 为什么 package evidence 不伪造 SNP/InDel 位点

当前 mini 数据包本身没有提供最终 SNP/InDel call 结果表，也没有提供已经筛选好的 KASP/CAPS marker 位点。为了保持 workflow 可复现，package evidence 转换生成的 `genome_variant_evidence.tsv` 对每个目标基因写入：

```text
variant_status = not_called
```

后续已经有独立的 Genomics Candidate Variant Calling MVP，可基于 BAM、`genome.bam_compatible.fa.gz` 和 `genome.original_coords.gff` 生成 `candidate_variants.tsv`、KASP preliminary screening 和 CAPS screening 表，并通过 `--variant-calling-dir outputs/genomics_variant_calling` 可选接入黄酮推荐报告。

这样做可以避免把 package evidence 中不存在的位点写成正式 marker evidence，也能让报告清楚区分“已有多组学候选证据”和“已通过独立 candidate variant calling 接入的真实候选位点”。即使接入 variant calling，KASP/CAPS 表仍是 preliminary screening，不是最终实验方案。
