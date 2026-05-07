# 四个 GitHub 项目对 Agri Multi-omics Breeding Agent Demo 的启发

## 1. 当前项目目标

当前项目不只是一个单一的 RNA-seq DEG 页面，而是要逐步形成一个面向杂粮育种场景的多组学智能体 Demo。

第一阶段已经把 Transcriptomics DEG Module 跑通：用户可以在 Gradio 页面中输入 BAM 目录、GFF 注释、目标性状等信息，系统自动完成 DEG 分析，并生成 `report.md`、`manifest.json`、`run.log`、`standardized_evidence.tsv` 和 `recommendation_report.md`。

后续目标是把 transcriptomics、metabolomics、genomics/GWAS 和 integration recommendation 逐步接入同一个 Demo。也就是说，页面上看到的不只是一个分析工具，而是一个可以接受数据、理解分析目标、调用确定性分析流程、沉淀证据表并输出候选解释的 Agri Multi-omics Breeding Agent。

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

对应到我们的 Demo，当前已经跑通的 Transcriptomics DEG Module 可以看作第一个 skill：

- 输入：BAM、GFF、contrast、trait、outdir。
- 执行：featureCounts + limma-voom R workflow。
- 输出：significant genes、report、manifest、run log、standardized evidence、recommendation report。

后续可以继续扩展：

- Metabolomics Module：读取代谢物表，输出差异代谢物和代谢证据。
- Genomics / GWAS Module：读取 genotype/VCF 和 phenotype，输出候选位点或候选区域。
- Integration Module：把不同组学证据统一成 `standardized_evidence.tsv`，再生成 `recommendation_report.md`。

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
3. 展示 Metabolomics Module 和 Genomics / GWAS Module 当前仍为占位，说明它们是后续 skill/module 扩展入口。
4. 展示 `standardized_evidence.tsv`，说明 DEG 结果已经被转成标准证据表，后续可以接入代谢组、基因组和表型证据。
5. 展示 `recommendation_report.md`，说明当前系统已经可以基于 transcriptomics evidence 生成第一版候选解释。
6. 展示 `report.md`、`manifest.json` 和 `run.log`，说明结果不仅能展示，也能追溯和复现。

今晚需要强调的结论：

- 当前版本仅基于 transcriptomics evidence。
- Metabolomics 和 Genomics/GWAS 仍是占位模块。
- `recommendation_report.md` 不是最终育种方案，只是候选证据解释。
- 这个 Demo 的价值在于打通了从数据输入、确定性工具调用、证据标准化到推荐报告生成的最小闭环。

