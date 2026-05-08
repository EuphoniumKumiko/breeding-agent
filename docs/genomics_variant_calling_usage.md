# Genomics Candidate Variant Calling MVP 使用说明

## 模块定位

`genomics_variant_calling` 是一个独立的候选区域 SNP/InDel calling MVP。它基于学长 mini 数据包中的 BAM、reference genome 和 candidate regions，在候选区域内运行 `samtools` / `bcftools`，并把实际 VCF 中存在的位点整理为后续 KASP/CAPS 设计的候选表。

它不替代现有 `Genomics Region Module`。原有 `marker_readiness.tsv` 保持 `variant_status=not_called` 仍然是正确的，因为该文件表达的是 mini 数据包原始状态；本模块是一个新增的独立 calling workflow。

## 重要限制

- 当前结果来自候选区域 calling，不等同于 WGS 全基因组变异检测。
- 当前 BAM 很可能是 RNA-seq BAM，结果受表达区域、reads 覆盖、剪接比对和等位基因表达偏倚限制。
- 只有 `bcftools` 实际生成的 VCF 位点才会进入 `candidate_variants.tsv`。
- workflow 不伪造 SNP/InDel 位点。
- CAPS 表不会伪造酶切位点，只标记为需要后续 restriction enzyme screening。
- 后续仍需更大群体基因型和黄酮含量关联验证。

## 依赖工具

需要命令行环境中存在：

```text
samtools
bcftools
```

如果缺失，workflow 会清晰报错并建议安装，例如：

```bash
micromamba install -c bioconda samtools bcftools
```

## 默认输入

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
bam_dir = data/private/flavonoid_marker_mini_5genes_50kb/bam
reference_fasta = data/private/flavonoid_marker_mini_5genes_50kb/genome.bam_compatible.fa.gz
regions_bed = data/private/flavonoid_marker_mini_5genes_50kb/regions/regions.bed
gff = data/private/flavonoid_marker_mini_5genes_50kb/genome.original_coords.gff
outdir = outputs/genomics_variant_calling
```

如果 `genome.bam_compatible.fa.gz` 不存在，会尝试 `genome.fa`。

如果 `genome.original_coords.gff` 不存在，会尝试 `genome.gff`。

## CLI 用法

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 -m breeding_agent.cli.genomics_variants \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/genomics_variant_calling
```

可选参数：

```text
--bam-dir
--reference-fasta
--regions-bed
--gff
--outdir
```

## workflow 流程

1. 校验 `samtools` 和 `bcftools` 是否可用。
2. 校验 BAM、reference FASTA、regions BED 是否存在。
3. 如果 reference 没有 `.fai`，运行 `samtools faidx`。
4. 如果 BAM 没有 `.bai`，运行 `samtools index`。
5. 使用 `bcftools mpileup` 限定 `regions.bed` 进行 pileup。
6. 使用 `bcftools call` 生成 raw VCF。
7. 使用 `bcftools filter` 做基础 QUAL 过滤。
8. 从 filtered VCF 解析真实位点，写候选表。
9. 生成 Markdown 报告和 manifest。

## 输出文件

```text
outputs/genomics_variant_calling/
├── variants/
│   ├── candidate_regions.raw.vcf.gz
│   └── candidate_regions.filtered.vcf.gz
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

## candidate_variants.tsv 字段

至少包含：

- `chrom`
- `pos`
- `ref`
- `alt`
- `variant_type`
- `qual`
- `filter`
- `depth`
- `source_vcf`
- `nearest_or_target_gene`
- `marker_implication`

如果 VCF 中没有位点，该文件只包含表头，不会补造候选变异。

## KASP candidate 规则

第一版规则：

- 只有 SNP 进入 `kasp_candidate_sites.tsv`。
- 双等位 SNP 标记为 `preliminary`。
- 多等位 SNP 标记为 `not_recommended`。
- 所有 KASP candidate 都需要后续人工检查 flanking sequence。

## CAPS candidate 规则

第一版规则：

- 不推断具体限制性内切酶。
- 不伪造酶切位点。
- `caps_status` 写 `requires_restriction_enzyme_screening`。
- 后续需要检测该变异是否改变限制性内切酶识别位点。

## 报告内容

`genomics_variant_calling_report.md` 会说明：

- 输入文件。
- 使用的 samtools/bcftools 命令。
- 输出 VCF 和候选表。
- SNP/InDel 数量。
- 三个重点基因 `Si9g04210.1`、`Si5g31340.1`、`Si9g34380.1` 是否有 called variant 覆盖。
- 当前结果来自候选区域 calling，不等同于 WGS 全基因组变异检测。
- RNA-seq BAM 的覆盖限制。
- 后续仍需更大群体基因型和黄酮含量关联验证。

## 验证命令

语法检查：

```bash
python3 -m py_compile \
  src/breeding_agent/modules/genomics/variant_calling.py \
  src/breeding_agent/workflows/genomics_variant_calling.py \
  src/breeding_agent/reports/genomics_variant_report.py \
  src/breeding_agent/cli/genomics_variants.py
```

单元测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

真实 calling，如果本地安装了 `samtools` 和 `bcftools`：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.genomics_variants \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/genomics_variant_calling
```

## 和现有模块的关系

- 不修改 RNA-seq DEG workflow。
- 不修改 R workflow。
- 不修改现有 Genomics Region Module。
- 不修改 Flavonoid Marker Recommendation workflow。
- 新增输出默认写到 `outputs/genomics_variant_calling/`，不要提交该目录。
