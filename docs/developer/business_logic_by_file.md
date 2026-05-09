# 主要业务代码文件逻辑说明

适用读者：想系统学习代码、准备认领某个模块开发任务的同学。  
阅读目标：按文件理解业务职责、输入输出、上下游关系、限制和阅读建议。

说明：本文不逐行解释代码，只解释业务逻辑。`__init__.py` 多为包初始化文件，通常不承载业务逻辑。

## `src/breeding_agent/cli/deg.py`

### 1. 所属层级
CLI 入口层。

### 2. 业务职责
解析 RNA-seq DEG 命令行参数，把本地 BAM/GFF 等输入转成 `RnaSeqDegConfig`。

### 3. 输入
`--bam-dir`、`--gff`、`--contrast`、`--prefix`、`--trait`、`--threads`、`--outdir`。

### 4. 输出
调用 workflow 后在 `outputs/...` 写 DEG 结果、报告、manifest、provenance。

### 5. 核心实现逻辑
构建 argparse parser，解析路径和参数，调用 `run_rnaseq_deg_task()`，把成功或失败状态打印到终端。

### 6. 上游依赖
用户 CLI；本地 BAM/GFF；`workflows/rnaseq_deg.py`。

### 7. 下游去向
RNA-seq DEG workflow 和后续 transcriptomics evidence integration。

### 8. 当前限制
不负责 DEG 算法，只是入口；不要在这里改 featureCounts 或 R 逻辑。

### 9. 新同学阅读建议
先读它理解 CLI 形状，再跳到 `workflows/rnaseq_deg.py`。不要轻易改默认注释策略。

## `src/breeding_agent/cli/flavonoid_markers.py`

### 1. 所属层级
CLI 入口层。

### 2. 业务职责
运行普通规则版黄酮候选标记推荐 workflow。

### 3. 输入
`--evidence-dir`、`--outdir`、可选 `--variant-calling-dir`。

### 4. 输出
候选标记表、报告、QA JSON、manifest。

### 5. 核心实现逻辑
解析参数，构造 `FlavonoidMarkerAggregationConfig`，调用 `run_flavonoid_marker_aggregation_task()`。

### 6. 上游依赖
标准 evidence TSV；可选 candidate variant calling 输出。

### 7. 下游去向
生成的报告和候选表会被 Gradio、老师汇报和后续 LangGraph/Deep Agents 对照使用。

### 8. 当前限制
不调用 LLM；不伪造 DOI 或 SNP/InDel。

### 9. 新同学阅读建议
先读 `workflows/flavonoid_marker_aggregation.py` 和 `agents/flavonoid_central_host.py`。

## `src/breeding_agent/cli/flavonoid_markers_graph.py`

### 1. 所属层级
CLI 入口层 / LangGraph 入口。

### 2. 业务职责
运行 LangGraph 版黄酮候选标记推荐 workflow，可选启用本地 LLM Reviewer。

### 3. 输入
`--evidence-dir`、`--outdir`、`--variant-calling-dir`、`--use-llm-reviewer`、`--llm-config`。

### 4. 输出
graph trace、final state、node decision table、summary、报告、QA、manifest。

### 5. 核心实现逻辑
构造 `FlavonoidMarkerLangGraphConfig`；未安装 LangGraph 时返回清晰提示；成功时打印输出路径和 LLM reviewer metadata。

### 6. 上游依赖
LangGraph 可选依赖；本地 LLM config 可选。

### 7. 下游去向
`workflows/flavonoid_marker_langgraph.py`。

### 8. 当前限制
只有 ReviewerAgent 可以调用 LLM；LLM 不直接生成 marker 结论。

### 9. 新同学阅读建议
如果修 LLM 开关，连读 `graphs/flavonoid_marker_graph.py` 和 `llm/executor.py`。

## `src/breeding_agent/cli/flavonoid_markers_deepagents.py`

### 1. 所属层级
CLI 入口层 / Deep Agents POC 入口。

### 2. 业务职责
运行并行 Deep Agents POC。

### 3. 输入
`--evidence-dir`、`--outdir`、可选 `--variant-calling-dir`。

### 4. 输出
Deep Agents trace、summary、decision table、报告、QA、manifest。

### 5. 核心实现逻辑
解析参数，调用 `run_flavonoid_marker_deepagents_task()`；缺依赖时提示不影响其他 CLI。

### 6. 上游依赖
标准 evidence、可选 variant evidence、Deep Agents optional dependency。

### 7. 下游去向
`workflows/flavonoid_marker_deepagents.py`。

### 8. 当前限制
POC 不替代 LangGraph，不调用真实 LLM。

### 9. 新同学阅读建议
只在做 harness 规划时改它；主线开发优先 LangGraph。

## `src/breeding_agent/cli/genomics_variants.py`

### 1. 所属层级
CLI 入口层 / Genomics Candidate Variant Calling 入口。

### 2. 业务职责
运行候选区域变异 calling MVP。

### 3. 输入
`--dataset-dir`、`--outdir`。

### 4. 输出
candidate variants、SNP/InDel candidates、KASP/CAPS preliminary tables、report、manifest、run.log。

### 5. 核心实现逻辑
构造 `GenomicsVariantCallingConfig` 并调用 workflow。

### 6. 上游依赖
学长 mini 数据包、samtools/bcftools。

### 7. 下游去向
variant evidence integration 和 Gradio Genomics / GWAS 展示。

### 8. 当前限制
不能替代 WGS/GBS 群体变异检测。

### 9. 新同学阅读建议
核心命令在 modules/workflow；不要在 CLI 里重写 calling 逻辑。

## `src/breeding_agent/cli/promoter_design.py`

### 1. 所属层级
CLI 入口层 / Promoter Design scaffold 入口。

### 2. 业务职责
接收 gene sequence / function 等参数，运行启动子设计 scaffold。

### 3. 输入
gene id、gene sequence、gene function、species、target expression level、outdir。

### 4. 输出
占位候选表、设计报告、验证计划、manifest。

### 5. 核心实现逻辑
校验 sequence 长度，构造 config，调用 `run_promoter_design_task()`。

### 6. 上游依赖
用户提供的基因信息。

### 7. 下游去向
后续 promoter predictor / generator 规划文档。

### 8. 当前限制
不训练模型，不生成真实启动子序列。

### 9. 新同学阅读建议
先读 `docs/promoter_design_task.md` 和 `workflows/promoter_design.py`。

## `src/breeding_agent/workflows/rnaseq_deg.py`

### 1. 所属层级
Workflow 编排层 / 生信数据处理层。

### 2. 业务职责
编排 RNA-seq DEG reproduction，从验证输入到外部命令、R 脚本、报告、标准 evidence 和 provenance。

### 3. 输入
BAM directory、GFF、contrast、prefix、trait、threads、outdir。

### 4. 输出
counts、DEG TSV、report、standardized evidence、candidate gene table、recommendation report、manifest、provenance。

### 5. 核心实现逻辑
校验输入和工具，运行 featureCounts，运行 limma-voom R 脚本，生成报告和 integration 输出，写 provenance。

### 6. 上游依赖
CLI / Gradio，validators，command runner，R script。

### 7. 下游去向
Transcriptomics DEG Tab 和 integration outputs。

### 8. 当前限制
只在明确任务要求时修改；不要随意改 featureCounts 参数。

### 9. 新同学阅读建议
配合 `workflows/rnaseq_deg/R/differential_expression_limma_voom.R` 看。

## `src/breeding_agent/workflows/flavonoid_marker_aggregation.py`

### 1. 所属层级
Workflow 编排层 / 智能体聚合分析层。

### 2. 业务职责
运行普通黄酮候选标记推荐并写最终输出。

### 3. 输入
evidence dir、outdir、optional variant calling dir。

### 4. 输出
候选表、报告、QA、manifest。

### 5. 核心实现逻辑
调用 CentralHost 聚合 evidence 和 agents，生成报告，写 QA JSON 和 manifest。

### 6. 上游依赖
CLI / Gradio。

### 7. 下游去向
报告展示、LangGraph/Deep Agents 对照。

### 8. 当前限制
默认不调用 LLM；不得破坏旧 CLI 兼容。

### 9. 新同学阅读建议
先读 `flavonoid_central_host.py`。

## `src/breeding_agent/workflows/flavonoid_marker_langgraph.py`

### 1. 所属层级
LangGraph workflow wrapper。

### 2. 业务职责
运行 LangGraph graph，写 graph artifacts 和 manifest。

### 3. 输入
evidence dir、outdir、variant calling dir、target genes、LLM reviewer 开关和 config path。

### 4. 输出
graph trace、final state、node decision table、summary、报告、QA、manifest。

### 5. 核心实现逻辑
构造 initial state，调用 compiled graph，调用 trace report writer，校验输出路径。

### 6. 上游依赖
LangGraph CLI / Gradio。

### 7. 下游去向
Gradio LangGraph 展示和开发者 trace 分析。

### 8. 当前限制
LangGraph 是编排层；LLM 只允许 ReviewerAgent。

### 9. 新同学阅读建议
改 node 前先读 `graphs/state.py` 和 `graphs/flavonoid_marker_graph.py`。

## `src/breeding_agent/workflows/flavonoid_marker_deepagents.py`

### 1. 所属层级
Deep Agents POC workflow wrapper。

### 2. 业务职责
运行 Deep Agents POC 并写 POC artifacts。

### 3. 输入
evidence dir、outdir、variant calling dir。

### 4. 输出
deepagents trace、summary、decision table、报告、QA、manifest。

### 5. 核心实现逻辑
调用 POC harness，复用聚合、报告和 QA。

### 6. 上游依赖
Deep Agents CLI。

### 7. 下游去向
POC 汇报和未来 harness 设计。

### 8. 当前限制
不替代 LangGraph，不接真实 LLM。

### 9. 新同学阅读建议
不要把主线逻辑迁移到 Deep Agents POC。

## `src/breeding_agent/workflows/genomics_region.py`

### 1. 所属层级
Workflow 编排层 / Genomics evidence analysis。

### 2. 业务职责
生成目标基因 region、annotation summary 和 marker readiness。

### 3. 输入
dataset dir、outdir。

### 4. 输出
genomics tables、report、manifest。

### 5. 核心实现逻辑
调用 `modules/genomics/genomics_region.py`，再生成 report。

### 6. 上游依赖
Gradio Genomics / GWAS Tab。

### 7. 下游去向
Gradio 展示和 marker readiness 文档。

### 8. 当前限制
不做 variant calling；`variant_status=not_called` 不代表无变异。

### 9. 新同学阅读建议
不要把 variant calling 逻辑塞进 region workflow。

## `src/breeding_agent/workflows/genomics_variant_calling.py`

### 1. 所属层级
Workflow 编排层 / Genomics Candidate Variant Calling。

### 2. 业务职责
运行候选区域 variant calling MVP。

### 3. 输入
dataset dir、outdir。

### 4. 输出
candidate variants、SNP/InDel、KASP/CAPS preliminary tables、report、manifest、log。

### 5. 核心实现逻辑
调用 genomics variant calling module，捕获缺工具错误，写 report 和 manifest。

### 6. 上游依赖
CLI / Gradio。

### 7. 下游去向
flavonoid variant evidence integration。

### 8. 当前限制
不能替代 WGS/GBS 群体检测。

### 9. 新同学阅读建议
不要改核心 calling 命令，除非任务明确要求。

## `src/breeding_agent/workflows/metabolomics_evidence.py`

### 1. 所属层级
Workflow 编排层 / Metabolomics evidence analysis。

### 2. 业务职责
读取已有代谢组相关表并生成标准输出。

### 3. 输入
dataset dir、outdir。

### 4. 输出
candidate metabolites、network edges、sPLS coefficients、report、manifest。

### 5. 核心实现逻辑
调用 metabolomics module，汇总 warnings 和 row counts，写报告。

### 6. 上游依赖
Gradio Metabolomics Tab。

### 7. 下游去向
报告和 evidence aggregation。

### 8. 当前限制
不是完整原始代谢组统计流程。

### 9. 新同学阅读建议
先读 docs/modules/metabolomics_evidence.md。

## `src/breeding_agent/workflows/promoter_design.py`

### 1. 所属层级
Workflow 编排层 / Promoter Design scaffold。

### 2. 业务职责
把启动子设计任务规范化为可运行 scaffold。

### 3. 输入
PromoterDesignInput 或 CLI config。

### 4. 输出
占位 candidate table、报告、validation plan、manifest。

### 5. 核心实现逻辑
校验 gene_sequence，不生成 synthetic promoter，写诚实的占位输出。

### 6. 上游依赖
Promoter CLI。

### 7. 下游去向
后续 promoter dataset inventory、predictor、generator 规划。

### 8. 当前限制
不是启动子生成模型。

### 9. 新同学阅读建议
不要往这里写 GAN / diffusion / DNA LM，先补数据集和验证设计。

## `src/breeding_agent/modules/genomics/genomics_region.py`

### 1. 所属层级
生信数据处理层。

### 2. 业务职责
整理目标基因区域、注释和 marker readiness。

### 3. 输入
学长数据包中的 region / annotation / target gene 信息。

### 4. 输出
target gene regions、annotation summary、marker readiness。

### 5. 核心实现逻辑
读取小表，聚合固定目标基因信息，输出缺失 warning。

### 6. 上游依赖
Genomics region workflow。

### 7. 下游去向
Genomics report 和 Gradio。

### 8. 当前限制
不调用变异检测。

### 9. 新同学阅读建议
如果要加 region 字段，注意 report 和 Gradio 表头同步。

## `src/breeding_agent/modules/genomics/variant_calling.py`

### 1. 所属层级
生信数据处理层 / Candidate Variant Calling。

### 2. 业务职责
从候选区域运行变异 calling 并生成候选标记筛选表。

### 3. 输入
dataset dir 中的 BAM、genome FASTA/GFF 和目标区域。

### 4. 输出
candidate variants、SNP/InDel、KASP/CAPS preliminary screening、logs。

### 5. 核心实现逻辑
检查 samtools/bcftools，调用现有命令，解析真实输出并分层 PASS/LowQual。

### 6. 上游依赖
Variant calling workflow。

### 7. 下游去向
Variant evidence integration、Gradio Genomics Tab。

### 8. 当前限制
不伪造位点；KASP/CAPS 不是最终方案。

### 9. 新同学阅读建议
改动前先跑 tests/test_genomics_variant_calling.py。

## `src/breeding_agent/modules/metabolomics/metabolomics_evidence.py`

### 1. 所属层级
生信数据处理层 / Metabolomics evidence。

### 2. 业务职责
把学长数据包中已有代谢组相关表整理为输出。

### 3. 输入
metabolome raw / candidate metabolite / gene-metabolite network 等小表。

### 4. 输出
标准代谢组 evidence tables 和统计摘要。

### 5. 核心实现逻辑
检查文件，复制或写空表头，记录 row count 和 warning。

### 6. 上游依赖
Metabolomics workflow。

### 7. 下游去向
报告、Gradio、黄酮 evidence aggregation。

### 8. 当前限制
不是从 mzML 或原始峰表开始的完整分析。

### 9. 新同学阅读建议
不要把原始代谢组全流程硬塞进当前 evidence module。

## `src/breeding_agent/modules/promoter/promoter_task_schema.py`

### 1. 所属层级
Promoter Design schema 层。

### 2. 业务职责
定义启动子设计 scaffold 的输入、输出、候选和数据集记录结构。

### 3. 输入
gene id、sequence、function、species、target expression。

### 4. 输出
dataclass / TypedDict 风格结构。

### 5. 核心实现逻辑
提供 schema，不做模型训练。

### 6. 上游依赖
Promoter workflow / CLI。

### 7. 下游去向
后续 predictor / generator / dataset inventory。

### 8. 当前限制
不包含真实 promoter activity predictor。

### 9. 新同学阅读建议
先扩 schema，再谈模型。

## `src/breeding_agent/integration/evidence_schema.py`

### 1. 所属层级
Evidence 标准化层。

### 2. 业务职责
定义统一 evidence 数据结构。

### 3. 输入
不同组学 evidence 字段。

### 4. 输出
标准化 evidence record。

### 5. 核心实现逻辑
用结构化对象统一字段名和意义。

### 6. 上游依赖
Transcriptomics standardizer。

### 7. 下游去向
Candidate aggregator 和 recommendation report。

### 8. 当前限制
不承载具体分析算法。

### 9. 新同学阅读建议
改 schema 会影响多处下游，需同步 tests。

## `src/breeding_agent/integration/transcriptomics_standardizer.py`

### 1. 所属层级
Evidence 标准化层。

### 2. 业务职责
把 DEG 结果转为标准 transcriptomics evidence。

### 3. 输入
DEG significant genes TSV、trait、comparison。

### 4. 输出
standardized_evidence.tsv。

### 5. 核心实现逻辑
读取 DEG 表，映射方向、effect size、adj p-value 和 evidence score。

### 6. 上游依赖
RNA-seq DEG workflow。

### 7. 下游去向
candidate_aggregator 和 Integration & Recommendation Tab。

### 8. 当前限制
不引入独立表型因果判断。

### 9. 新同学阅读建议
注意 trait 只是用户分析目标，不是独立表型验证。

## `src/breeding_agent/integration/candidate_aggregator.py`

### 1. 所属层级
Evidence 聚合层。

### 2. 业务职责
从 standardized evidence 生成候选基因表。

### 3. 输入
standardized_evidence.tsv。

### 4. 输出
candidate_gene_table.tsv。

### 5. 核心实现逻辑
按 entity 聚合 evidence，生成候选排序表。

### 6. 上游依赖
transcriptomics_standardizer。

### 7. 下游去向
recommendation report 和 Gradio Integration Tab。

### 8. 当前限制
目前主要服务 transcriptomics demo。

### 9. 新同学阅读建议
不要把黄酮 marker 专用逻辑混到这里。

## `src/breeding_agent/integration/recommendation_report.py`

### 1. 所属层级
报告前 integration 层。

### 2. 业务职责
生成早期 transcriptomics recommendation report。

### 3. 输入
candidate gene table、trait。

### 4. 输出
recommendation_report.md。

### 5. 核心实现逻辑
把候选基因表转为 Markdown 建议，并写明 trait 边界。

### 6. 上游依赖
candidate_aggregator。

### 7. 下游去向
Integration & Recommendation Tab。

### 8. 当前限制
不是完整多组学推荐。

### 9. 新同学阅读建议
黄酮主报告看 `reports/flavonoid_marker_report.py`。

## `src/breeding_agent/integration/flavonoid_marker_package_importer.py`

### 1. 所属层级
Evidence 标准化层。

### 2. 业务职责
把学长 mini 数据包转换为 flavonoid marker evidence TSV。

### 3. 输入
dataset dir 中的 target summary、annotations、metabolome 等文件。

### 4. 输出
五类 evidence TSV。

### 5. 核心实现逻辑
读取包内小表，提取三固定基因和 seed literature DOI。

### 6. 上游依赖
脚本和 Gradio evidence 按钮。

### 7. 下游去向
flavonoid_marker_aggregator 和 agents。

### 8. 当前限制
只使用已提供或固定核验 evidence，不伪造 DOI。

### 9. 新同学阅读建议
新增 evidence 字段要同步 aggregator、report 和 QA。

## `src/breeding_agent/integration/flavonoid_marker_aggregator.py`

### 1. 所属层级
Evidence 聚合层。

### 2. 业务职责
聚合 transcriptomics、metabolomics、annotation、literature、variant evidence 为候选标记表。

### 3. 输入
五类 evidence TSV 和可选 variant calling dir。

### 4. 输出
`flavonoid_marker_candidates.tsv`、candidate rows、warnings。

### 5. 核心实现逻辑
按固定基因合并统计值、代谢物、注释、DOI、variant 状态和 marker recommendation 字段。

### 6. 上游依赖
workflow / CentralHost。

### 7. 下游去向
agents、reports、QA、Gradio。

### 8. 当前限制
LowQual 不得优先；没有 calling 时保持 not_called。

### 9. 新同学阅读建议
这是黄酮主业务核心，改动需跑 QA 和报告测试。

## `src/breeding_agent/integration/flavonoid_variant_evidence.py`

### 1. 所属层级
Variant evidence integration 层。

### 2. 业务职责
读取 candidate variant calling 输出并按目标基因汇总。

### 3. 输入
`candidate_variants.tsv`、`kasp_candidate_sites.tsv`、`caps_candidate_sites.tsv`。

### 4. 输出
gene-level variant evidence rows。

### 5. 核心实现逻辑
统计 PASS/LowQual、SNP/InDel、KASP preliminary、CAPS screening。

### 6. 上游依赖
Genomics Candidate Variant Calling MVP。

### 7. 下游去向
flavonoid marker aggregator 和 report。

### 8. 当前限制
不展开或伪造原始位点。

### 9. 新同学阅读建议
Si9g04210.1 若当前 no_called_variant，不要显示成已有 called variant。

## `src/breeding_agent/integration/flavonoid_marker_qa.py`

### 1. 所属层级
QA 规则层。

### 2. 业务职责
检查黄酮报告是否满足学长硬性要求。

### 3. 输入
最终报告文本。

### 4. 输出
QA dict 和 `passed`。

### 5. 核心实现逻辑
检查三个固定基因、`群体`、文献查阅、DOI、统计值、SNP/InDel/KASP/CAPS。

### 6. 上游依赖
report / FinalQAAgent。

### 7. 下游去向
`qa_check.json`、manifest、Gradio。

### 8. 当前限制
规则 QA 不代表实验验证完成。

### 9. 新同学阅读建议
不要弱化 QA，除非业务要求明确改变。

## `src/breeding_agent/agents/base.py`

### 1. 所属层级
Agent interface 层。

### 2. 业务职责
定义 LLM-ready Agent 输入、输出、结果和规则 fallback 基类。

### 3. 输入
agent context、prompt template、parameters。

### 4. 输出
`AgentInput`、`AgentOutput`、`AgentResult`。

### 5. 核心实现逻辑
用 dataclass 统一 agent 合约，不引入外部 LLM SDK。

### 6. 上游依赖
所有 agents。

### 7. 下游去向
LangGraph、Deep Agents POC、未来 LLM adapter。

### 8. 当前限制
接口本身不调用模型。

### 9. 新同学阅读建议
新增 Agent 先遵守这里的输出结构。

## `src/breeding_agent/agents/context_builder.py`

### 1. 所属层级
Agent context 层。

### 2. 业务职责
把多类 evidence 汇总为统一 agent context。

### 3. 输入
evidence dir、candidate rows、variant calling dir、warnings。

### 4. 输出
结构化 dict。

### 5. 核心实现逻辑
读取小型 TSV，按基因组织 evidence，不读取大文件。

### 6. 上游依赖
CentralHost、LangGraph、Deep Agents。

### 7. 下游去向
所有 flavonoid agents 和 LLM reviewer。

### 8. 当前限制
不做 LLM 调用。

### 9. 新同学阅读建议
新增 context 字段时注意 trace 和 tests。

## `src/breeding_agent/agents/flavonoid_central_host.py`

### 1. 所属层级
Agent 编排层。

### 2. 业务职责
普通 workflow 中顺序调度所有 flavonoid agents。

### 3. 输入
evidence dir、outdir、variant calling dir。

### 4. 输出
agent outputs、最终报告、QA。

### 5. 核心实现逻辑
聚合候选表，构建 context，运行 literature / marker / validation / reviewer / final QA。

### 6. 上游依赖
普通 workflow。

### 7. 下游去向
报告和 manifest。

### 8. 当前限制
不使用 LangGraph，也不调用 LLM。

### 9. 新同学阅读建议
普通 workflow 的 agent 顺序从这里看。

## `src/breeding_agent/agents/flavonoid_literature_agent.py`

### 1. 所属层级
Agent 业务层。

### 2. 业务职责
生成文献查阅文本，保留 DOI。

### 3. 输入
literature evidence rows。

### 4. 输出
literature review text 和 `AgentOutput`。

### 5. 核心实现逻辑
读取已有 DOI evidence，组织成报告小节。

### 6. 上游依赖
context_builder / evidence TSV。

### 7. 下游去向
report、ReviewerAgent、FinalQAAgent。

### 8. 当前限制
不查外部文献，不补造 DOI。

### 9. 新同学阅读建议
若接 LLM，只能摘要已有 DOI，不可生成新 DOI。

## `src/breeding_agent/agents/flavonoid_marker_recommendation_agent.py`

### 1. 所属层级
Agent 业务层。

### 2. 业务职责
生成 SNP/InDel/KASP/CAPS 推荐文本。

### 3. 输入
candidate rows 和 variant evidence status。

### 4. 输出
marker recommendation text。

### 5. 核心实现逻辑
按 PASS/LowQual/not_called 等状态生成分层建议。

### 6. 上游依赖
flavonoid_marker_aggregator。

### 7. 下游去向
report、ReviewerAgent。

### 8. 当前限制
不伪造位点；preliminary 不等于最终 marker。

### 9. 新同学阅读建议
这是高风险 Agent，LLM 化要最后考虑。

## `src/breeding_agent/agents/flavonoid_validation_agent.py`

### 1. 所属层级
Agent 业务层。

### 2. 业务职责
生成后续验证方案。

### 3. 输入
candidate context、marker recommendation。

### 4. 输出
validation plan text。

### 5. 核心实现逻辑
组织 Sanger、candidate-region calling、KASP/CAPS、群体验证、qRT-PCR、LC-MS/MS。

### 6. 上游依赖
context_builder。

### 7. 下游去向
report、ReviewerAgent。

### 8. 当前限制
不能写成验证已完成。

### 9. 新同学阅读建议
这是下一步可考虑 LLM 增强的 Agent。

## `src/breeding_agent/agents/flavonoid_reviewer_agent.py`

### 1. 所属层级
Agent 业务层 / LLM 审阅增强入口。

### 2. 业务职责
检查报告草稿的过度推断和证据边界。

### 3. 输入
candidate rows、literature text、marker text、validation plan、report text、可选 LLM review。

### 4. 输出
reviewer notes、warnings、LLM metadata。

### 5. 核心实现逻辑
先运行规则检查；LangGraph 可选调用本地 LLM；通过 guard 后合并审阅增强。

### 6. 上游依赖
LangGraph reviewer node 或普通 CentralHost。

### 7. 下游去向
FinalQAAgent、final report、graph trace。

### 8. 当前限制
LLM 只审阅，不生成新 marker 结论。

### 9. 新同学阅读建议
LLM 相关问题同时读 `llm/executor.py` 和 `llm/output_guard.py`。

## `src/breeding_agent/agents/flavonoid_final_qa_agent.py`

### 1. 所属层级
Agent QA 层。

### 2. 业务职责
包装 canonical QA。

### 3. 输入
最终报告文本。

### 4. 输出
QA `AgentOutput`。

### 5. 核心实现逻辑
调用 `check_flavonoid_marker_report()`。

### 6. 上游依赖
report text。

### 7. 下游去向
qa_check.json。

### 8. 当前限制
建议保持规则化，不用 LLM 替代。

### 9. 新同学阅读建议
不要绕过 FinalQAAgent。

## `src/breeding_agent/agents/prompt_templates.py`

### 1. 所属层级
LLM-ready prompt 层。

### 2. 业务职责
集中保存未来 LLM 可用的 prompt 模板。

### 3. 输入
agent context。

### 4. 输出
prompt template string。

### 5. 核心实现逻辑
把不伪造 DOI/SNP/InDel、LowQual、preliminary、WGS/GBS 限制写进模板。

### 6. 上游依赖
Agent classes。

### 7. 下游去向
未来 adapter 和当前文档说明。

### 8. 当前限制
模板不是模型调用。

### 9. 新同学阅读建议
新增 LLM 能力先补 prompt 和 guard。

## `src/breeding_agent/graphs/state.py`

### 1. 所属层级
LangGraph state schema 层。

### 2. 业务职责
定义 LangGraph state 的可 JSON 序列化字段。

### 3. 输入
workflow 初始参数和节点输出。

### 4. 输出
`FlavonoidGraphState`。

### 5. 核心实现逻辑
使用 TypedDict 描述 state 字段。

### 6. 上游依赖
LangGraph workflow。

### 7. 下游去向
graph nodes 和 final state JSON。

### 8. 当前限制
新增 state 字段要注意 LangGraph 是否保留。

### 9. 新同学阅读建议
LLM config 当前通过 agent_context 传递，避免未声明字段丢失。

## `src/breeding_agent/graphs/flavonoid_marker_graph.py`

### 1. 所属层级
LangGraph 编排层。

### 2. 业务职责
定义 LangGraph nodes 和边。

### 3. 输入
initial graph state。

### 4. 输出
final graph state、graph trace。

### 5. 核心实现逻辑
按节点顺序加载 evidence、聚合候选、构建 context、运行 agents、写报告和 QA。

### 6. 上游依赖
LangGraph workflow wrapper。

### 7. 下游去向
trace reports、Gradio、manifest。

### 8. 当前限制
只有 reviewer node 可选调用 LLM。

### 9. 新同学阅读建议
新增 node 必须写 trace 和 tests。

## `src/breeding_agent/deepagents/flavonoid_deepagents_poc.py`

### 1. 所属层级
Deep Agents POC 层。

### 2. 业务职责
生成 deterministic Deep Agents POC trace 和 summary。

### 3. 输入
evidence、context、variant calling dir。

### 4. 输出
deepagents trace、summary、decision table。

### 5. 核心实现逻辑
optional import deepagents，复用规则 agents，记录每一步。

### 6. 上游依赖
Deep Agents workflow wrapper。

### 7. 下游去向
POC 输出和文档汇报。

### 8. 当前限制
不替代 LangGraph，不调用 LLM。

### 9. 新同学阅读建议
不要把 POC 当成生产主线。

## `src/breeding_agent/llm/adapter_base.py`

### 1. 所属层级
LLM 接口层。

### 2. 业务职责
定义 LLM config、request、response 结构。

### 3. 输入
模型参数、messages、chat template kwargs。

### 4. 输出
dataclass。

### 5. 核心实现逻辑
提供不依赖 SDK 的最小抽象。

### 6. 上游依赖
executor。

### 7. 下游去向
OpenAI-compatible adapter。

### 8. 当前限制
只定义结构，不发请求。

### 9. 新同学阅读建议
新增 provider 时先扩这里。

## `src/breeding_agent/llm/openai_compatible_adapter.py`

### 1. 所属层级
LLM adapter 层。

### 2. 业务职责
调用本地 OpenAI-compatible chat completions。

### 3. 输入
LLMConfig、LLMRequest。

### 4. 输出
LLMResponse。

### 5. 核心实现逻辑
用标准库 HTTP POST 请求 `/chat/completions`，传递 `chat_template_kwargs.enable_thinking=false`。

### 6. 上游依赖
executor。

### 7. 下游去向
output_guard。

### 8. 当前限制
不引入 OpenAI SDK；不保证服务一定可用。

### 9. 新同学阅读建议
切换 LM Studio/Ollama/vLLM/SGLang 时优先改本地 config。

## `src/breeding_agent/llm/executor.py`

### 1. 所属层级
LLM 执行层。

### 2. 业务职责
读取本地 config，构造 ReviewerAgent LLM 请求，处理 fallback。

### 3. 输入
agent context、config path、rule reviewer notes、enabled flag。

### 4. 输出
`LLMReviewerResult` metadata 和可选 content。

### 5. 核心实现逻辑
解析轻量 YAML，检查 enabled/provider/agent，调用 adapter，执行 output_guard。

### 6. 上游依赖
LangGraph reviewer node。

### 7. 下游去向
ReviewerAgent merge 和 graph trace。

### 8. 当前限制
只服务 ReviewerAgent；失败必须 fallback。

### 9. 新同学阅读建议
不要在 executor 中加入 marker 结论生成。

## `src/breeding_agent/llm/output_guard.py`

### 1. 所属层级
LLM 安全层。

### 2. 业务职责
拦截不合规 LLM reviewer 文本。

### 3. 输入
LLM content 和 context。

### 4. 输出
GuardResult。

### 5. 核心实现逻辑
正则检查 DOI、坐标、LowQual、preliminary KASP/CAPS、WGS/GBS 限制。

### 6. 上游依赖
executor。

### 7. 下游去向
fallback 或 reviewer merge。

### 8. 当前限制
guard 是最低安全线，不代表人工审阅。

### 9. 新同学阅读建议
新增 LLM Agent 必须新增对应 guard。

## `src/breeding_agent/reports/deg_result_parser.py`

### 1. 所属层级
报告辅助层。

### 2. 业务职责
解析 DEG 结果，给报告生成器提供结构化摘要。

### 3. 输入
DEG TSV。

### 4. 输出
显著基因摘要和统计信息。

### 5. 核心实现逻辑
读取表格、统计行数和关键字段，供 DEG report 使用。

### 6. 上游依赖
RNA-seq DEG workflow。

### 7. 下游去向
`deg_report.py`。

### 8. 当前限制
只解析已有结果，不做差异分析。

### 9. 新同学阅读建议
改 DEG report 时先看它。

## `src/breeding_agent/reports/deg_report.py`

### 1. 所属层级
报告生成层。

### 2. 业务职责
生成 RNA-seq DEG Markdown 报告。

### 3. 输入
DEG 结果、运行参数、工具和输出路径。

### 4. 输出
`reports/report.md`。

### 5. 核心实现逻辑
汇总 counts、DEG 结果和运行信息，说明分析边界。

### 6. 上游依赖
RNA-seq workflow。

### 7. 下游去向
Gradio Transcriptomics Tab 和 integration。

### 8. 当前限制
报告不代表独立表型验证。

### 9. 新同学阅读建议
不要把黄酮 marker 业务写进 DEG report。

## `src/breeding_agent/reports/metabolomics_report.py`

### 1. 所属层级
报告生成层。

### 2. 业务职责
生成代谢组 evidence analysis 报告。

### 3. 输入
代谢组表格 row count、warnings、输出路径。

### 4. 输出
`metabolomics_report.md`。

### 5. 核心实现逻辑
说明读取了哪些已有代谢组结果表和当前限制。

### 6. 上游依赖
metabolomics workflow。

### 7. 下游去向
Gradio Metabolomics Tab。

### 8. 当前限制
不是完整原始质谱流程报告。

### 9. 新同学阅读建议
新增代谢组表时同步 report 和 Gradio。

## `src/breeding_agent/reports/genomics_report.py`

### 1. 所属层级
报告生成层。

### 2. 业务职责
生成基因组 region / annotation 报告。

### 3. 输入
target regions、annotation summary、marker readiness。

### 4. 输出
`genomics_report.md`。

### 5. 核心实现逻辑
展示目标基因区域、注释和 `variant_status=not_called` 边界。

### 6. 上游依赖
genomics region workflow。

### 7. 下游去向
Gradio Genomics / GWAS Tab。

### 8. 当前限制
不声称完成 variant calling。

### 9. 新同学阅读建议
不要把 candidate variant calling 报告混进 region report。

## `src/breeding_agent/reports/genomics_variant_report.py`

### 1. 所属层级
报告生成层。

### 2. 业务职责
生成 Candidate Variant Calling MVP 报告。

### 3. 输入
variant calling manifest、candidate/SNP/InDel/KASP/CAPS 表统计。

### 4. 输出
`genomics_variant_calling_report.md`。

### 5. 核心实现逻辑
汇总 PASS/LowQual、SNP/InDel、KASP/CAPS preliminary screening，并写明限制。

### 6. 上游依赖
genomics variant calling workflow。

### 7. 下游去向
Gradio 和 flavonoid variant evidence integration。

### 8. 当前限制
不能替代 WGS/GBS 群体变异检测。

### 9. 新同学阅读建议
不要把 preliminary screening 写成最终标记方案。

## `src/breeding_agent/reports/flavonoid_marker_report.py`

### 1. 所属层级
报告生成层 / 黄酮主业务报告。

### 2. 业务职责
生成谷子黄酮候选标记推荐报告。

### 3. 输入
candidate rows、literature rows、agent 文本、variant calling dir、QA。

### 4. 输出
`flavonoid_marker_report.md`。

### 5. 核心实现逻辑
展示三个固定基因、统计学数值、文献 DOI、marker 推荐、variant evidence、验证计划和限制。

### 6. 上游依赖
普通 workflow、LangGraph、Deep Agents POC。

### 7. 下游去向
QA、Gradio、老师汇报。

### 8. 当前限制
不得声称最终 KASP/CAPS 或实验验证完成。

### 9. 新同学阅读建议
任何改动都要同步 `flavonoid_marker_qa.py` 和报告测试。

## `src/breeding_agent/reports/langgraph_trace_report.py`

### 1. 所属层级
LangGraph trace 报告层。

### 2. 业务职责
写出 graph trace、final state、node decision table 和 summary。

### 3. 输入
LangGraph final state。

### 4. 输出
`graph_trace.json`、`graph_state_final.json`、`node_decision_table.tsv`、`langgraph_summary.md`。

### 5. 核心实现逻辑
把每个 node 的输入摘要、输出摘要、证据、warning、limitation 和 passed 状态写成可审计记录。

### 6. 上游依赖
LangGraph workflow。

### 7. 下游去向
Gradio LangGraph 展示、调试和汇报。

### 8. 当前限制
只记录 trace，不改变业务结果。

### 9. 新同学阅读建议
新增 node metadata 时注意 decision table 字段稳定性。

## `src/breeding_agent/web/gradio_app.py`

### 1. 所属层级
Gradio 展示层。

### 2. 业务职责
提供本地 Web 工作台，触发 workflow 并展示已有输出。

### 3. 输入
本地路径、按钮、checkbox、textbox。

### 4. 输出
页面状态、表格、Markdown、JSON、日志。

### 5. 核心实现逻辑
每个 Tab 调用已有 workflow 或读取已有 output；LangGraph 小节可选传递 LLM reviewer 开关。

### 6. 上游依赖
用户浏览器。

### 7. 下游去向
workflows 和 output 文件。

### 8. 当前限制
不承载业务核心逻辑，不读取 LLM config 内容。

### 9. 新同学阅读建议
先实现 CLI/workflow/tests，再接 Gradio。

## `workflows/rnaseq_deg/R/differential_expression_limma_voom.R`

### 1. 所属层级
R 生信分析层。

### 2. 业务职责
运行 limma-voom 差异表达分析。

### 3. 输入
featureCounts count matrix、样本分组、contrast。

### 4. 输出
DEG TSV。

### 5. 核心实现逻辑
读取 counts，构建设计矩阵，运行 voom/limma，输出显著基因表。

### 6. 上游依赖
RNA-seq workflow 的 featureCounts 输出。

### 7. 下游去向
DEG report 和 transcriptomics standardizer。

### 8. 当前限制
除非任务明确要求，不修改 R workflow。

### 9. 新同学阅读建议
R 逻辑稳定，优先不要动。

## tests 主要文件

### 1. 所属层级
测试验证层。

### 2. 业务职责
保护当前核心能力不被回归破坏。

### 3. 输入
临时目录、mock TSV、已有 evidence、小型示例。

### 4. 输出
unittest 结果。

### 5. 核心实现逻辑
覆盖 agent interface、flavonoid agent layer、variant evidence、genomics variant calling、LangGraph、Deep Agents、LLM reviewer、omics modules、Promoter scaffold。

### 6. 上游依赖
开发改动。

### 7. 下游去向
提交前验证。

### 8. 当前限制
测试通过不代表实验验证完成。

### 9. 新同学阅读建议
改哪个模块先读对应 test；新增功能必须补测试。
