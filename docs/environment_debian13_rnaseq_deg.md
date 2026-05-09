# Debian 13 RNA-seq DEG 环境与复现记录

适用读者：需要复现 RNA-seq DEG 运行环境或排查 Debian 工具依赖的同学。  
阅读目标：记录当前 DEG 环境配置，不代表黄酮 LangGraph / LLM / Promoter 全部环境说明。

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
