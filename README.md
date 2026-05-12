# breeding-agent

适用读者：第一次打开项目的新同学、老师汇报前需要快速确认当前能力的人、后续多智能体开发参与者。  
阅读目标：用最短路径理解项目定位、已完成能力、常用命令、Gradio 入口、LLM Reviewer 和当前边界。

## 1. 项目定位

`breeding-agent` 是一个面向谷子多组学育种分析的本地可复现项目。当前实现已经不只是 RNA-seq DEG demo，而是覆盖：

- 生信数据处理层：RNA-seq DEG、代谢组 evidence、基因组 region、Genomics Candidate Variant Calling MVP。
- Evidence 标准化层：transcriptomics / metabolomics / annotation / literature / variant evidence 聚合。
- 智能体聚合分析层：规则化 flavonoid marker agents、LLM-ready interface、LangGraph 主线 workflow、Deep Agents POC。
- 本地 LLM Reviewer 层：OpenAI-compatible 本地模型只增强 LangGraph ReviewerAgent。
- Gradio 展示层：顶部 `gr.Tab` 工作台。
- Promoter Design scaffold：任务定义、schema、数据盘点和占位 workflow。

## 2. 推荐阅读顺序

如果只想先抓住主线，按这个顺序看：

1. `README.md`
2. `docs/project_onboarding.md`
3. `docs/architecture_overview.md`
4. `docs/developer/code_walkthrough_for_meeting.md`
5. `docs/developer/gradio_to_langgraph_call_chain.md`
6. `docs/developer/literature_agent_v3_walkthrough.md`
7. `docs/developer/current_project_boundary_for_meeting.md`

## 3. 当前完成能力

| 能力 | 当前实现状态 |
| --- | --- |
| RNA-seq DEG reproduction | 已完成 CLI / workflow / report / evidence integration |
| 谷子黄酮候选标记推荐 | 已满足固定三基因、`群体`、文献查阅、DOI、统计值、SNP/InDel/KASP/CAPS 推荐 |
| 多组学 evidence 聚合 | 已聚合 transcriptomics / metabolomics / annotation / literature，支持 variant evidence |
| Genomics Candidate Variant Calling MVP | 已输出真实候选 SNP/InDel、PASS/LowQual、KASP/CAPS preliminary screening |
| LLM-ready Agent Interface | 已完成 AgentInput / AgentOutput / context builder / prompt templates |
| LangGraph workflow | 已作为主线多智能体编排 workflow 跑通，并接入 Gradio |
| Deep Agents POC | 已跑通，作为并行 POC，不替代 LangGraph |
| 本地 LLM ReviewerAgent | 已接入 Windows LM Studio / Qwen3.5-9B，只增强 ReviewerAgent，输出经过 output_guard 和 FinalQAAgent |
| Gradio LLM 展示 | 已显示 Use LLM Reviewer、LLM Config Path、llm_used / fallback_used / guard_passed / model |
| Promoter Design scaffold | 已完成任务定义、schema、workflow/CLI 占位输出和数据盘点，不生成真实启动子 |

## 4. 快速开始

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 -m unittest discover -s tests
```

如果只看页面：

```bash
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

浏览器访问：

```text
http://127.0.0.1:7860
```

## 5. Clone 后恢复 Demo 数据

GitHub 仓库不包含 `data/private/`、`outputs/` 和 `configs/llm.local.yaml`。这些目录分别对应私有/大型输入数据、本地运行结果和本地 LLM 配置，不能提交到 GitHub。

完整复现谷子黄酮候选标记 demo 需要额外补充两类包：

- 原始 mini 数据包：`data/private/flavonoid_marker_mini_5genes_50kb`
- runtime artifacts 运行结果包：`outputs/flavonoid_marker_from_package/evidence`、`outputs/genomics_variant_calling`、`outputs/flavonoid_marker_langgraph_llm_real`、`outputs/lobster_external_agent_benchmark`

项目负责人打包原始 mini 数据包：

```bash
cd ~/projects/breeding-agent
mkdir -p ~/transfer
tar --zstd -cf ~/transfer/flavonoid_marker_mini_5genes_50kb.tar.zst data/private/flavonoid_marker_mini_5genes_50kb
```

新同学解压原始 mini 数据包：

```bash
cd ~/projects/breeding-agent
tar --zstd -xf ~/Downloads/flavonoid_marker_mini_5genes_50kb.tar.zst -C .
ls data/private/flavonoid_marker_mini_5genes_50kb
```

项目负责人打包 runtime artifacts：

```bash
cd ~/projects/breeding-agent
mkdir -p ~/transfer
tar --zstd -cf ~/transfer/breeding_agent_demo_runtime_artifacts.tar.zst \
  outputs/flavonoid_marker_from_package/evidence \
  outputs/genomics_variant_calling \
  outputs/flavonoid_marker_langgraph_llm_real \
  outputs/lobster_external_agent_benchmark
```

新同学解压 runtime artifacts：

```bash
cd ~/projects/breeding-agent
tar --zstd -xf ~/Downloads/breeding_agent_demo_runtime_artifacts.tar.zst -C .
```

有 runtime artifacts 后运行默认 LangGraph：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_jiaqi \
  --variant-calling-dir outputs/genomics_variant_calling
```

检查 QA：

```bash
python3 -c "import json; print(json.load(open('outputs/flavonoid_marker_langgraph_jiaqi/logs/qa_check.json'))['passed'])"
```

更多 clone + unzip + run 的完整步骤见 `docs/developer/demo_data_restore_guide.md`。

## 6. 常用 CLI

生成黄酮 marker evidence：

```bash
PYTHONPATH=src python3 scripts/demo/create_flavonoid_marker_evidence_from_package.py \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/flavonoid_marker_from_package/evidence
```

普通黄酮候选标记推荐：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package \
  --variant-calling-dir outputs/genomics_variant_calling
```

Genomics Candidate Variant Calling MVP：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.genomics_variants \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/genomics_variant_calling
```

LangGraph 主线 workflow：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph \
  --variant-calling-dir outputs/genomics_variant_calling
```

LangGraph + 本地 LLM Reviewer：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_llm_real \
  --variant-calling-dir outputs/genomics_variant_calling \
  --use-llm-reviewer \
  --llm-config configs/llm.local.yaml
```

Deep Agents POC：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_deepagents \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_deepagents \
  --variant-calling-dir outputs/genomics_variant_calling
```

Promoter Design scaffold：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.promoter_design \
  --gene-id Si9g04210.1 \
  --gene-sequence ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC \
  --gene-function "flavonoid-related candidate gene" \
  --species foxtail_millet \
  --target-expression-level high \
  --outdir outputs/promoter_design_demo
```

## 7. Gradio 工作台

当前页面使用顶部 `gr.Tab`：

- Transcriptomics DEG Module
- Metabolomics Module
- Genomics / GWAS Module
- Integration & Recommendation
- 谷子黄酮候选标记推荐

黄酮 Tab 包含普通推荐、variant evidence、LangGraph workflow、Use LLM Reviewer、LLM Config Path 和 LLM Reviewer Status。Gradio 只是展示层和本地 workflow 触发入口，不改变后端业务逻辑。

## 8. 本地 LLM Reviewer

当前实现：

- Windows LM Studio 部署 Qwen3.5-9B。
- Debian VM 通过 OpenAI-compatible API 调用。
- 请求体包含 `chat_template_kwargs.enable_thinking=false`。
- 只增强 LangGraph `ReviewerAgent`。
- LLM 不允许引入新的 DOI 值，也不直接生成 SNP/InDel/KASP/CAPS 结论。
- 输出经过 `output_guard` 和 `FinalQAAgent`。
- 失败、空内容或 guard 不通过时 fallback 到规则版 ReviewerAgent。

真实运行中已观察到：

```text
llm_reviewer_enabled=true
llm_used=true
fallback_used=false
model=qwen/qwen3.5-9b
guard_passed=true
qa_check.json passed=true
```

本地真实配置 `configs/llm.local.yaml` 不应提交 Git。

## 9. Promoter Design scaffold

Promoter Design 当前只是 scaffold：

- 定义输入：gene_id、gene_sequence、gene_function、species、target expression。
- 定义输出：candidate table、report、validation plan、manifest。
- 新增数据盘点文档。
- 不训练模型。
- 不生成真实启动子序列。
- 不输出可直接实验使用的 synthetic promoter。

## 9. 当前能力边界

未完成：

- KASP 标记定稿。
- CAPS 酶切方案设计。
- WGS/GBS 群体变异检测。
- 大群体基因型-黄酮含量关联验证。
- 实验验证。
- 启动子生成模型训练。

必须遵守：

- 不伪造 SNP/InDel 位点。
- 不伪造 DOI。
- 不伪造启动子序列。
- LowQual 不得作为优先推荐。
- KASP/CAPS preliminary screening 不是最终引物或酶切方案。
- Candidate-region variant calling 不能替代 WGS/GBS 群体变异检测。
- 不提交 `data/private/`、`outputs/`、`configs/llm.local.yaml`。

## 10. 推荐阅读路径

1. `docs/architecture_overview.md`
2. `docs/project_onboarding.md`
3. `docs/developer/demo_data_restore_guide.md`
4. `docs/developer/codebase_map.md`
5. `docs/developer/business_logic_by_file.md`
6. `docs/developer/workflow_tracing_guide.md`
7. `docs/developer/agent_parallel_development_guide.md`
8. `docs/developer/local_llm_integration_walkthrough.md`
9. `docs/developer/gradio_workbench_walkthrough.md`
10. `docs/developer/testing_and_release_checklist.md`
