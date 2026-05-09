# Flavonoid Marker Aggregation 使用说明

适用读者：需要运行或维护普通黄酮候选标记推荐 workflow 的同学。  
阅读目标：理解规则版 aggregation 的输入输出、Agent 调用和与 LangGraph / LLM Reviewer 的关系。

## Workflow 定位

`flavonoid_marker_aggregation` 是谷子黄酮候选标记推荐的规则版、模板版、可复现 workflow，并带有 DeepRare-like lightweight agent layer。它读取已经标准化的 evidence TSV，聚合固定重点基因 `Si9g04210.1`、`Si5g31340.1`、`Si9g34380.1`，并生成候选表、Markdown 报告、QA JSON 和 manifest。

核心结论为：

```text
优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。
```

## 和 RNA-seq DEG Workflow 的关系

现有 RNA-seq DEG workflow 负责从 BAM 和 GFF 复现差异表达分析，并生成 transcriptomics evidence。flavonoid marker aggregation 不修改、不调用、不替代现有 DEG workflow；它只读取上游已经整理好的 flavonoid marker evidence 文件，用于跨转录组、代谢组、基因组/变异、功能注释和文献查阅 evidence 的报告聚合。

## 生成学长数据包 Evidence

先从本地 mini 数据包生成标准 evidence：

```bash
PYTHONPATH=src python3 scripts/demo/create_flavonoid_marker_evidence_from_package.py \
  --dataset-dir data/private/flavonoid_marker_mini_5genes_50kb \
  --outdir outputs/flavonoid_marker_from_package/evidence
```

输入数据来自学长要求的核心文件：

- 转录组：`bam/` 中所有文件
- 代谢组：`metabolome_raw_3372.tsv`
- 基因组：`genome.fa` 和 `genome.gff`
- 功能注释：`local_region_emapper_annotations.tsv`

转换后的标准 evidence 位于：

```text
outputs/flavonoid_marker_from_package/evidence/
├── transcriptome_evidence.tsv
├── metabolome_evidence.tsv
├── annotation_evidence.tsv
├── genome_variant_evidence.tsv
└── literature_evidence.tsv
```

## 运行 Aggregation CLI

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_from_package
```

该旧 CLI 不调用外部 API，不调用真实 LLM，也不依赖 LangGraph 或 Deep Agents。可通过 `--variant-calling-dir outputs/genomics_variant_calling` 可选接入已生成的 candidate variant calling evidence。

## DeepRare-like lightweight agent layer

当前 agent 层是规则版编排层，不调用 LLM，不调用外部 API。它的目标是把 aggregation workflow 拆成可审阅的角色模块，而不是改变 CLI 或输出结构。LangGraph 主线 workflow 和 Deep Agents POC 都复用这一层，但不改变旧 CLI 的默认行为。

已实现模块：

```text
src/breeding_agent/agents/
├── flavonoid_central_host.py
├── flavonoid_literature_agent.py
├── flavonoid_marker_recommendation_agent.py
├── flavonoid_validation_agent.py
├── flavonoid_reviewer_agent.py
└── flavonoid_final_qa_agent.py
```

角色分工：

- `FlavonoidCentralHost`：DeepRare-like central host，组织 evidence 聚合、文献查阅、标记推荐、验证方案、review 和 final QA。
- `FlavonoidLiteratureAgent`：读取 `literature_evidence.tsv`，原样展示 DOI，不编造 DOI。
- `FlavonoidMarkerRecommendationAgent`：根据 candidate evidence 和 `variant_status` 推荐 SNP/InDel/KASP/CAPS；`variant_status=not_called` 时明确说明没有最终 SNP/InDel 位点。
- `FlavonoidValidationAgent`：生成 Sanger、候选区域 SNP/InDel calling、KASP、CAPS/dCAPS、群体关联分析、qRT-PCR 和 LC-MS/MS 验证方案。
- `FlavonoidReviewerAgent`：检查过度推断、缺失统计值、缺失 DOI、缺失验证方案和疑似伪造 variant 位点。
- `FlavonoidFinalQAAgent`：包装复用 `src/breeding_agent/integration/flavonoid_marker_qa.py`，不重复实现冲突 QA 逻辑。

当前已经通过明确 adapter 将本地 OpenAI-compatible LLM 接入 LangGraph 的 `ReviewerAgent`，只做审阅增强。普通 aggregation CLI 仍保持规则版，不调用 LLM。未来如扩展到其他 Agent，仍必须保留规则 fallback，并遵守：不伪造 DOI、不伪造 SNP/InDel 位点、`variant_status=not_called` 时不能输出具体位点。

## LangGraph 和 Deep Agents POC

LangGraph 是当前主线开源智能体编排框架：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_graph \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_langgraph \
  --variant-calling-dir outputs/genomics_variant_calling
```

Deep Agents POC 是并行 harness 验证入口，不替代 LangGraph：

```bash
PYTHONPATH=src python3 -m breeding_agent.cli.flavonoid_markers_deepagents \
  --evidence-dir outputs/flavonoid_marker_from_package/evidence \
  --outdir outputs/flavonoid_marker_deepagents \
  --variant-calling-dir outputs/genomics_variant_calling
```

## 输出文件位置

```text
outputs/flavonoid_marker_from_package/
├── integration/
│   └── flavonoid_marker_candidates.tsv
├── reports/
│   └── flavonoid_marker_report.md
├── logs/
│   └── qa_check.json
└── manifest.json
```

`flavonoid_marker_candidates.tsv` 包含每个重点基因的转录组统计值、代谢物相关证据、功能注释、KEGG/pathway、variant_status 和 SNP/InDel/KASP/CAPS 标记建议。

## 查看 QA 结果

查看规则 QA：

```bash
cat outputs/flavonoid_marker_from_package/logs/qa_check.json
```

QA 会检查：

- 三个固定重点基因是否出现
- 是否包含“群体”“文献查阅”“DOI”“SNP”“InDel”“KASP”“CAPS”
- 每个重点基因是否展示统计学数值
- 是否展示 DOI
- 是否给出 SNP/InDel/KASP/CAPS 标记类型建议

## 为什么当前版本不伪造 SNP/InDel 位点

当前 mini 数据包没有提供最终 SNP/InDel calling 结果表，也没有提供已经筛选好的 KASP/CAPS 位点。因此 `genome_variant_evidence.tsv` 中保留：

```text
variant_status=not_called
```

报告会明确说明：当前 mini 数据包未提供最终 SNP/InDel 位点；建议后续基于 BAM、`genome.fa/genome.gff` 或 `genome.bam_compatible.fa.gz` 与 `genome.original_coords.gff` 进行候选区域 SNP/InDel calling，再筛选 KASP/CAPS 可转化位点。

这样可以区分“已有多组学候选证据”和“尚未完成正式变异位点 calling”，避免把未验证位置写成正式 marker。
