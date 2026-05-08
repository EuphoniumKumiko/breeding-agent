# Gradio Workbench 模块导读

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
| `src/breeding_agent/workflows/flavonoid_marker_aggregation.py` | Flavonoid marker 后端 |
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
| `Integration & Recommendation` | `build_integration_recommendation()` | 读取 `outputs/gradio_demo_run` 中已有 DEG integration 输出 |
| `谷子黄酮候选标记推荐` | `generate_flavonoid_evidence()` | `create_evidence_from_package()` |
| `谷子黄酮候选标记推荐` | `run_flavonoid_marker_recommendation()` | `run_flavonoid_marker_aggregation_task()` |
| `谷子黄酮候选标记推荐` | `run_flavonoid_full_pipeline()` | 先 evidence，再 aggregation |
| `谷子黄酮候选标记推荐` | `refresh_flavonoid_outputs()` | 读取已有 flavonoid marker 输出 |

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

按钮：

- `Load Demo Genomics`
- `Run Genomics Region Analysis`

输出：

- `target_gene_regions.tsv`
- `annotation_summary.tsv`
- `marker_readiness.tsv`
- `genomics_report.md`
- `manifest.json`

该模块不做正式 SNP/InDel calling，不输出最终 SNP/InDel 坐标。`marker_readiness.tsv` 中 `variant_status=not_called` 表示后续仍需候选区域 variant calling。

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

按钮：

- `生成 evidence`
- `运行标记推荐`
- `一键运行完整流程`
- `刷新当前结果`

输出：

- `运行状态`
- `QA 状态`
- `warning / error 信息`
- `Markdown 报告`
- `候选标记表`
- `qa_check.json`
- `manifest.json`

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
outputs/flavonoid_marker_from_package/
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
