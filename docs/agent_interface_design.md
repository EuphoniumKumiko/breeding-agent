# LLM-ready Agent Interface 设计说明

## 1. 当前定位

当前 flavonoid marker agent layer 仍以规则化实现为默认执行路径，不调用外部 API，不接真实大模型 SDK。LLM-ready interface 已把输入、输出、prompt 模板和 fallback 规则整理清楚，并已被 LangGraph 主线 workflow 和 Deep Agents POC 复用。真实 OpenAI / 本地开源大模型接入仍是下一阶段工作。

生产路径仍然是 deterministic rule-based fallback：

```text
FlavonoidCentralHost
  -> context_builder
  -> LiteratureAgent
  -> MarkerRecommendationAgent
  -> ValidationAgent
  -> ReviewerAgent
  -> FinalQAAgent
```

## 2. 为什么先做接口

先做接口而不接真实模型有三个原因：

- 复现性：当前报告、候选表和 QA 必须稳定生成，`qa_check.json` 必须继续 `passed=true`。
- 安全边界：黄酮标记推荐不能伪造 DOI，不能伪造 SNP/InDel 位点，不能把 LowQual 或 preliminary screening 写成最终标记。
- 可替换性：未来模型调用应只是 agent 的可选 adapter；没有模型、模型失败或输出不合规时，仍回到规则版结果。

## 3. 核心接口

新增文件：

```text
src/breeding_agent/agents/base.py
```

核心对象：

- `AgentInput`：包含 `agent_name`、结构化 `context`、`prompt_template` 和可选参数。
- `AgentOutput`：统一输出，包含 `agent_name`、`summary`、`evidence_used`、`warnings`、`limitations` 和 `structured_payload`。
- `AgentResult`：记录输入、输出、是否使用 fallback、是否启用 LLM 和原始响应。
- `BaseAgent`：定义 `run_with_context(context)`。
- `RuleBasedAgent`：当前规则 fallback 的基类。
- `LLMReadyAgentMixin`：只提供 prompt 构建和空的 `invoke_llm()` hook，不调用模型。

旧 `run()` 调用保持兼容；新接口通过 `run_with_context(context)` 返回 `AgentOutput`。

## 4. Prompt 模板

新增文件：

```text
src/breeding_agent/agents/prompt_templates.py
```

包含：

- `literature_agent_prompt`
- `marker_recommendation_agent_prompt`
- `validation_agent_prompt`
- `reviewer_agent_prompt`
- `final_qa_agent_prompt`

所有模板都包含硬性限制：

- 不伪造 SNP/InDel 位点。
- 不伪造 DOI。
- LowQual 不得优先推荐。
- preliminary KASP/CAPS 不等于最终标记、最终引物或最终酶切方案。
- 当前候选区域 variant calling 不能替代 WGS/GBS 群体变异检测。
- 最终报告必须保留学长硬性要求和固定结论句。

## 5. Context Builder

新增文件：

```text
src/breeding_agent/agents/context_builder.py
```

`build_flavonoid_agent_context()` 会读取并汇总：

- `transcriptome_evidence.tsv`
- `metabolome_evidence.tsv`
- `annotation_evidence.tsv`
- `genome_variant_evidence.tsv`
- `literature_evidence.tsv`
- 可选 `variant_calling_dir/tables/` 下的 variant evidence
- aggregation 后的 `candidate_rows`

输出是结构化 `dict`，包括：

- `target_genes`
- `hard_requirements`
- 各 evidence rows
- `evidence_by_gene`
- `variant_calling`
- `warnings`

它不做 LLM 调用，也不读取 `data/private/` 大文件到 agent prompt；只使用已整理的小型 evidence TSV 和候选表。

## 6. 每个 Agent 的职责

- `FlavonoidLiteratureAgent`：读取文献 evidence，原样展示 DOI，不补写 DOI。
- `FlavonoidMarkerRecommendationAgent`：根据 `variant_status` 和 `variant_evidence_status` 生成 SNP/InDel/KASP/CAPS 推荐。
- `FlavonoidValidationAgent`：输出 Sanger、SNP/InDel calling、KASP、CAPS/dCAPS、群体关联、qRT-PCR、LC-MS/MS 验证计划。
- `FlavonoidReviewerAgent`：检查缺失统计值、缺失 DOI、伪造位点、LowQual 过度推荐、preliminary KASP/CAPS 过度解释和 WGS/GBS 过度声明。
- `FlavonoidFinalQAAgent`：复用 `check_flavonoid_marker_report()`，不重复实现 QA。
- `FlavonoidCentralHost`：构建 context，顺序调度 agents，保留规则 fallback metadata。

## 7. 未来接入方式

未来如果接 OpenAI 或本地模型，推荐做法：

1. 保留当前 `RuleBasedAgent` 作为 fallback。
2. 新增独立 adapter，把 `AgentInput` 转成模型请求，把模型输出解析为 `AgentOutput`。
3. adapter 失败、超时、输出缺少硬性字段或违反限制时，丢弃模型结果并使用规则版输出。
4. 模型输出进入报告前仍必须经过 `ReviewerAgent` 和 `FinalQAAgent`。

LangGraph 已作为主线开源智能体编排框架接入：它只把现有 agent 节点化，不改变 evidence schema、报告 QA、CLI 参数或规则 fallback。Deep Agents 已有并行 POC，用于验证更高层 harness 接入；它不替代 LangGraph。两者当前都不调用真实 LLM。

## 8. 当前不接真实大模型的原因

当前任务目标是科研可复现 workflow。真实模型调用会带来网络、权限、版本、成本和不可重复输出问题；也可能引入伪造 DOI、伪造 SNP/InDel 位点或过度解释 LowQual / preliminary screening 的风险。因此当前只完成 interface、prompt、context、LangGraph 编排和 Deep Agents POC；ReviewerAgent + Ollama/Qwen 或其他本地开源大模型 adapter 需要单独阶段接入和评审。

## 9. Fallback 意义

规则 fallback 确保：

- 无外部服务也能运行。
- 旧 CLI 保持兼容。
- 可选 variant evidence 接入保持稳定。
- `qa_check.json` 继续 `passed=true`。
- 生物学边界不被模型输出覆盖。
