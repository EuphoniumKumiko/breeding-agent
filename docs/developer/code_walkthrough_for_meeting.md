# 组会代码讲解提纲

这份提纲面向今晚组会，目标是用 3 分钟把项目主线讲清楚，避免把注意力放在实现细节上。

## 1. 一句话概括

这个项目的核心不是“训练一个新模型”，而是把学长给的谷子多组学 evidence 按固定边界串成一条可复现流水线：

`生信 evidence -> LangGraph workflow -> LiteratureAgent v3 query_plan -> PubMed 检索 -> literature_results_online -> relevance 分层 -> MarkerRecommendationAgent -> ValidationAgent -> QA -> Gradio 展示`

## 2. 3 分钟主线

1. 入口在 `Gradio`，但它只是展示和触发层，不是核心算法。
2. 核心输入来自证据包和原始文件名溯源，例如 `bam/`、`metabolome_raw_3372.tsv`、`genome.fa`、`genome.gff`、`local_region_emapper_annotations.tsv`。
3. `LangGraph` 负责把 evidence 按固定顺序编排：证据加载、候选整合、文献分析、标记推荐、验证方案、QA、报告输出。
4. `LiteratureAgent v3` 先从生信 evidence 自动生成 `literature_query_plan`，再交给外部 literature pipeline 做 PubMed 检索，最后把结果回流到本仓库做相关性分层。
5. `MarkerRecommendationAgent` 只给出候选 SNP/InDel/KASP/CAPS 建议，明确保留“预筛选”边界，不声称最终标记。
6. `ValidationAgent` 负责给出后续验证方案，强调还需要更大群体的基因型和黄酮含量验证。
7. `FinalQAAgent` 和 `OutputGuard` 负责守边界：不编 DOI，不编位点，不把 demo 结果当真实 evidence。
8. 最终产物是报告和 QA JSON，供组会展示和后续实验设计使用。

## 3. 代码阅读顺序

建议按这个顺序讲：

1. `src/breeding_agent/web/gradio_app.py`
2. `src/breeding_agent/cli/flavonoid_markers_graph.py`
3. `src/breeding_agent/workflows/flavonoid_marker_langgraph.py`
4. `src/breeding_agent/graphs/flavonoid_marker_graph.py`
5. `src/breeding_agent/agents/flavonoid_literature_agent.py`
6. `src/breeding_agent/literature/query_builder.py`
7. `src/breeding_agent/integration/flavonoid_marker_qa.py`
8. `src/breeding_agent/reports/flavonoid_marker_report.py`

## 4. 你可以直接说的话

> 这个项目的重点不是单点算法，而是把谷子黄酮相关的多组学 evidence 变成一条可复现、可检查、边界清楚的推荐链路。Gradio 只是入口，真正的业务逻辑在 LangGraph、LiteratureAgent、MarkerRecommendation、Validation 和 QA 这些后端模块里。

> 文献部分我们先从证据包自动生成 query plan，再让外部 literature pipeline 做 PubMed 检索，最后回流到本地做 relevance 分层和 QA。demo fixture 只用于演示，不会被当成真实 DOI evidence。

> 标记推荐的结论始终是候选级别：优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发 SNP/InDel/KASP/CAPS 候选，再用更大群体和黄酮含量数据去验证。

## 5. 提醒

- 不要把 `Gradio` 讲成算法层。
- 不要把 `report` 讲成最终验证结论。
- 不要把 `KASP/CAPS` 讲成最终 primer/酶切方案。
- 不要把 `WGS/GBS` 群体验证、湿实验验证讲成已经完成。

