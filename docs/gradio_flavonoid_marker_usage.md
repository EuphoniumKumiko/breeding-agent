# Gradio 谷子黄酮候选标记推荐页面使用说明

## 启动 Gradio

在项目根目录运行：

```bash
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

开发时需要热重载可以运行：

```bash
GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 PYTHONPATH=src gradio src/breeding_agent/web/gradio_app.py
```

启动后访问：

```text
http://127.0.0.1:7860
```

如果服务器绑定在 `0.0.0.0:7860`，本机浏览器仍可用 `http://127.0.0.1:7860` 访问。

reload mode 下推荐代码只从 `src/breeding_agent` 包内导入可复用逻辑。若仍需临时从项目根目录导入脚本，可使用 `PYTHONPATH=src:.`，但正式代码应优先把可复用实现放入 `src/breeding_agent/`。

## 新增 Tab

页面中新增 Tab：

```text
谷子黄酮候选标记推荐
```

该页面用于组会或本地检查时查看谷子黄酮候选标记推荐结果，包括 evidence 生成、aggregation 运行、候选表、Markdown 报告、QA 结果和 manifest。

## 默认路径

Tab 默认使用服务器本地路径：

```text
dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
evidence_dir = outputs/flavonoid_marker_from_package/evidence
outdir = outputs/flavonoid_marker_from_package
```

页面只接收路径字符串，不上传 BAM、FASTA 或代谢组大文件。

## 三个按钮

### 生成 evidence

读取 `dataset_dir` 中的 mini 数据包，调用：

```text
scripts/demo/create_flavonoid_marker_evidence_from_package.py
```

输出到：

```text
outputs/flavonoid_marker_from_package/evidence/
```

### 运行标记推荐

读取 `evidence_dir`，调用已有 backend workflow：

```text
src/breeding_agent/workflows/flavonoid_marker_aggregation.py
```

不重新实现聚合逻辑。

### 一键运行完整流程

先生成 evidence，再运行 flavonoid marker aggregation。

## 输出文件

运行后页面读取并展示：

```text
outputs/flavonoid_marker_from_package/integration/flavonoid_marker_candidates.tsv
outputs/flavonoid_marker_from_package/reports/flavonoid_marker_report.md
outputs/flavonoid_marker_from_package/logs/qa_check.json
outputs/flavonoid_marker_from_package/manifest.json
```

如果文件不存在，页面会显示清晰提示，不会崩溃。

## 判断 QA 是否通过

页面会展示 QA 状态，例如：

```text
passed=true
```

也可以直接查看：

```bash
cat outputs/flavonoid_marker_from_package/logs/qa_check.json
```

如果 `passed=false`，根据 `missing_items` 检查是否缺少固定基因、统计值、`群体`、文献查阅 DOI 或 SNP/InDel/KASP/CAPS 标记类型建议。

## 为什么不上传 BAM/FASTA 大文件

BAM、FASTA、索引和原始代谢组文件体积较大，并且属于本地私有数据。当前 Gradio 页面只接受服务器本地路径，避免浏览器上传大文件，也避免误把 `data/private/` 或 `outputs/` 中的数据纳入 Git。

当前版本仍遵守后端限制：不调用外部 API，不引入 Deep Agents、LangGraph 或大模型依赖，不伪造 DOI，不伪造 SNP/InDel 具体位点。
