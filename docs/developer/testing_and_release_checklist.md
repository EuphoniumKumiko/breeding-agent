# 测试与发布前检查清单

适用读者：准备提交 PR、交付阶段结果或让其他同学复现实验的开发者。  
阅读目标：统一提交前命令、禁止提交项和常见 workflow 验证步骤。

## 1. 基础 Git 检查

```bash
git status --short --untracked-files=all
git diff --stat
```

确认没有误提交：

- `outputs/`
- `data/private/`
- `configs/llm.local.yaml`
- BAM / BAI / FASTA / index / 大型中间文件

检查关键禁止文件是否被误改：

```bash
git diff -- src/breeding_agent/workflows/rnaseq_deg.py \
  workflows/rnaseq_deg/R/differential_expression_limma_voom.R
```

## 2. py_compile 模板

如果改了 Python 文件：

```bash
python3 -m py_compile <changed_python_files>
```

示例：

```bash
python3 -m py_compile \
  src/breeding_agent/web/gradio_app.py \
  src/breeding_agent/cli/flavonoid_markers_graph.py
```

如果只改 Markdown，说明“不适用，因为没有修改 Python 文件”。

## 3. unittest 模板

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

不要在文档中硬编码测试数量；以实际运行输出为准。

## 4. 旧黄酮推荐 CLI

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package
```

带 variant evidence：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package \
  --variant-calling-dir outputs/genomics_variant_calling
```

检查：

```bash
cat outputs/flavonoid_marker_from_package/logs/qa_check.json
```

## 5. LangGraph CLI

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph \
  --variant-calling-dir outputs/genomics_variant_calling
```

如果未安装 `langgraph`，应提示：

```text
LangGraph is not installed. Install with: pip install langgraph
```

## 6. LangGraph + LLM Reviewer CLI

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph_llm_real \
  --variant-calling-dir outputs/genomics_variant_calling \
  --use-llm-reviewer \
  --llm-config configs/llm.local.yaml
```

检查：

```bash
grep -R "llm_reviewer_enabled\\|llm_used\\|fallback_used\\|guard_passed\\|fallback_reason\\|model=" \
  -n outputs/flavonoid_marker_langgraph_llm_real/graph
cat outputs/flavonoid_marker_langgraph_llm_real/logs/qa_check.json
```

预期边界：

- LLM 只增强 ReviewerAgent。
- output_guard 和 FinalQAAgent 仍生效。
- 不直接生成 SNP/InDel/KASP/CAPS 结论。

## 7. Deep Agents POC CLI

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_deepagents \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_deepagents \
  --variant-calling-dir outputs/genomics_variant_calling
```

未安装 Deep Agents 时应清晰提示，不影响旧 CLI 和 LangGraph CLI。

## 8. Promoter Design scaffold CLI

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.promoter_design \
  --gene-id Si9g04210.1 \
  --gene-sequence ATGCGTACGTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGC \
  --gene-function "flavonoid-related candidate gene" \
  --species foxtail_millet \
  --target-expression-level high \
  --outdir outputs/promoter_design_demo
```

检查报告是否明确说明：当前不是 promoter generator，不生成真实启动子序列。

## 9. Gradio 启动

```bash
PYTHONPATH=src python3 -m breeding_agent.web.gradio_app
```

开发热重载：

```bash
GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 \
PYTHONPATH=src gradio src/breeding_agent/web/gradio_app.py
```

## 10. 提交信息建议

格式：

```text
docs: sync developer codebase guide
feat: add local llm reviewer guard metadata
fix: preserve llm reviewer flag in langgraph state
```

提交前再次确认：

- 是否只改了任务允许的文件。
- 是否保留能力边界。
- 是否没有把 private data、outputs 或本地 LLM config 放进 Git。
