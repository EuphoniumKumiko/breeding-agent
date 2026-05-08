# Testing and Validation 导读

## 1. 模块作用

本文件说明当前项目如何做基本验证。它适合每次改代码或文档后做提交前检查，也适合新人理解测试覆盖了哪些行为。

当前测试主要覆盖：

- Flavonoid marker QA 规则。
- Flavonoid lightweight agent layer。
- Metabolomics 和 Genomics workflow 的输出文件与缺文件行为。

## 2. 当前测试目录说明

```text
tests/
├── test_flavonoid_agent_layer.py
├── test_flavonoid_marker_qa.py
└── test_omics_modules.py
```

### `test_flavonoid_marker_qa.py`

验证 `check_flavonoid_marker_report()`：

- 完整报告应通过 QA。
- 缺少固定基因会失败。
- 缺少 `群体` 会失败。
- 缺少 DOI 会失败。
- 缺少统计值会失败。

### `test_flavonoid_agent_layer.py`

验证 agent layer：

- Literature agent 能返回 DOI review text。
- Marker recommendation agent 在 `variant_status=not_called` 时不伪造坐标。
- Validation agent 输出包含群体、Sanger、SNP/InDel calling、KASP、CAPS/dCAPS、qRT-PCR、LC-MS/MS。
- Final QA agent 能通过完整报告。
- Flavonoid marker CLI 能用真实 evidence 跑通并生成 QA。

### `test_omics_modules.py`

验证代谢组和基因组模块：

- 有学长数据包时能生成输出文件。
- 基因组 `marker_readiness.tsv` 包含三个固定重点基因。
- `variant_status=not_called`。
- 缺少部分输入时不会直接崩溃，而是返回 warning。

## 3. 如何运行 unittest

在项目根目录运行：

```bash
cd ~/projects/breeding-agent
PYTHONPATH=src python3 -m unittest discover -s tests
```

成功时会看到类似：

```text
Ran 16 tests
OK
```

如果 `data/private/flavonoid_marker_mini_5genes_50kb` 不存在，部分 omics package tests 会被 skip，这是测试中显式写的行为。

## 4. 如何运行 py_compile

如果修改了 Python 文件，运行：

```bash
python3 -m py_compile <changed_python_files>
```

例如只改了 Gradio：

```bash
python3 -m py_compile src/breeding_agent/web/gradio_app.py
```

如果只修改 Markdown 文档，可以说明：

```text
py_compile 不适用，因为本次只修改 Markdown 文档。
```

## 5. 如何运行 flavonoid marker CLI 验证

先确认 evidence 目录存在：

```text
outputs/flavonoid_marker_from_package/evidence
```

运行：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package
```

成功时会输出：

```text
[flavonoid-markers] qa passed: True
```

## 6. 如何检查 qa_check.json

查看：

```bash
cat outputs/flavonoid_marker_from_package/logs/qa_check.json
```

重点看：

- `passed`
- `missing_items`
- `gene_check`
- `statistics_check`
- `has_doi`
- `has_marker_types`

通过条件通常应为：

```text
passed=true
```

如果失败，根据 `missing_items` 定位缺少内容。

## 7. 如何确认没有修改 RNA-seq DEG workflow 和 R workflow

查看 Git 状态：

```bash
git status --short
git diff --stat
git diff --name-only
```

确认不应出现：

```text
src/breeding_agent/workflows/rnaseq_deg.py
workflows/rnaseq_deg/R/differential_expression_limma_voom.R
```

如果出现，除非任务明确要求，否则不要提交这些修改。

## 8. Git 提交前检查清单

提交前检查：

- `git status --short`
- `git diff --stat`
- 如果改 Python：`python3 -m py_compile <changed_python_files>`
- 如果改 workflow 或集成逻辑：`PYTHONPATH=src python3 -m unittest discover -s tests`
- 如果改 flavonoid marker 逻辑：运行 flavonoid marker CLI，并检查 `qa_check.json`
- 确认没有提交 `data/private/`
- 确认没有提交 `outputs/`
- 确认没有提交 BAM、BAI、FASTA、FASTA index
- 确认没有伪造 DOI
- 确认没有伪造 SNP/InDel 位点
- 确认没有无意修改 RNA-seq DEG workflow 或 R workflow

## 9. 常见问题

### 为什么只改文档也要看 git status？

因为项目里有 `data/private/` 和 `outputs/`，很容易误把本地数据或运行结果混入变更。

### 为什么 QA 不是 pytest？

当前测试使用 Python 标准库 `unittest`，不需要额外测试依赖。

### 为什么 tests 里会引用 outputs 下的 evidence？

当前 agent layer 测试使用已经生成的标准 evidence 作为真实输入。不要把 `outputs/` 当成需要提交的内容；测试环境中应提前准备好对应 evidence。

### 为什么要单独跑 flavonoid marker CLI？

unittest 会覆盖一部分 CLI 行为，但手动跑真实输出目录可以确认最终 report、candidate table、QA JSON 和 manifest 都在预期位置。

## 10. 学习建议

先读 `tests/test_flavonoid_marker_qa.py`，因为它最短，能快速理解项目硬性质量要求。再读 `tests/test_flavonoid_agent_layer.py`，理解 agent layer 的边界。最后读 `tests/test_omics_modules.py`，理解代谢组和基因组模块为什么要在缺文件时返回 warning 而不是崩溃。
