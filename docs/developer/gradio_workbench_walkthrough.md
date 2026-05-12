# Gradio 工作台后端映射说明

> Deprecated: 这份说明已被 `docs/developer/gradio_to_langgraph_call_chain.md` 和 `docs/architecture_overview.md` 收敛。它只保留为旧版后台映射参考，不再作为新人首读文档。

适用读者：需要维护 Gradio 页面或把新 workflow 接入展示层的同学。  
阅读目标：理解每个 Tab 调用哪个后端模块、Refresh 如何读输出、哪些逻辑不能写进 Gradio。

## 1. 页面结构

当前 Gradio 页面仍使用顶部 `gr.Tab` 结构，不是左侧 sticky dashboard，也不是单页纵向布局。

入口：

```text
src/breeding_agent/web/gradio_app.py
```

启动：

```bash
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

## 1.1 Clone 后的 Demo 数据准备

GitHub 不包含 `data/private/`、`outputs/` 和 `configs/llm.local.yaml`。Gradio 页面里的黄酮、variant calling、LangGraph 和 Lobster-style benchmark 展示依赖本地数据或本地运行结果，因此新同学 clone 后需要先补充：

- 原始 mini 数据包：`data/private/flavonoid_marker_mini_5genes_50kb`
- runtime artifacts 运行结果包：`outputs/flavonoid_marker_from_package/evidence`、`outputs/genomics_variant_calling`、`outputs/flavonoid_marker_langgraph_llm_real`、`outputs/lobster_external_agent_benchmark`

项目负责人打包原始 mini 数据包：

```bash
cd ~/projects/breeding-agent
mkdir -p ~/transfer
tar --zstd -cf ~/transfer/flavonoid_marker_mini_5genes_50kb.tar.zst data/private/flavonoid_marker_mini_5genes_50kb
```

新同学解压：

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

新同学解压：

```bash
cd ~/projects/breeding-agent
tar --zstd -xf ~/Downloads/breeding_agent_demo_runtime_artifacts.tar.zst -C .
ls outputs/flavonoid_marker_from_package/evidence
ls outputs/genomics_variant_calling
ls outputs/flavonoid_marker_langgraph_llm_real
ls outputs/lobster_external_agent_benchmark
```

完整 clone + unzip + run 流程见 `docs/developer/demo_data_restore_guide.md`。

## 2. Tab 与后端 workflow 对应关系

| Tab | 后端调用 | 展示内容 | 说明 |
| --- | --- | --- | --- |
| Transcriptomics DEG Module | `workflows/rnaseq_deg.py` | significant genes、report、manifest、run.log | 调用现有 RNA-seq DEG workflow |
| Metabolomics Module | `workflows/metabolomics_evidence.py` | metabolomics tables、report、manifest | 读取学长数据包已有结果表，不重做完整原始质谱分析 |
| Genomics / GWAS Module | `workflows/genomics_region.py`、`workflows/genomics_variant_calling.py` | region tables、variant calling tables、PASS/LowQual summary | Candidate variant calling 不能替代 WGS/GBS |
| Integration & Recommendation | 读取 `outputs/gradio_demo_run` | standardized evidence、candidate gene table、recommendation report | 当前不是完整多组学自动整合入口 |
| 谷子黄酮候选标记推荐 | flavonoid aggregation、LangGraph workflow | candidates、report、QA、LangGraph trace、LLM Reviewer status | 主业务展示 Tab |

## 3. 黄酮 Tab 的普通推荐

按钮：

- `生成 evidence`
- `运行标记推荐`
- `一键运行完整流程`
- `刷新当前结果`

调用：

```text
create_evidence_from_package()
run_flavonoid_marker_aggregation_task()
_build_flavonoid_outputs()
```

输出：

- `flavonoid_marker_candidates.tsv`
- `flavonoid_marker_report.md`
- `qa_check.json`
- `manifest.json`

## 4. variant evidence 展示

输入：

```text
variant_calling_dir = outputs/genomics_variant_calling
```

目录存在时读取：

- `candidate_variants.tsv`
- `kasp_candidate_sites.tsv`
- `caps_candidate_sites.tsv`

页面展示 PASS/LowQual、SNP/InDel、KASP/CAPS preliminary screening。LowQual 不应优先推荐；KASP/CAPS 表不是最终实验方案。

## 5. LangGraph workflow 展示

输入：

```text
langgraph_outdir = outputs/flavonoid_marker_langgraph
```

有 runtime artifacts 后，也可以先从 CLI 生成给家琦单独查看的默认 LangGraph 输出：

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

按钮：

- `Run LangGraph Workflow`
- `Refresh LangGraph Results`

展示：

- LangGraph Run Status
- LangGraph QA Status
- LangGraph Summary
- Node Decision Table
- Final Report
- Details: `graph_trace.json`、`graph_state_final.json`、`qa_check.json`、`manifest.json`

Gradio 调用已有 `run_flavonoid_marker_langgraph_task()`，不重复实现 node 逻辑。

## 6. Use LLM Reviewer

新增控件：

- `Use LLM Reviewer`
- `LLM Config Path`
- `LLM Reviewer Status`

行为：

- 未勾选时：不传 `use_llm_reviewer=True`，完全不调用本地模型。
- 勾选时：把 `LLM Config Path` 作为路径参数传给 LangGraph workflow。
- 页面不读取或展示 `configs/llm.local.yaml` 内容。

状态来源：

- `graph_trace.json`
- `graph_state_final.json`
- `manifest.json`

展示字段：

- `llm_reviewer_enabled`
- `llm_used`
- `fallback_used`
- `model`
- `guard_passed`
- `fallback_reason`

如果没有 LLM 字段，显示：

```text
LLM Reviewer not enabled / 未启用本地大模型审阅
```

## 7. Refresh LangGraph Results

Refresh 不重新运行 workflow，只读取已有输出：

```text
graph/langgraph_summary.md
graph/node_decision_table.tsv
graph/graph_trace.json
graph/graph_state_final.json
reports/flavonoid_marker_report.md
logs/qa_check.json
manifest.json
```

如果文件不存在，页面给出 warning，不伪造结果。

## 8. Gradio 与业务逻辑边界

Gradio 只负责：

- 接收本地路径。
- 调用 workflow。
- 读取小型输出表、Markdown、JSON。
- 展示状态和 warning。

Gradio 不负责：

- 生成 SNP/InDel。
- 生成 DOI。
- 修改 QA 规则。
- 读取或展示 LLM config 敏感内容。
- 替代 workflow / agents / graphs 的业务逻辑。

新增业务能力时，先实现 CLI / workflow / tests，再接入 Gradio。

Gradio 维护时仍要遵守 Git 边界：不要提交 `data/private/`、`outputs/` 或 `configs/llm.local.yaml`，也不要把 runtime artifacts 复制进 `docs/` 或 `src/`。
