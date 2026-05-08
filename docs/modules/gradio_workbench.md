# Gradio Workbench 模块导读

## 1. 模块作用

Gradio Workbench 是 `breeding-agent` 的本地展示层，用于在浏览器中触发已有 workflow 或读取已有输出。它适合组会演示、老师汇报和本地结果检查。

重要边界：

- Gradio 只是 UI 展示层。
- 不改变后端 workflow 逻辑。
- 不上传 BAM、FASTA 或代谢组大文件。
- 只使用服务器本地路径。
- 不伪造 DOI。
- 不伪造 SNP/InDel 位点。

## 2. 核心文件

| 文件 | 作用 |
| --- | --- |
| `src/breeding_agent/web/gradio_app.py` | Gradio app |
| `src/breeding_agent/workflows/rnaseq_deg.py` | Transcriptomics 后端 |
| `src/breeding_agent/workflows/metabolomics_evidence.py` | Metabolomics 后端 |
| `src/breeding_agent/workflows/genomics_region.py` | Genomics 后端 |
| `src/breeding_agent/workflows/flavonoid_marker_aggregation.py` | Flavonoid marker 后端 |
| `scripts/demo/create_flavonoid_marker_evidence_from_package.py` | evidence 生成逻辑的脚本入口 |
| `docs/gradio_flavonoid_marker_usage.md` | 黄酮标记页面说明 |
| `docs/gradio_omics_modules_usage.md` | 多组学页面说明 |

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

这是为了同时支持：

- `python3 -m breeding_agent.web.gradio_app`
- `gradio src/breeding_agent/web/gradio_app.py`

## 4. 页面模块

当前页面为左侧 sticky 模块导航 + 右侧单页完整模块展示。右侧按顺序包含：

1. `Transcriptomics DEG Module（转录组差异表达分析模块）`
2. `Metabolomics Evidence Module（代谢组证据分析模块）`
3. `Genomics Region Module（基因组候选区域分析模块）`
4. `Integration & Recommendation（整合推荐模块）`
5. `Flavonoid Marker Recommendation（黄酮候选标记推荐）`

左侧导航只是页面内 anchor 跳转，不负责隐藏或显示模块。

## 5. 每个页面模块对应的后端 workflow

| 页面模块 | Gradio 回调 | 后端入口 |
| --- | --- | --- |
| Transcriptomics DEG | `run_deg_analysis()` | `run_rnaseq_deg_task()` |
| Metabolomics Evidence | `run_metabolomics_evidence_analysis()` | `run_metabolomics_evidence_task()` |
| Genomics Region | `run_genomics_region_analysis_ui()` | `run_genomics_region_task()` |
| Integration & Recommendation | `build_integration_recommendation()` | 读取已有 DEG integration 输出 |
| Flavonoid Marker Recommendation | `generate_flavonoid_evidence()` | `create_evidence_from_package()` |
| Flavonoid Marker Recommendation | `run_flavonoid_marker_recommendation()` | `run_flavonoid_marker_aggregation_task()` |
| Flavonoid Marker Recommendation | `run_flavonoid_full_pipeline()` | 先 evidence，再 aggregation |
| Flavonoid Marker Recommendation | `refresh_flavonoid_outputs()` | 读取已有输出 |

## 6. 普通启动命令

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

默认读取：

```text
GRADIO_SERVER_NAME=0.0.0.0
GRADIO_SERVER_PORT=7860
```

如果需要显式指定：

```bash
GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 \
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

## 7. reload mode 启动命令

开发热重载：

```bash
cd ~/projects/breeding-agent
GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 \
PYTHONPATH=src gradio src/breeding_agent/web/gradio_app.py
```

不要再使用 `GRADIO_RELOAD_MODE=1` 作为推荐启动方式。标准结构是保留顶层 `demo = build_app()`，并只在 `__name__ == "__main__"` 时调用 `demo.launch()`。

## 8. 为什么有时要 unset proxy

如果 shell 或 micromamba 环境设置了代理变量，本地浏览器访问 `127.0.0.1:7860`、Gradio websocket 或静态资源请求可能被错误转发到代理，导致页面打不开、一直 loading 或连接失败。

遇到本地页面异常时，可以先临时清理代理环境变量：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
```

然后再启动 Gradio。

这一步只影响当前 shell，不会修改代码。

## 9. 如何访问页面

启动后访问：

```text
http://127.0.0.1:7860
```

如果部署在远程服务器：

- 服务端绑定 `0.0.0.0:7860`。
- 浏览器访问服务器 IP 或通过 SSH port forwarding 访问。

## 10. 如何查看输出

Gradio 页面会展示：

- Run Status。
- 主结果表。
- Summary Report。
- manifest JSON。
- run log。
- QA JSON。
- warning / error。

也可以直接在文件系统中查看：

```text
outputs/gradio_demo_run/
outputs/gradio_metabolomics_run/
outputs/gradio_genomics_run/
outputs/flavonoid_marker_from_package/
```

注意：`outputs/` 是运行结果目录，不要提交到 Git。

## 11. 常见问题

### 页面按钮应该写业务逻辑吗？

不应该。按钮只应该调用已有 workflow 或读取已有输出。

### 为什么不上传 BAM/FASTA？

BAM、FASTA、索引和代谢组大表体积大，而且属于本地私有数据。页面只接收路径字符串，避免浏览器上传大文件和误提交数据。

### reload mode 只显示 Watching 怎么办？

检查：

- 是否使用标准 reload 命令。
- 是否安装 gradio。
- 是否有端口冲突。
- 是否被代理变量影响。

### Gradio 页面能不能改变后端结果？

页面按钮会触发已有 workflow 运行，因此会写 outputs。但页面本身不改变 workflow 逻辑。

## 12. 学习建议

读 `gradio_app.py` 时不要从 CSS 开始。建议顺序：

1. 找 `build_app()`。
2. 看每个模块的输入框和按钮。
3. 找按钮 `.click()` 绑定。
4. 跳到对应回调函数。
5. 从回调函数跳到 workflow。
6. 对照输出读取 helper，例如 `_build_flavonoid_outputs()`。
