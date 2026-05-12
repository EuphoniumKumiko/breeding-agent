# Gradio 到 LangGraph 的调用链

这份文档只解释“页面上的按钮如何落到后端工作流”，不讨论算法细节。

## 1. 角色分工

- `Gradio`：展示层和触发层，负责收集输入、显示输出、刷新已有结果。
- `CLI / workflow wrapper`：负责把页面输入转成结构化配置对象。
- `LangGraph`：负责真正的业务编排。
- `Agent` / `literature` / `QA` / `report` 模块：负责具体业务逻辑。

## 2. 调用链

### 2.1 用户在页面上点击运行

页面会把这些输入传给 `run_langgraph_workflow_ui()`：

- evidence 目录
- outdir
- variant calling 目录
- literature results JSONL 路径
- 是否启用 LLM reviewer
- LLM 配置路径

### 2.2 Gradio 只做最小校验

`Gradio` 这一层只检查：

- 路径是否存在
- 是否为空
- 是否需要提示 warning

它不解析 evidence，不生成 query plan，不做 DOI 判断。

### 2.3 调到 LangGraph 工作流

`run_langgraph_workflow_ui()` 会构造 `FlavonoidMarkerLangGraphConfig`，然后交给：

`run_flavonoid_marker_langgraph_task()`

这个 workflow wrapper 会：

- 解析路径
- 建立 manifest
- 初始化 graph state
- 调用 LangGraph 或 sequential fallback
- 写出 report、QA、trace、manifest、query plan

## 3. 为什么页面里保留原始文件名

页面和报告中保留 `bam/`、`metabolome_raw_3372.tsv`、`genome.fa`、`genome.gff` 这些名字，是为了输入溯源。

这表示：

- 我们知道证据来自哪里
- 我们可以回到原始输入复核
- 这不等于页面在展示未经处理的原始数据

真正的解析和归纳是在后端 workflow 和 report 里完成的。

## 4. 文献结果是怎么回流的

`Gradio` 新增的 `Literature results JSONL path` 只是一个输入路径。

路径会被传给 `FlavonoidMarkerLangGraphConfig(literature_results=...)`，然后进入：

`FlavonoidLiteratureAgent -> analyze_literature -> report / qa`

这样页面只是控制输入位置，文献分析仍然在后端完成。

## 5. 你可以怎么讲

> 这套界面不是把算法写进前端，而是把后端 workflow 暴露成可操作的入口。页面负责把证据和结果展示出来，真正的判断规则仍在 LangGraph 和各个 Agent 里。

