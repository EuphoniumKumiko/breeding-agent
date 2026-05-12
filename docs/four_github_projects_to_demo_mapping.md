# 四个 GitHub 项目对 Agri Multi-omics Breeding Agent Demo 的启发

> Deprecated: 这份外部项目映射已被 `README.md`、`docs/project_onboarding.md` 和 `docs/architecture_overview.md` 的当前主线说明覆盖。它更适合作为阶段性背景材料，而不是新人首读文档。

适用读者：需要向老师解释项目定位、外部项目启发和当前实现边界的同学。  
阅读目标：把外部项目启发映射到当前 breeding-agent 的真实能力，不夸大未完成部分。

## 1. 当前项目目标

当前项目不只是一个单一的 RNA-seq DEG 页面，而是要逐步形成一个面向杂粮育种场景的多组学智能体 Demo。

第一阶段已经把 Transcriptomics DEG Module 跑通；当前又完成了 Metabolomics evidence、Genomics / GWAS region 展示、Genomics Candidate Variant Calling MVP、flavonoid marker recommendation、LangGraph workflow、Deep Agents POC 和 Promoter Design scaffold。页面上看到的不只是一个分析工具，而是一个可以接受本地数据路径、调用确定性分析流程、沉淀证据表并输出候选解释的 Agri Multi-omics Breeding Agent。

## 2. AutoBA 对本项目的启发

AutoBA 对本项目最直接的启发是 `data_list + goal_description` 的任务输入方式。

它强调用户不是只点击一个固定按钮，而是提供两类核心信息：

- `data_list`：用户有哪些数据，数据路径在哪里。
- `goal_description`：用户想解决什么分析目标。

这对我们的 Demo 很重要。当前 Gradio 页面已经有 `trait_selection`、`optional_file`、BAM directory、GFF annotation 等输入，这些可以继续扩展成更明确的配置驱动任务：

- `trait`：本次分析关注的育种性状，例如高产、抗旱、耐盐碱、抗病。
- `optional_file`：后续可接入表型表、样本信息、候选基因列表或文献证据。
- `analysis_goal`：用户用自然语言描述本次想回答的问题，例如“找出 LM 中高表达且可能与高产相关的候选基因”。

因此，AutoBA 给我们的落地启发是：Demo 不应只暴露底层参数，而应逐步形成“用户输入数据路径 + 分析目标 + 系统自动组织任务”的工作流。

## 3. OmicsAgent 对本项目的启发

OmicsAgent 对本项目的启发是多组学 skills 架构。

它不是把所有能力写成一个大脚本，而是把不同组学任务拆成相对独立的 skill 或 module。每个 module 负责一种清晰的分析能力，最后由上层系统组合调用。

对应到我们的 Demo，当前已经跑通的模块都可以看作独立 skill / module：

- 输入：BAM、GFF、contrast、trait、outdir。
- 执行：featureCounts + limma-voom R workflow。
- 输出：significant genes、report、manifest、run log、standardized evidence、recommendation report。

- Metabolomics Module：读取已有代谢物表，输出代谢证据。
- Genomics / GWAS Module：读取 genome/GFF/regions/annotation，展示候选区域和 annotation evidence。
- Genomics Candidate Variant Calling MVP：输出真实候选区域 SNP/InDel、PASS/LowQual 和 KASP/CAPS preliminary screening。
- Flavonoid Marker Recommendation：把 transcriptomics、metabolomics、annotation、literature 和 variant evidence 聚合为候选标记推荐。
- LangGraph workflow：把规则化 agents 节点化，作为当前主线开源智能体编排框架。
- Deep Agents POC：并行 harness 验证入口，不替代 LangGraph。
- Promoter Design scaffold：任务定义和占位输出，不生成真实启动子序列。

因此，OmicsAgent 给我们的落地启发是：当前 Demo 的每个 Tab 不只是页面占位，而是未来可逐步升级成独立 skill/module 的入口。

## 4. Lobster AI / Omics-OS 对本项目的启发

Lobster AI / Omics-OS 对本项目的启发主要有三点：supervisor + specialist agents、确定性科学工具调用、provenance / reproducibility。

第一，supervisor + specialist agents 说明多组学智能体不应让一个模型包办所有事情。更合理的方式是：上层 supervisor 理解用户目标、组织任务，下层 specialist agents 或 modules 分别负责 transcriptomics、metabolomics、genomics 和 integration。

第二，科学分析流程应尽量调用确定性工具，而不是让 LLM 临时生成脚本。对我们当前 Demo 来说，这一点非常关键：featureCounts 参数和 Rscript 参数应该由 workflow 固定管理，LLM 不应随意改动。这样才能保证结果稳定、可复现、可解释。

第三，provenance / reproducibility 对科研 Demo 很重要。我们现在已经在 workflow 中生成：

- `manifest.json`：记录任务配置、输入路径、输出路径、命令和运行状态。
- `run.log`：记录运行过程和工具输出。
- `standardized_evidence.tsv`：把 DEG 结果转成标准证据表，方便后续多组学整合。

因此，Lobster AI / Omics-OS 给我们的落地启发是：Demo 不应只展示一个漂亮结果，而要展示“结果从哪里来、用什么命令生成、可以如何复现、如何进入下一步整合”。

## 5. GPTomics bioSkills 对本项目的启发

GPTomics bioSkills 对本项目的启发是 `SKILL.md` 形式的实验流程沉淀。

它的价值不是简单写一份说明书，而是把 coding agent 执行任务时应该遵守的操作规范写清楚。例如：

- 输入文件应该如何命名。
- 哪些参数可以改，哪些参数不能改。
- 每一步应该生成什么输出。
- 遇到错误时应该如何检查。
- 哪些报告和日志必须保留。

这对我们后续建设实验室自己的 AgriMind bioSkills 很有意义。杨亿学长已经提供了可复现的 RNA-seq DEG 流程，后续可以把这些流程沉淀成实验室内部的 skill：

- `agri-transcriptomics-deg`
- `agri-metabolomics-analysis`
- `agri-gwas-analysis`
- `agri-evidence-integration`

这些 bioSkills 可以明确告诉 Codex / coding agent：不要随意改 `featureCounts` 参数，不要随意改 `Rscript` 参数，不要绕过既定 workflow，不要只生成临时脚本而不保留 provenance。

因此，GPTomics bioSkills 给我们的落地启发是：把“人知道怎么跑”的流程，变成“agent 也必须按规范跑”的实验室知识资产。

## 6. 对今晚 Demo 的直接落地

今晚 Demo 需要展示的重点不是底层生信原理，而是“这个多组学育种智能体已经有了可运行雏形”。

建议展示顺序：

1. 打开 Multi-omics Gradio 页面，说明它不是单一 RNA-seq 页面，而是面向多组学育种智能体的 Demo。
2. 展示 Transcriptomics DEG Module 可运行，输入 BAM directory、GFF annotation、trait 后运行分析。
3. 展示 Metabolomics Module 和 Genomics / GWAS Module，说明它们已经能读取学长 mini 数据包的已有结果表和区域注释。
4. 展示 Candidate Variant Calling MVP 的 PASS/LowQual、SNP/InDel、KASP/CAPS preliminary screening 输出。
5. 展示谷子黄酮候选标记推荐报告，说明系统已经满足三个固定基因、统计学数值、文献 DOI、`群体` 和 SNP/InDel/KASP/CAPS 推荐要求。
6. 展示 LangGraph workflow 的 `langgraph_summary.md`、`node_decision_table.tsv` 和 `graph_trace.json`。
7. 简要说明 Deep Agents POC 和 Promoter Design scaffold 都已存在；本地 LLM 目前只增强 LangGraph ReviewerAgent，不训练启动子模型。

今晚需要强调的结论：

- 当前版本已经跨 transcriptomics、metabolomics、annotation、literature 和 candidate variant evidence。
- LangGraph 是主线编排框架，Deep Agents 是并行 POC。
- 当前本地 LLM 只做 ReviewerAgent 审阅增强，不直接生成 SNP/InDel/KASP/CAPS 结论；更多 Agent 的模型接入是后续规划。
- Promoter Design 当前只是 scaffold，不是启动子生成模型。
- `flavonoid_marker_report.md` 不是最终育种方案；KASP/CAPS 不是最终实验方案，candidate-region variant calling 不能替代 WGS/GBS 群体检测。
- 这个 Demo 的价值在于打通了从数据输入、确定性工具调用、证据标准化到推荐报告生成的最小闭环。
