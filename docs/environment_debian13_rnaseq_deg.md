# Debian 13 RNA-seq DEG 环境与复现记录

## 1. 环境信息

- Host OS: Windows
- Virtualization: VMware Workstation Pro
- Guest OS: Debian 13 stable
- Conda manager: micromamba
- Environment name: rnaseq_deg
- Threads: 4

## 2. 软件版本

```bash
python --version
samtools --version
featureCounts -v
Rscript --version

## 3. 核心命令
THREADS=4 bash scripts/rerun_packaged_mini_from_bam.sh

## 4. 核心输出
JM_vs_LM.mini.significant_genes.tsv

## 5. 显著基因
Si9g04210.1

## 6. 结论
LM 组显著高表达
