# Demo 数据与运行结果恢复指南

适用读者：刚从 GitHub clone 项目的新同学、需要复现谷子黄酮候选标记 demo 的协作者。  
阅读目标：明确哪些文件不在 GitHub、如何补充学长提供的原始 mini 数据包、如何补充 demo runtime artifacts，以及如何跑通默认 LangGraph demo。

## 1. 为什么 GitHub 不包含这些数据

GitHub 仓库只保存代码、轻量文档和可复现 workflow，不提交以下本地内容：

- `data/private/`：包含学长提供的 BAM、FASTA、GFF、代谢组表等私有或较大数据。
- `outputs/`：包含本地运行生成的 evidence、variant calling、LangGraph、benchmark 等运行结果。
- `configs/llm.local.yaml`：包含本地 LLM 服务地址、模型名或本机配置，不应公开。

因此，从 GitHub clone 后不能假设这些目录已经存在。要完整复现谷子黄酮候选标记 demo，需要额外补充两类包：

- 原始 mini 数据包：`data/private/flavonoid_marker_mini_5genes_50kb`
- runtime artifacts 运行结果包：若干 `outputs/` 下的已生成 demo 结果

## 2. 原始 mini 数据包

原始 mini 数据包是学长提供的核心输入，必须放在项目根目录下的固定路径：

```text
data/private/flavonoid_marker_mini_5genes_50kb
```

核心输入包括：

- 转录组：`bam/` 中所有文件
- 代谢组：`metabolome/metabolome_raw_3372.tsv`
- 基因组：`genome.fa` 和 `genome.gff`
- 功能注释：`annotations/local_region_emapper_annotations.tsv`

项目负责人从项目根目录打包：

```bash
cd ~/projects/breeding-agent
mkdir -p ~/transfer
tar --zstd -cf ~/transfer/flavonoid_marker_mini_5genes_50kb.tar.zst data/private/flavonoid_marker_mini_5genes_50kb
```

新同学从项目根目录解压：

```bash
cd ~/projects/breeding-agent
tar --zstd -xf ~/Downloads/flavonoid_marker_mini_5genes_50kb.tar.zst -C .
```

解压后检查：

```bash
ls data/private/flavonoid_marker_mini_5genes_50kb
```

期望至少能看到：

```text
bam
metabolome
annotations
transcriptome
genome.fa
genome.gff
genome.original_coords.gff
genome.bam_compatible.fa.gz
sample_metadata.tsv
target_genes.tsv
```

## 3. Runtime Artifacts 运行结果包

runtime artifacts 是为了让新同学快速打开 demo、刷新 Gradio 结果或直接跑下游 LangGraph 而准备的已生成运行结果。它们不是 GitHub 内容，也不是原始数据。

建议包含这些目录：

```text
outputs/flavonoid_marker_from_package/evidence
outputs/genomics_variant_calling
outputs/flavonoid_marker_langgraph_llm_real
outputs/lobster_external_agent_benchmark
```

项目负责人从项目根目录打包：

```bash
cd ~/projects/breeding-agent
mkdir -p ~/transfer
tar --zstd -cf ~/transfer/breeding_agent_demo_runtime_artifacts.tar.zst \
  outputs/flavonoid_marker_from_package/evidence \
  outputs/genomics_variant_calling \
  outputs/flavonoid_marker_langgraph_llm_real \
  outputs/lobster_external_agent_benchmark
```

新同学从项目根目录解压：

```bash
cd ~/projects/breeding-agent
tar --zstd -xf ~/Downloads/breeding_agent_demo_runtime_artifacts.tar.zst -C .
```

解压后检查：

```bash
ls outputs/flavonoid_marker_from_package/evidence
ls outputs/genomics_variant_calling
ls outputs/flavonoid_marker_langgraph_llm_real
ls outputs/lobster_external_agent_benchmark
```

## 4. 有 Runtime Artifacts 后运行默认 LangGraph

有 `outputs/flavonoid_marker_from_package/evidence` 和 `outputs/genomics_variant_calling` 后，可以直接运行默认 LangGraph，不需要本地 LLM 配置：

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_jiaqi \
  --variant-calling-dir outputs/genomics_variant_calling
```

检查 QA 是否通过：

```bash
python3 -c "import json; print(json.load(open('outputs/flavonoid_marker_langgraph_jiaqi/logs/qa_check.json'))['passed'])"
```

期望输出：

```text
True
```

也可以直接查看完整 QA：

```bash
cat outputs/flavonoid_marker_langgraph_jiaqi/logs/qa_check.json
```

其中应包含：

```text
"passed": true
```

## 5. 家琦第一天 Clone + Unzip + Run

下面命令假设代码仓库已经有访问权限，两个压缩包已经放到 `~/Downloads/`。

```bash
cd ~/projects
git clone <repo-url> breeding-agent
cd breeding-agent

tar --zstd -xf ~/Downloads/flavonoid_marker_mini_5genes_50kb.tar.zst -C .
tar --zstd -xf ~/Downloads/breeding_agent_demo_runtime_artifacts.tar.zst -C .

ls data/private/flavonoid_marker_mini_5genes_50kb
ls outputs/flavonoid_marker_from_package/evidence
ls outputs/genomics_variant_calling

PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_jiaqi \
  --variant-calling-dir outputs/genomics_variant_calling

python3 -c "import json; print(json.load(open('outputs/flavonoid_marker_langgraph_jiaqi/logs/qa_check.json'))['passed'])"
```

如果最后输出 `True`，说明默认 LangGraph demo 的 QA 已通过。

## 6. Git 安全边界

任何时候都不要提交以下内容到 GitHub：

- `data/private/`
- `outputs/`
- `configs/llm.local.yaml`
- BAM / BAI / FASTA / FASTA index / 大型中间文件

提交前检查：

```bash
git status --short --untracked-files=all
git diff --stat
```

如果看到 `data/private/`、`outputs/` 或 `configs/llm.local.yaml` 出现在待提交列表中，先停止提交并移出 Git 跟踪范围。
