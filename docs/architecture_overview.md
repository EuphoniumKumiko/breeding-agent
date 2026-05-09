# breeding-agent 架构总览

## 项目定位

`breeding-agent` 是一个面向谷子多组学育种分析的本地可复现项目。当前已经实现的能力集中在两条主线：

- RNA-seq DEG reproduction workflow：从本地 BAM 和 GFF 输入复现差异表达分析，并生成报告、标准化 transcriptomics evidence、候选基因表和 provenance。
- 谷子黄酮候选标记推荐：基于学长 mini 数据包整理出的 transcriptome、metabolome、annotation、genome variant 和 literature evidence，给出 SNP/InDel/KASP/CAPS 候选标记类型建议。

项目根目录当前没有 `README.md`。新人应优先阅读：

- `AGENTS.md`
- `docs/project_onboarding.md`
- 本文档
- `docs/code_reading_guide.md`

## 当前已实现能力

已实现：

- `src/breeding_agent/cli/deg.py`：RNA-seq DEG CLI。
- `src/breeding_agent/workflows/rnaseq_deg.py`：RNA-seq DEG workflow 编排。
- `workflows/rnaseq_deg/R/differential_expression_limma_voom.R`：limma-voom 差异表达 R 脚本。
- `scripts/demo/create_flavonoid_marker_evidence_from_package.py`：从学长 mini 数据包生成标准 flavonoid marker evidence。
- `src/breeding_agent/cli/flavonoid_markers.py`：黄酮候选标记 aggregation CLI。
- `src/breeding_agent/workflows/flavonoid_marker_aggregation.py`：黄酮候选标记 aggregation workflow。
- `src/breeding_agent/agents/`：规则版 DeepRare-like lightweight agent layer。
- `src/breeding_agent/graphs/`：可选 LangGraph 版黄酮候选标记 graph 编排。
- `src/breeding_agent/cli/flavonoid_markers_graph.py`：并行 LangGraph workflow CLI。
- `src/breeding_agent/modules/metabolomics/`：代谢组 evidence analysis 后端。
- `src/breeding_agent/modules/genomics/`：基因组候选区域和 marker readiness 后端。
- `src/breeding_agent/web/gradio_app.py`：本地 Gradio 工作台。
- `tests/`：规则 QA、agent layer、omics modules 的 unittest。

计划中或未完成：

- 完整原始质谱峰表重分析：计划中，当前代谢组模块只读取已有结果表。
- 正式 SNP/InDel calling：计划中，当前基因组模块不输出具体 SNP/InDel 坐标。
- 基于大群体基因型和黄酮含量的关联验证：计划中。
- 外部文献 API 或 LLM 文献检索：未接入，当前只读取已有 `literature_evidence.tsv`。

## 整体数据流

### RNA-seq DEG 数据流

```text
本地 BAM + GFF
  -> src/breeding_agent/cli/deg.py
  -> src/breeding_agent/workflows/rnaseq_deg.py
  -> validators/
  -> featureCounts
  -> workflows/rnaseq_deg/R/differential_expression_limma_voom.R
  -> reports/deg_report.py
  -> integration/transcriptomics_standardizer.py
  -> integration/candidate_aggregator.py
  -> integration/recommendation_report.py
  -> manifest.json + run.log + provenance/
```

### 学长数据包到黄酮标记推荐数据流

```text
data/private/flavonoid_marker_mini_5genes_50kb/
  -> scripts/demo/create_flavonoid_marker_evidence_from_package.py
  -> integration/flavonoid_marker_package_importer.py
  -> outputs/flavonoid_marker_from_package/evidence/*.tsv
  -> cli/flavonoid_markers.py
  -> workflows/flavonoid_marker_aggregation.py
  -> agents/flavonoid_central_host.py
  -> integration/flavonoid_marker_aggregator.py
  -> reports/flavonoid_marker_report.py
  -> integration/flavonoid_marker_qa.py
  -> outputs/flavonoid_marker_from_package/
```

### Gradio 工作台数据流

```text
src/breeding_agent/web/gradio_app.py
  -> 调用已有 workflow / helper 函数
  -> 读取本地输出文件
  -> 展示状态、表格、Markdown 报告、manifest、QA JSON、日志
```

Gradio 只是展示层和按钮入口，不改变后端分析逻辑。

### LangGraph 版黄酮标记推荐数据流

```text
outputs/flavonoid_marker_from_package/evidence/*.tsv
  -> cli/flavonoid_markers_graph.py
  -> workflows/flavonoid_marker_langgraph.py
  -> graphs/flavonoid_marker_graph.py
  -> load_evidence_node
  -> aggregate_candidates_node
  -> build_agent_context_node
  -> literature / marker / validation / reviewer / final_qa agent nodes
  -> reports/flavonoid_marker_report.py
  -> reports/langgraph_trace_report.py
  -> outputs/flavonoid_marker_langgraph/
```

LangGraph 在本项目中只负责 workflow / agent graph 编排，不负责模型推理。当前不接真实大模型、不接本地开源模型、不接 OpenAI SDK、不接 Deep Agents。

## 模块划分

### CLI

- `src/breeding_agent/cli/deg.py`
  - 解析 `--bam-dir`、`--gff`、`--contrast`、`--prefix`、`--trait`、`--threads`、`--outdir`。
  - 构造 `RnaSeqDegConfig`。
  - 调用 `run_rnaseq_deg_task`。
- `src/breeding_agent/cli/flavonoid_markers.py`
  - 解析 `--evidence-dir` 和 `--outdir`。
  - 构造 `FlavonoidMarkerAggregationConfig`。
  - 调用 `run_flavonoid_marker_aggregation_task`。
- `src/breeding_agent/cli/flavonoid_markers_graph.py`
  - 解析 `--evidence-dir`、`--outdir` 和可选 `--variant-calling-dir`。
  - 构造 `FlavonoidMarkerLangGraphConfig`。
  - 调用 `run_flavonoid_marker_langgraph_task`。
  - 如果未安装 LangGraph，提示 `pip install langgraph`，不影响旧 CLI。

### workflows

- `rnaseq_deg.py`：负责完整 RNA-seq DEG 编排、外部命令、manifest、provenance。
- `metabolomics_evidence.py`：调用代谢组 module，生成报告和 manifest。
- `genomics_region.py`：调用基因组 module，生成报告和 manifest。
- `flavonoid_marker_aggregation.py`：调用 CentralHost、生成报告、写 QA JSON 和 manifest。
- `flavonoid_marker_langgraph.py`：可选 LangGraph workflow wrapper，写 graph trace、node decision table、summary、报告、QA 和 manifest。

### modules

- `modules/metabolomics/metabolomics_evidence.py`
  - 读取学长数据包中已有代谢组表。
  - 复制或写空表头输出。
  - 统计预览、row count、warning。
- `modules/genomics/genomics_region.py`
  - 读取 regions、annotations、target genes 相关表。
  - 输出 target regions、annotation summary、marker readiness。
  - 固定 `variant_status=not_called`。

### integration

- `transcriptomics_standardizer.py`：把 DEG 结果整理为标准 transcriptomics evidence。
- `candidate_aggregator.py`：从标准 evidence 生成候选基因表。
- `recommendation_report.py`：生成第一版 transcriptomics recommendation report。
- `flavonoid_marker_package_importer.py`：从学长数据包 evidence summary 生成五类 flavonoid marker evidence TSV。
- `flavonoid_marker_aggregator.py`：聚合五类 evidence，生成 `flavonoid_marker_candidates.tsv`。
- `flavonoid_marker_qa.py`：规则 QA，检查固定基因、统计值、`群体`、DOI、SNP/InDel/KASP/CAPS 等。

### agents

`src/breeding_agent/agents/` 是规则版 DeepRare-like lightweight agent layer，不调用 LLM，不调用外部 API：

- `FlavonoidCentralHost`：统一编排。
- `FlavonoidLiteratureAgent`：读取已有 DOI evidence，不编造 DOI。
- `FlavonoidMarkerRecommendationAgent`：按 `variant_status` 推荐 SNP/InDel/KASP/CAPS。
- `FlavonoidValidationAgent`：生成验证方案。
- `FlavonoidReviewerAgent`：检查过度推断、缺失 DOI、缺失统计值、疑似伪造坐标等。
- `FlavonoidFinalQAAgent`：复用 canonical QA。

这些 agents 已支持 LLM-ready `run_with_context()` interface，可作为 LangGraph nodes 运行。

### graphs

`src/breeding_agent/graphs/` 是可选 LangGraph 编排层：

- `state.py`：定义 JSON 可序列化的 `FlavonoidGraphState`。
- `flavonoid_marker_graph.py`：定义 `load_evidence_node`、`aggregate_candidates_node`、`build_agent_context_node`、各 agent node、`report_node` 和 `write_outputs_node`。

Graph 输出：

- `graph/graph_trace.json`
- `graph/graph_state_final.json`
- `graph/node_decision_table.tsv`
- `graph/langgraph_summary.md`

### reports

- `deg_report.py`：RNA-seq DEG Markdown 报告。
- `metabolomics_report.py`：代谢组 evidence analysis 报告。
- `genomics_report.py`：基因组 region / annotation 报告。
- `flavonoid_marker_report.py`：黄酮候选标记推荐报告。

### Gradio

- `src/breeding_agent/web/gradio_app.py`
  - 当前使用顶部 `gr.Tab` 页面结构。
  - 包含 `Transcriptomics DEG Module`、`Metabolomics Module`、`Genomics / GWAS Module`、`Integration & Recommendation`、`谷子黄酮候选标记推荐` 五个 Tab。
  - 只接收本地路径，不上传 BAM/FASTA/代谢组大文件。

## 每个模块的输入和输出

### RNA-seq DEG

输入：

- BAM directory
- GFF annotation
- contrast、prefix、trait、threads、outdir

输出：

- `counts/gene_counts_mini.txt`
- `mini_de/<prefix>.significant_genes.tsv`
- `reports/report.md`
- `integration/standardized_evidence.tsv`
- `integration/candidate_gene_table.tsv`
- `integration/recommendation_report.md`
- `logs/run.log`
- `manifest.json`
- `provenance/commands.sh`
- `provenance/checksums.sha256`

### Metabolomics Evidence

输入：

- `metabolome/metabolome_raw_3372.tsv`
- `metabolome/candidate_metabolites.tsv`
- `metabolome/flavonoid_related_significant_metabolites.tsv`
- `metabolome/target_gene_metabolite_network_edges.tsv`
- `metabolome/target_gene_spls_coefficients.tsv`
- `metabolome/target_gene_related_metabolite_abundance.tsv`
- `sample_metadata.tsv`
- `annotations/target_gene_evidence_summary.tsv`

输出：

- `candidate_metabolites.tsv`
- `flavonoid_related_significant_metabolites.tsv`
- `target_gene_metabolite_network_edges.tsv`
- `target_gene_spls_coefficients.tsv`
- `metabolomics_report.md`
- `manifest.json`

### Genomics Region

输入：

- `genome.fa`
- `genome.gff`
- `genome.original_coords.gff`
- `genome.bam_compatible.fa.gz`
- `regions/regions.bed`
- `regions/regions.samtools.txt`
- `regions/deg_features.tsv`
- `target_genes.tsv`
- `annotations/local_region_emapper_annotations.tsv`
- `annotations/target_gene_emapper_annotations.tsv`
- `annotations/target_gene_evidence_summary.tsv`

输出：

- `target_gene_regions.tsv`
- `annotation_summary.tsv`
- `marker_readiness.tsv`
- `genomics_report.md`
- `manifest.json`

`marker_readiness.tsv` 必须包含三个重点基因，且 `variant_status=not_called`。

### Flavonoid Marker Recommendation

输入 evidence：

- `transcriptome_evidence.tsv`
- `metabolome_evidence.tsv`
- `annotation_evidence.tsv`
- `genome_variant_evidence.tsv`
- `literature_evidence.tsv`

输出：

- `integration/flavonoid_marker_candidates.tsv`
- `reports/flavonoid_marker_report.md`
- `logs/qa_check.json`
- `manifest.json`

## CLI / workflow / report / QA / Gradio 的关系

推荐理解方式：

```text
CLI 负责参数解析
workflow 负责调度与 manifest
module / integration 负责核心数据整理
report 负责 Markdown 输出
QA 负责规则检查
Gradio 负责本地页面展示和触发已有入口
```

不要把业务逻辑写进 Gradio 页面。Gradio 页面应该只调用现有 workflow 或读取已有输出。

## 当前限制

- 代谢组模块不是完整原始质谱重分析。
- 基因组模块不做正式 SNP/InDel calling。
- 当前 mini 数据包没有最终 SNP/InDel 位点，因此不能输出具体 SNP/InDel 坐标。
- 当前文献 evidence 只来自已有 `literature_evidence.tsv`，不做外部 API 检索。
- 默认 flavonoid marker aggregation 是规则版 workflow，不调用 LLM、不调用 Deep Agents，也不依赖 LangGraph。
- 并行 LangGraph workflow 是可选编排入口，当前仍不调用真实 LLM、本地开源模型或外部 API。

## 禁止事项

- 不要伪造 DOI。
- 不要伪造 SNP/InDel 位点。
- 不要把 `data/private/` 或 `outputs/` 加入 Git。
- 不要提交 BAM、FASTA、索引或大型中间文件。
- 不要随意修改 `src/breeding_agent/workflows/rnaseq_deg.py`。
- 不要随意修改 `workflows/rnaseq_deg/R/differential_expression_limma_voom.R`。
- 不要削弱 validation、provenance 或 QA 逻辑。
