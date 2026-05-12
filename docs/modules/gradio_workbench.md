# Gradio Workbench 模块导读

> Deprecated: 这份模块说明已被 `docs/developer/gradio_to_langgraph_call_chain.md` 和 `docs/architecture_overview.md` 收敛。它更适合旧版页面映射，不建议新人优先阅读。

适用读者：维护 Gradio 展示层或准备把新 workflow 接入页面的同学。  
阅读目标：理解当前 Tab 结构、后端映射、LLM Reviewer 状态展示和 Gradio 的边界。

## 1. 模块作用

Gradio Workbench 是 `breeding-agent` 的本地展示层，用于在浏览器中触发已有 workflow 或读取已有输出。本文档以当前 `src/breeding_agent/web/gradio_app.py` 的实际实现为准。

当前页面是顶部 Tab 布局：

```text
Agri Multi-omics Breeding Agent Demo
```

它不是左侧 sticky 导航，不是单页 dashboard，也不是 Radio 模块切换。

重要边界：

- Gradio 只是 UI 展示层和本地 workflow 触发入口。
- 不改变后端 workflow 逻辑。
- 不上传 BAM、FASTA 或代谢组大文件。
- 只使用服务器本地路径。
- 不伪造 DOI。
- 不伪造 SNP/InDel 位点。

## 2. 核心文件

| 文件 | 作用 |
| --- | --- |
| `src/breeding_agent/web/gradio_app.py` | Gradio app |
| `src/breeding_agent/workflows/rnaseq_deg.py` | Transcriptomics DEG 后端 |
| `src/breeding_agent/workflows/metabolomics_evidence.py` | Metabolomics 后端 |
| `src/breeding_agent/workflows/genomics_region.py` | Genomics region 后端 |
| `src/breeding_agent/workflows/genomics_variant_calling.py` | Genomics Candidate Variant Calling MVP 后端 |
| `src/breeding_agent/workflows/flavonoid_marker_aggregation.py` | Flavonoid marker 后端 |
| `src/breeding_agent/workflows/lobster_external_agent_benchmark.py` | Lobster-style external benchmark 后端 |
| `src/breeding_agent/integration/flavonoid_marker_package_importer.py` | evidence 生成逻辑 |
| `docs/gradio_flavonoid_marker_usage.md` | 黄酮标记 Tab 说明 |
| `docs/gradio_omics_modules_usage.md` | 多组学 Tab 说明 |

## 3. 入口函数

Gradio 顶层对象：

```text
demo = build_app()
```

普通启动入口：

```text
if __name__ == "__main__":
    demo.launch(...)
```

当前 `demo.launch()` 从环境变量读取：

```text
GRADIO_SERVER_NAME
GRADIO_SERVER_PORT
```

默认值分别是 `0.0.0.0` 和 `7860`。

## 4. 当前页面 Tab

当前 `build_app()` 中真实存在的 Tab 为：

1. `Transcriptomics DEG Module`
2. `Metabolomics Module`
3. `Genomics / GWAS Module`
4. `Integration & Recommendation`
5. `谷子黄酮候选标记推荐`

这些 Tab 在顶部显示，由 Gradio 的 `gr.Tab` 实现。文档中不要再描述成左侧导航或单页全部展开布局，除非后续代码确实再次修改。

## 5. 每个 Tab 对应的后端入口

| Tab | Gradio 回调 | 后端入口 |
| --- | --- | --- |
| `Transcriptomics DEG Module` | `run_deg_analysis()` | `run_rnaseq_deg_task()` |
| `Metabolomics Module` | `run_metabolomics_evidence_analysis()` | `run_metabolomics_evidence_task()` |
| `Genomics / GWAS Module` | `run_genomics_region_analysis_ui()` | `run_genomics_region_task()` |
| `Genomics / GWAS Module` | `run_genomics_variant_calling_ui()` | `run_genomics_variant_calling_task()` |
| `Genomics / GWAS Module` | `refresh_variant_calling_outputs()` | 读取 `outputs/genomics_variant_calling` 中已有 candidate variant calling 输出 |
| `Integration & Recommendation` | `build_integration_recommendation()` | 读取 `outputs/gradio_demo_run` 中已有 DEG integration 输出 |
| `谷子黄酮候选标记推荐` | `generate_flavonoid_evidence()` | `create_evidence_from_package()` |
| `谷子黄酮候选标记推荐` | `run_flavonoid_marker_recommendation()` | `run_flavonoid_marker_aggregation_task()`，可选读取 `variant_calling_dir` |
| `谷子黄酮候选标记推荐` | `run_flavonoid_full_pipeline()` | 先 evidence，再 aggregation，可选读取 `variant_calling_dir` |
| `谷子黄酮候选标记推荐` | `refresh_flavonoid_outputs()` | 读取已有 flavonoid marker 输出 |
| `谷子黄酮候选标记推荐` | `run_langgraph_workflow_ui()` | `run_flavonoid_marker_langgraph_task()` |
| `谷子黄酮候选标记推荐` | `refresh_langgraph_outputs()` | 读取已有 LangGraph workflow 输出 |
| `谷子黄酮候选标记推荐` | `run_lobster_benchmark_ui()` | `run_lobster_external_agent_benchmark_task()` |
| `谷子黄酮候选标记推荐` | `refresh_lobster_benchmark_outputs()` | 读取已有 Lobster-style benchmark 输出 |

## 6. 各 Tab 展示内容

### Transcriptomics DEG Module

输入：

- `trait_selection`
- `BAM directory`
- `GFF annotation`
- `optional_file`
- `threads`

按钮：

- `Load Demo Benchmark`
- `Run Transcriptomics Analysis`

输出：

- `status`
- `significant_genes`
- `recommendation_report.md / report.md`
- `manifest.json`
- `run.log`

### Metabolomics Module

输入：

- `dataset_dir`
- `outdir`

按钮：

- `Load Demo Metabolomics`
- `Run Metabolomics Evidence Analysis`

输出：

- `candidate_metabolites.tsv`
- `flavonoid_related_significant_metabolites.tsv`
- `target_gene_metabolite_network_edges.tsv`
- `target_gene_spls_coefficients.tsv`
- `metabolomics_report.md`
- `manifest.json`

该模块是基于学长数据包已有代谢组结果表的 evidence analysis，不是完整原始质谱重分析。

### Genomics / GWAS Module

输入：

- `dataset_dir`
- `outdir`
- Candidate Variant Calling 小节中的 `dataset_dir`
- `variant_calling_outdir`

按钮：

- `Load Demo Genomics`
- `Run Genomics Region Analysis`
- `Load Demo Variant Calling`
- `Run Variant Calling`
- `Refresh Variant Results`

输出：

- `target_gene_regions.tsv`
- `annotation_summary.tsv`
- `marker_readiness.tsv`
- `genomics_report.md`
- `manifest.json`
- `Variant Quality Summary`
- `candidate_variants.tsv`
- `snp_candidates.tsv`
- `indel_candidates.tsv`
- `kasp_candidate_sites.tsv`
- `caps_candidate_sites.tsv`
- `genomics_variant_calling_report.md`
- `outputs/genomics_variant_calling/manifest.json`
- `outputs/genomics_variant_calling/logs/run.log`

Region analysis 仍不输出最终 SNP/InDel 坐标，`marker_readiness.tsv` 中 `variant_status=not_called` 表示 mini 数据包原始状态没有 final variant calling。Candidate Variant Calling 小节调用已有 `samtools`/`bcftools` workflow；如果工具缺失，页面在 `Run Status` 显示清晰错误。`Refresh Variant Results` 只读取已有结果，缺失时提示先运行 `Run Variant Calling`。

PASS variants can be prioritized for downstream marker review（PASS 位点可优先进入后续标记开发复核）。LowQual variants are retained for traceability but should not be directly prioritized（LowQual 位点仅作为可追溯候选记录保留，不应直接优先用于标记开发）。This result does not replace WGS/GBS population variant calling（当前结果不能替代 WGS/GBS 群体变异检测）。

### Integration & Recommendation

按钮：

- `Generate Recommendation`

输出：

- `Standardized Evidence Table`
- `Candidate Gene Table`
- `Recommendation Report`
- `Current Transcriptomics Report`
- `Provenance / Reproducibility`

当前它主要汇总 `outputs/gradio_demo_run` 下已有 DEG integration 输出，不应描述为完整多组学自动整合 workflow。

### 谷子黄酮候选标记推荐

输入：

- `dataset_dir`
- `evidence_dir`
- `outdir`
- `variant_calling_dir`
- `langgraph_outdir`
- `Use LLM Reviewer`
- `LLM Config Path`
- `Lobster Evidence Dir`
- `Variant Calling Dir`
- `Internal Agent Outdir`
- `Lobster Benchmark Outdir`

按钮：

- `生成 evidence`
- `运行标记推荐`
- `一键运行完整流程`
- `刷新当前结果`
- `Run LangGraph Workflow`
- `Refresh LangGraph Results`
- `Run Lobster-style Benchmark`
- `Refresh Lobster Benchmark Results`

输出：

- `运行状态`
- `QA 状态`
- `warning / error 信息`
- `Markdown 报告`
- `候选标记表`
- `候选区域变异 calling 证据`
- `qa_check.json`
- `manifest.json`
- `LLM Reviewer Status`
- `LangGraph Summary`
- `Node Decision Table`
- `Final Report`
- Details: `graph_trace.json`、`graph_state_final.json`、`qa_check.json`、`manifest.json`
- Lobster benchmark status
- `backend_name` / `backend_mode` / `real_lobster_run`
- `lobster_style_agent_report.md`
- `comparison_matrix.tsv`
- `lobster_vs_internal_comparison.md`
- `benchmark_manifest.json`

`variant_calling_dir` 可选，默认 `outputs/genomics_variant_calling`。留空或目录不存在时保持原有黄酮推荐流程；目录存在时读取 `candidate_variants.tsv`、`kasp_candidate_sites.tsv` 和 `caps_candidate_sites.tsv`，并在报告中展示三个固定基因的 `variant_evidence_status`、PASS/LowQual、SNP/InDel、KASP preliminary screening 和 CAPS screening 统计。LowQual 不应直接优先用于 KASP/CAPS 开发，KASP/CAPS 表不是最终引物或酶切方案。

`langgraph_outdir` 默认 `outputs/flavonoid_marker_langgraph`。`Run LangGraph Workflow` 调用现有 LangGraph workflow；`Refresh LangGraph Results` 只读取已有 graph 输出。`Use LLM Reviewer` 默认关闭；勾选后只增强 ReviewerAgent，并使用 `LLM Config Path` 指向的本地 OpenAI-compatible 配置。页面不读取或展示配置文件内容，只显示路径和运行状态。

LLM Reviewer 状态从 `graph_trace.json`、`graph_state_final.json` 或 manifest 中读取，展示 `llm_reviewer_enabled`、`llm_used`、`fallback_used`、`model`、`guard_passed` 和 `fallback_reason`。本地 LLM 不直接生成 SNP/InDel/KASP/CAPS 结论；输出仍经过 output_guard 和 FinalQAAgent，不通过会 fallback 到规则版 ReviewerAgent。Deep Agents POC 已作为并行 CLI/workflow 跑通，但当前未接入 Gradio，且不替代 LangGraph。

`Lobster Benchmark Outdir` 默认 `outputs/lobster_external_agent_benchmark`。`Run Lobster-style Benchmark` 调用现有 Lobster-style benchmark workflow；`Refresh Lobster Benchmark Results` 只读取已有 benchmark 输出。该区展示 `backend_name=lobster_ai_reference`、`backend_mode=mock_reference`、`real_lobster_run=false`、`lobster_style_agent_report.md`、`comparison_matrix.tsv`、`lobster_vs_internal_comparison.md` 和 `benchmark_manifest.json`。当前不是 Lobster AI 真实运行结果，只是 external reference benchmark，不替代 LangGraph 主流程。

## 7. 普通启动命令

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

## 8. reload mode 启动命令

```bash
cd ~/projects/breeding-agent
GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 PYTHONPATH=src gradio src/breeding_agent/web/gradio_app.py
```

## 9. 代理问题处理

如果虚拟机或 shell 设置了代理，访问 `127.0.0.1:7860` 时可能出现 502、页面加载失败或 websocket 异常。可临时执行：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export NO_PROXY=localhost,127.0.0.1,0.0.0.0
export no_proxy=localhost,127.0.0.1,0.0.0.0
```

从宿主机访问虚拟机服务时，也可以把虚拟机 IP 加入 `NO_PROXY/no_proxy`。

## 10. 如何查看输出

页面输出主要来自：

```text
outputs/gradio_demo_run/
outputs/gradio_metabolomics_run/
outputs/gradio_genomics_run/
outputs/genomics_variant_calling/
outputs/flavonoid_marker_from_package/
outputs/flavonoid_marker_langgraph/
outputs/lobster_external_agent_benchmark/
```

这些都是运行输出目录，不应提交 Git。

## 11. 学习建议

读 `gradio_app.py` 时建议按以下顺序：

1. 找 `build_app()`。
2. 看每个 `with gr.Tab(...)` 内有哪些输入、按钮和输出。
3. 找 `.click(...)` 绑定。
4. 跳到对应回调函数。
5. 从回调函数追到 workflow。
6. 对照 `_build_metabolomics_outputs()`、`_build_genomics_outputs()`、`_build_flavonoid_outputs()` 理解页面如何读取已有输出文件。
