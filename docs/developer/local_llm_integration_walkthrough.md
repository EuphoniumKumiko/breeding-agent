# 本地 LLM 接入复现指南

适用读者：需要复现 LM Studio / Qwen 本地 ReviewerAgent 接入的同学。  
阅读目标：理解本地 LLM 从配置、调用、guard、fallback 到 trace 展示的全过程。

## 1. 当前实现定位

当前实现只把本地 OpenAI-compatible LLM 接入 LangGraph workflow 的 `ReviewerAgent`。它不替代规则版 workflow，不直接生成 SNP/InDel/KASP/CAPS 结论，不调用外部 API。

已验证的真实运行状态：

- Windows LM Studio 部署 Qwen3.5-9B。
- Debian VM 访问 `http://192.168.1.4:1234/v1`。
- model 为 `qwen/qwen3.5-9b`。
- `llm_reviewer_enabled=true`
- `llm_used=true`
- `fallback_used=false`
- `guard_passed=true`
- `qa_check.json passed=true`

## 2. Windows LM Studio 部署

当前实现使用 LM Studio 的 OpenAI-compatible server：

```text
base_url = http://192.168.1.4:1234/v1
model = qwen/qwen3.5-9b
```

关键点：

- LM Studio 在 Windows 宿主机启动模型服务。
- Debian VM 通过局域网 IP 访问 Windows。
- 如果 VM 无法访问，先检查 Windows 防火墙、LM Studio server 是否监听局域网、VM 网络模式和代理设置。

## 3. Debian VM 调用方式

CLI：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_llm_real \
  --variant-calling-dir outputs/genomics_variant_calling \
  --use-llm-reviewer \
  --llm-config configs/llm.local.yaml
```

Gradio：

- 打开 `谷子黄酮候选标记推荐` Tab。
- 在 LangGraph 小节勾选 `Use LLM Reviewer`。
- `LLM Config Path` 填 `configs/llm.local.yaml`。
- 点击 `Run LangGraph Workflow`。

## 4. 配置文件

`configs/llm.local.example.yaml` 是可提交示例配置，默认 `enabled=false`。

`configs/llm.local.yaml` 是本地真实配置，不应提交 Git。原因：

- 可能包含本地 IP、端口、模型名、内部服务路径。
- 不同同学机器配置不同。
- 误提交后会让 CI 或其他环境误连本地服务。

关键字段：

```yaml
enabled: true
provider: openai_compatible
base_url: http://192.168.1.4:1234/v1
model: qwen/qwen3.5-9b
temperature: 0.1
max_tokens: 1200
chat_template_kwargs:
  enable_thinking: false
enabled_agents:
  - reviewer_agent
```

## 5. 为什么 `enable_thinking=false`

当前 ReviewerAgent 只需要可审计的审阅文本，不需要模型输出长推理链。`enable_thinking=false` 让本地 Qwen 服务尽量返回最终审阅内容，减少不可控文本进入 guard 和报告。

## 6. 为什么先接 ReviewerAgent

ReviewerAgent 是最适合首个 LLM 接入的 Agent：

- 它只做审阅增强，不生产候选位点。
- 规则版 ReviewerAgent 先运行，LLM 只能补充审阅提示。
- output_guard 可以拦截伪造 DOI、伪造坐标、LowQual overclaim 和 preliminary KASP/CAPS overclaim。
- 失败时可以无损 fallback 到规则版 ReviewerAgent。

## 7. 调用链

```text
LangGraph reviewer_agent_node
-> FlavonoidReviewerAgent.run_with_context()
-> llm/executor.py
-> llm/openai_compatible_adapter.py
-> LM Studio / Qwen3.5-9B
-> llm/output_guard.py
-> FlavonoidReviewerAgent.add_llm_review()
-> FinalQAAgent
```

## 8. output_guard 兜底

`output_guard.py` 检查：

- DOI 是否来自输入或报告已有文本。
- 是否出现疑似新 SNP/InDel 坐标。
- LowQual 是否被写成优先推荐。
- preliminary KASP/CAPS 是否被写成最终标记、最终引物或最终酶切方案。
- 是否保留不能替代 WGS/GBS 群体变异检测的限制。

guard 不通过时，LLM 输出被丢弃，workflow 使用规则版 ReviewerAgent。

## 9. 空内容 fallback

如果本地服务返回空 content，fallback reason 为 `empty_final_content`。这能避免空审阅文本覆盖规则版审阅结果。

## 10. 为什么不能让 LLM 直接生成 SNP/InDel/KASP/CAPS

SNP/InDel/KASP/CAPS 涉及真实位点、引物和实验方案。当前项目的证据来自 mini 数据包、候选区域 calling 和已有 literature evidence，尚未完成 WGS/GBS 群体变异检测和实验验证。让 LLM 直接生成结论会带来伪造位点和过度声明风险。

## 11. 后续扩展

可考虑：

- ValidationAgent：让 LLM 优化验证计划措辞，但不宣称验证已完成。
- LiteratureAgent：让 LLM 做摘要增强，但 DOI 必须来自 evidence。
- MarkerRecommendationAgent：最后考虑，且必须有更强 guard。

不建议：

- FinalQAAgent LLM 化。它应保持规则化终检。

## 12. 切换后端

只要提供 OpenAI-compatible `/v1/chat/completions`，理论上可切换：

- LM Studio
- Ollama OpenAI-compatible endpoint
- vLLM
- SGLang

切换时只改本地 `configs/llm.local.yaml`，不要改业务代码；也不要提交该本地配置。
