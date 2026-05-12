# LiteratureAgent v3 讲解稿

这份文档解释文献模块从“读 evidence”到“生成检索计划”再到“回流分析”的完整链路。

## 1. v3 想解决什么问题

v2 解决的是：

- 读取 `literature_evidence.tsv`
- 读取外部 literature results JSONL
- 做 DOI 边界检查、demo fixture 脱敏、report QA

v3 新增的是第一步：

- 从当前生信 evidence 自动生成 `literature_query_plan`
- 再把这个 plan 交给外部 `agri-breeding-literature-pipeline` 做 PubMed 检索
- 最后把检索结果回流回来做分析

## 2. v3 的流程

`生信 evidence / candidate context`

→ `query_builder.py`

→ `literature_query_plan.jsonl / literature_query_plan.tsv`

→ `agri-breeding-literature-pipeline` 检索

→ `literature_search_results_online.jsonl`

→ `LiteratureAgent` 读取结果

→ `relevance_level = high / medium / background`

→ `report` + `qa_check.json`

## 3. query_plan 是什么

query_plan 不是论文结论，也不是搜索结果，它只是“检索意图”。

字段包括：

- `query_id`
- `query`
- `crop`
- `trait`
- `gene_id`
- `query_type`
- `keywords`
- `source_terms`

它的作用是把证据上下文拆成可复用的搜索条目。

## 4. 为什么要做 relevance 分层

外部文献不应该被一律写成“直接证据”。

所以 report 里区分三层：

- `high`：更接近 Setaria italica / foxtail millet + flavonoid / marker / breeding 语境
- `medium`：和 millet / flavonoid 有关，但不够具体
- `background`：更偏通用背景

这能帮助组会听众快速看懂哪些文献更接近候选基因，哪些只是背景材料。

## 5. demo fixture 的边界

demo fixture 只用于流程演示，不计入真实 PubMed evidence。

因此：

- `source=PubMedFixture`
- `is_demo=true`
- DOI 会被显示成 `DEMO_ONLY` / `NA`
- 不进入 `has_doi`
- 不进入真实 evidence 统计

## 6. 这段话适合怎么说

> v3 不是单纯去抓更多文献，而是先把生信 evidence 变成标准化检索计划，再把检索结果按相关性分层。这样报告里能清楚地区分：哪些是 verified DOI evidence，哪些只是外部背景，哪些只是 demo fixture。

