# 本地 OpenAI-compatible ReviewerAgent 接入说明

适用读者：需要复现本地 LM Studio / Qwen 接入、调试 LLM Reviewer 或检查 Gradio 状态展示的同学。  
阅读目标：明确本地 LLM Reviewer 的配置、调用方式、Gradio 展示、安全边界和 fallback 行为。

## 1. 定位

本功能只增强 LangGraph flavonoid marker workflow 中的 `ReviewerAgent`。默认不开启；不传 `--use-llm-reviewer` 时 workflow 完全不请求本地模型。

当前接入的是本地 OpenAI-compatible chat completions 后端，例如 LM Studio 暴露的 `/v1/chat/completions`。代码不绑定 Ollama、不引入 OpenAI SDK、不调用外部 API。

## 2. 配置

示例配置：

```text
configs/llm.local.example.yaml
```

关键字段：

- `provider`: 当前支持 `openai_compatible`。
- `base_url`: 本地 OpenAI-compatible `/v1` 地址。
- `model`: 本地模型名。
- `temperature`
- `max_tokens`
- `timeout_seconds`
- `chat_template_kwargs.enable_thinking`: 必须传递为 `false`。
- `enabled_agents`: 目前只允许 `reviewer_agent`。

`configs/llm.local.example.yaml` 默认 `enabled: false`，避免误触发模型请求。真正调用由 CLI 参数 `--use-llm-reviewer` 显式控制。

## 3. 运行命令

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_llm \
  --variant-calling-dir outputs/genomics_variant_calling \
  --use-llm-reviewer \
  --llm-config configs/llm.local.example.yaml
```

不传 `--use-llm-reviewer` 时，LangGraph workflow 仍按规则化 agents 运行。

## 4. Gradio 展示

Gradio 的 `谷子黄酮候选标记推荐` Tab 中，`LangGraph Multi-agent Workflow（LangGraph 多智能体聚合流程）` 小节已新增：

- `Use LLM Reviewer`
- `LLM Config Path`
- `LLM Reviewer Status`

`Use LLM Reviewer` 默认关闭。关闭时不调用本地模型；开启时 Gradio 只把配置路径传给 LangGraph workflow，不读取或展示配置文件内容。`Refresh LangGraph Results` 会从已有 `graph_trace.json`、`graph_state_final.json` 或 manifest 中读取 LLM Reviewer 状态。

## 5. 安全边界

LLM 只做审阅增强，不直接生成 SNP/InDel/KASP/CAPS 结论。`output_guard` 会检查：

- 不伪造 DOI。
- 不伪造 SNP/InDel 坐标。
- LowQual 不得作为优先推荐。
- preliminary KASP/CAPS 不得写成最终标记、最终引物或最终酶切方案。
- 必须保留当前结果不能替代 WGS/GBS 群体变异检测的限制说明。

如果 LLM 请求失败、返回空内容或 guard 不通过，会 fallback 到规则版 `ReviewerAgent`。

## 6. Trace 字段

LangGraph 的 `graph_trace.json`、`node_decision_table.tsv` 和 `langgraph_summary.md` 会在 reviewer node 中记录：

- `llm_reviewer_enabled`
- `llm_used`
- `fallback_used`
- `model`
- `guard_passed`
- `fallback_reason`

这些字段用于确认是否实际使用本地模型，以及是否触发规则 fallback。

## 7. 当前限制

- 只增强 `reviewer_agent_node`。
- 不改变 aggregation、variant evidence、marker recommendation 或 QA 业务逻辑。
- 不接入真实外部 LLM 服务。
- Gradio 只展示状态和传递 config path，不读取配置内容。
- 不替代人工审阅和实验验证。
