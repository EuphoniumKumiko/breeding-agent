# Agent 并行开发指南

适用读者：准备并行开发 Literature / Validation / Reviewer / 新 Agent 的同学。  
阅读目标：明确每个 Agent 的职责边界、LLM 接入顺序、安全规则和分支开发规范。

## 1. 当前已有 Agent

| Agent | 文件 | 当前职责 | 是否已接 LLM |
| --- | --- | --- | --- |
| LiteratureAgent | `agents/flavonoid_literature_agent.py` | 读取已有 literature evidence，保留 DOI，生成文献查阅文本 | 否 |
| MarkerRecommendationAgent | `agents/flavonoid_marker_recommendation_agent.py` | 根据 candidate rows 和 variant evidence 给出 SNP/InDel/KASP/CAPS 推荐 | 否 |
| ValidationAgent | `agents/flavonoid_validation_agent.py` | 生成 Sanger、qRT-PCR、LC-MS/MS、群体验证等后续验证计划 | 否 |
| ReviewerAgent | `agents/flavonoid_reviewer_agent.py` | 检查过度推断、缺 DOI、伪造坐标、LowQual 和 preliminary overclaim | 是，仅 LangGraph 可选本地 LLM 增强 |
| FinalQAAgent | `agents/flavonoid_final_qa_agent.py` | 调用 canonical QA，确保固定基因、统计值、关键词、DOI 和 marker 类型存在 | 不建议 |

## 2. Agent 职责边界

- LiteratureAgent：只能基于已有 evidence 和已核验 DOI 组织文本，不能补造 DOI。
- MarkerRecommendationAgent：只能基于真实 candidate rows 和 variant evidence 推荐类型，不能创造 SNP/InDel 坐标。
- ValidationAgent：负责“还需要哪些验证”，不能把候选证据写成已完成实验验证。
- ReviewerAgent：负责审阅和风险提示，不生产新生物学结论。
- FinalQAAgent：规则化终检，建议保持 deterministic，不能交给 LLM 替代。

## 3. LLM 接入优先级

建议顺序：

1. ReviewerAgent：已完成。适合 LLM，因为它只做审阅增强，风险可由 output_guard 控制。
2. ValidationAgent：下一步可考虑。它生成验证计划，风险低于 marker 结论生成。
3. LiteratureAgent：可用于摘要增强，但 DOI 必须来自输入 evidence。
4. MarkerRecommendationAgent：最后再考虑。它最接近 SNP/InDel/KASP/CAPS 业务结论，风险最高。
5. FinalQAAgent：不建议 LLM 化，应保持规则化。

## 4. 新增 Agent 标准流程

1. 新建 `src/breeding_agent/agents/<name>_agent.py`。
2. 使用 `AgentOutput` / `run_with_context(context)` 统一接口。
3. 在 `agents/prompt_templates.py` 增加 prompt 模板。
4. 在 `agents/context_builder.py` 增加必要 context 字段。
5. 在 LangGraph 中新增 node，写入 `graph_trace`。
6. 明确 fallback 规则。
7. 写单元测试，覆盖正常输出、缺输入、边界约束。
8. 如需要展示，再更新 Gradio；不要把业务逻辑写进 Gradio。
9. 更新 README、AGENTS、developer 文档。

## 5. 分支开发规范

- 每个 Agent 一个功能分支，例如 `feature/validation-agent-llm-review`。
- 不要在 Agent 分支里改 RNA-seq DEG workflow。
- 不要改 `workflows/rnaseq_deg/R/differential_expression_limma_voom.R`。
- 不要提交 `outputs/`。
- 不要提交 `data/private/`。
- 不要提交 `configs/llm.local.yaml`。
- 如果两个同学同时改 LangGraph node，先约定 node 名称和 state 字段，避免冲突。
- 如果需要改 report 或 QA，先说明业务原因，因为这些文件承载学长硬性要求。

## 6. Agent 输出安全边界

所有 Agent 必须遵守：

- 不伪造 SNP/InDel 位点。
- 不伪造 DOI。
- LowQual 不得作为优先推荐。
- preliminary KASP/CAPS 不等于最终标记、最终引物或最终酶切方案。
- Candidate variant calling 不能替代 WGS/GBS 群体变异检测。
- Promoter scaffold 不生成真实启动子序列。
- LLM 输出不能覆盖规则 QA 和 FinalQAAgent。

## 7. LangGraph node trace 要求

每个新增 node 至少记录：

- `node_name`
- `agent_name`
- `input_summary`
- `output_summary`
- `evidence_used`
- `warnings`
- `limitations`
- `passed`

LLM node 还应记录：

- `llm_reviewer_enabled` 或类似开关名
- `llm_used`
- `fallback_used`
- `model`
- `guard_passed`
- `fallback_reason`

## 8. Gradio 展示原则

- Gradio 只展示和触发 workflow，不实现业务规则。
- Refresh 按钮只读取已有输出，不重新运行 workflow。
- 不在页面中展示敏感 config 内容。
- 不上传 BAM、FASTA、代谢组大表。

## 9. Review 清单

提交前确认：

- 新 Agent 是否有规则 fallback。
- LLM 输出是否经过 guard。
- QA 是否仍通过。
- 报告是否保留 `群体`、三个固定基因、统计值、DOI、SNP/InDel/KASP/CAPS。
- 是否没有修改禁止文件。

## 10. Lobster External Agent Benchmark

当前实现新增了 `src/breeding_agent/external_agents/` 和 `workflows/lobster_external_agent_benchmark.py`，用于建立 Lobster-style 外部多组学 Agent 对照评测。

定位：

- 这是 external reference / mock benchmark，不是内部 Agent 主流程。
- 参考对象是 `https://github.com/the-omics-os/lobster`。
- 当前不安装 Lobster、不导入 Lobster、不真实运行 Lobster。
- 输出中必须保留 `backend_name=lobster_ai_reference`、`backend_mode=mock_reference`、`real_lobster_run=false`。

后续接入真实 Lobster adapter 时建议：

1. 单独开分支，不和内部 Agent 改动混在一起。
2. 先实现只读 adapter，把本项目 evidence 转成 Lobster 输入。
3. 真实运行 Lobster 的结果只能进入 comparison 层，不直接覆盖内部 MarkerRecommendationAgent 输出。
4. 保留内部 FinalQAAgent 和 evidence traceability。
5. 继续在报告中说明 KASP/CAPS 是 preliminary screening，variant calling 不能替代 WGS/GBS 群体检测。

避免冲突原则：

- 不改 `graphs/flavonoid_marker_graph.py` 主线节点。
- 不改 LLM ReviewerAgent。
- 不改 Deep Agents POC。
- 不改 Gradio。
- 不提交真实外部框架生成的大型中间数据。
