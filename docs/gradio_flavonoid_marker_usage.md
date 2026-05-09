# Gradio 谷子黄酮候选标记推荐 Tab 使用说明

本文档按当前 `src/breeding_agent/web/gradio_app.py` 的实际实现描述。当前 Gradio 页面是一个 `gr.Blocks` 应用，标题为：

```text
Agri Multi-omics Breeding Agent Demo
```

页面使用顶部 `gr.Tab` 组织模块，不是左侧 sticky 导航，不是单页 dashboard，也不是 Radio 模块切换。当前与黄酮标记推荐相关的页面位于：

```text
谷子黄酮候选标记推荐
```

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

启动后访问：

```text
http://127.0.0.1:7860
```

如果在虚拟机或带代理的 shell 中遇到 `localhost` 502、页面一直 loading、websocket 连接失败等问题，可以临时清理代理：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY=localhost,127.0.0.1,0.0.0.0
export no_proxy=localhost,127.0.0.1,0.0.0.0
```

如果需要从宿主机访问虚拟机 Gradio，请把虚拟机 IP 也加入 `NO_PROXY/no_proxy`，避免 localhost 或虚拟机 IP 请求走代理。

## 当前 Tab 结构

当前 Gradio 页面包含以下 Tab：

- `Transcriptomics DEG Module`
- `Metabolomics Module`
- `Genomics / GWAS Module`
- `Integration & Recommendation`
- `谷子黄酮候选标记推荐`

本文件只说明 `谷子黄酮候选标记推荐` Tab。该 Tab 只接收服务器本地路径，不上传 BAM、FASTA 或代谢组大文件。

## 输入框

`谷子黄酮候选标记推荐` Tab 当前有五个输入框：

```text
dataset_dir
evidence_dir
outdir
variant_calling_dir
langgraph_outdir
```

默认值：

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
evidence_dir = outputs/flavonoid_marker_from_package/evidence
outdir = outputs/flavonoid_marker_from_package
variant_calling_dir = outputs/genomics_variant_calling
langgraph_outdir = outputs/flavonoid_marker_langgraph
```

含义：

- `dataset_dir`：学长 mini 数据包本地目录。
- `evidence_dir`：从数据包转换得到的标准 evidence TSV 目录。
- `outdir`：flavonoid marker aggregation 输出目录。
- `variant_calling_dir`：可选 Genomics Candidate Variant Calling MVP 输出目录。留空或目录不存在时保持原有黄酮推荐流程，不失败；目录存在时读取 variant evidence 并接入报告。
- `langgraph_outdir`：LangGraph workflow 输出目录，用于展示 graph trace、节点决策表、summary、最终报告、QA 和 manifest。

## 按钮

当前 Tab 有六个按钮：

```text
生成 evidence
运行标记推荐
一键运行完整流程
刷新当前结果
Run LangGraph Workflow
Refresh LangGraph Results
```

### 生成 evidence

调用 `create_evidence_from_package()`，读取 `dataset_dir` 中的 mini 数据包，并向 `evidence_dir` 写出标准 evidence 文件：

```text
transcriptome_evidence.tsv
metabolome_evidence.tsv
annotation_evidence.tsv
genome_variant_evidence.tsv
literature_evidence.tsv
```

该步骤使用的脚本入口是：

```text
scripts/demo/create_flavonoid_marker_evidence_from_package.py
```

核心实现位于：

```text
src/breeding_agent/integration/flavonoid_marker_package_importer.py
```

### 运行标记推荐

调用：

```text
src/breeding_agent/workflows/flavonoid_marker_aggregation.py
```

它读取 `evidence_dir`，运行规则版 flavonoid marker aggregation workflow，并生成候选表、Markdown 报告、QA JSON 和 manifest。

如果 `variant_calling_dir` 存在，还会读取：

```text
outputs/genomics_variant_calling/tables/candidate_variants.tsv
outputs/genomics_variant_calling/tables/kasp_candidate_sites.tsv
outputs/genomics_variant_calling/tables/caps_candidate_sites.tsv
```

并在报告中增加或刷新 `候选区域变异 calling 证据` 小节。该接入只读取真实输出，不伪造 SNP/InDel 位点；`preliminary_pass` 不等于最终 KASP marker。

### 一键运行完整流程

先执行 `生成 evidence`，再执行 `运行标记推荐`。该按钮同样支持可选 `variant_calling_dir`。

### 刷新当前结果

不重新运行 workflow，只从 `outdir` 读取当前已有输出并刷新页面展示。

如果上一次推荐运行时接入了 `variant_calling_dir`，刷新后报告中应能看到 `候选区域变异 calling 证据` 小节，包括三个固定基因的 `variant_evidence_status`。

### Run LangGraph Workflow

调用现有：

```text
src/breeding_agent/workflows/flavonoid_marker_langgraph.py
```

它复用 `evidence_dir`、`variant_calling_dir` 和 `langgraph_outdir`，运行已实现的 LangGraph 多智能体编排 workflow。Gradio 不重复实现 LangGraph 节点逻辑。

如果 LangGraph 未安装，页面会显示：

```text
LangGraph is not installed. Install with: pip install langgraph
```

### Refresh LangGraph Results

只读取 `langgraph_outdir` 下已有输出，不重新运行 workflow。若结果不存在，页面提示：

```text
尚未生成 LangGraph workflow 结果，请先点击 Run LangGraph Workflow。
```

## 页面输出

当前 Tab 展示：

- `运行状态`
- `QA 状态`
- `warning / error 信息`
- `Markdown 报告`
- `候选标记表`
- `候选区域变异 calling 证据`
- `qa_check.json`
- `manifest.json`
- LangGraph Run Status
- LangGraph QA Status
- LangGraph Summary
- Node Decision Table
- LangGraph Final Report
- Details: `graph_trace.json`、`graph_state_final.json`、`qa_check.json`、`manifest.json`

对应文件通常位于：

```text
outputs/flavonoid_marker_from_package/integration/flavonoid_marker_candidates.tsv
outputs/flavonoid_marker_from_package/reports/flavonoid_marker_report.md
outputs/flavonoid_marker_from_package/logs/qa_check.json
outputs/flavonoid_marker_from_package/manifest.json
```

LangGraph 输出通常位于：

```text
outputs/flavonoid_marker_langgraph/graph/graph_trace.json
outputs/flavonoid_marker_langgraph/graph/graph_state_final.json
outputs/flavonoid_marker_langgraph/graph/node_decision_table.tsv
outputs/flavonoid_marker_langgraph/graph/langgraph_summary.md
outputs/flavonoid_marker_langgraph/reports/flavonoid_marker_report.md
outputs/flavonoid_marker_langgraph/logs/qa_check.json
outputs/flavonoid_marker_langgraph/manifest.json
```

如果文件不存在，页面会显示 `File not found` 或 warning，不会把缺失文件伪装成已有结果。

接入 variant calling evidence 后，报告和候选表应展示：

- `Si9g04210.1`、`Si5g31340.1`、`Si9g34380.1` 的 `variant_evidence_status`。
- PASS / LowQual 统计。
- SNP / InDel 统计。
- KASP `preliminary_pass` 与 `low_quality_review_required` 统计。
- CAPS `pass_variant_requires_enzyme_screening` 与 `low_quality_variant_requires_review` 统计。
- “不能替代 WGS/GBS 群体变异检测”。
- “LowQual 不应直接优先用于 KASP/CAPS 开发”。
- “KASP/CAPS 表只是 preliminary screening，不是最终引物或酶切方案”。

如果某个基因，例如 `Si9g04210.1`，当前为 `no_called_variant_in_current_mini_calling`，页面和报告不能把它显示成已有 called variant。

## QA 判断

页面会从：

```text
outputs/flavonoid_marker_from_package/logs/qa_check.json
```

读取 QA 状态。通过时通常显示：

```text
passed=true
```

QA 会检查：

- 三个固定重点基因是否出现：
  - `Si9g04210.1`
  - `Si5g31340.1`
  - `Si9g34380.1`
- 是否包含统计值。
- 是否包含 `群体`。
- 是否包含文献查阅和 DOI。
- 是否包含 SNP/InDel/KASP/CAPS 标记类型建议。

## 关键限制

- 当前 Gradio 是展示层和本地 workflow 触发入口，不改变后端 workflow 逻辑。
- 默认黄酮推荐 workflow 不调用外部 API，不引入 Deep Agents、LangGraph 或大模型依赖。
- LangGraph 展示区使用现有规则化 agents，不调用真实大模型；LangGraph 只负责编排 LiteratureAgent、MarkerRecommendationAgent、ValidationAgent、ReviewerAgent、FinalQAAgent。
- `graph_trace.json` 和 `node_decision_table.tsv` 用于追踪每个节点的输入、输出、证据、警告和限制。
- 后续可以在 graph node 基础上接入本地开源大模型或 Deep Agents；本轮不接入。
- DOI 只能来自已核验的 evidence，不能伪造。
- 当前 mini 数据包未提供最终 SNP/InDel 位点，不能伪造 SNP/InDel 坐标。
- 如果 genome evidence 中 `variant_status=not_called`，报告必须说明后续需要候选区域 variant calling。
- 可选 `variant_calling_dir` 只把已有 Candidate Variant Calling MVP 结果接入报告展示，不改变后端分析边界。
- PASS variants 可优先进入后续 marker review；LowQual variants 仅作为可追溯候选记录保留，不应直接优先用于标记开发。
- 当前结果不能替代 WGS/GBS 群体变异检测，后续仍需更大群体基因型和黄酮含量数据验证关联。
- `data/private/` 和 `outputs/` 是本地数据和运行输出目录，不应提交 Git。
