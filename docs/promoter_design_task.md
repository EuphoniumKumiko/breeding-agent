# Promoter Design Task

## 任务背景：从候选基因到启动子设计

Promoter Design Module 面向老师和学长提出的新设计型任务：输入基因序列和基因功能，输出候选启动子序列及使用方法。它承接当前 breeding-agent 的多组学育种主线，把黄酮候选基因、功能注释、表达目标和后续验证计划组织成可复现任务。

当前阶段只做任务定义、数据盘点和 workflow 脚手架。它不是 TargetGAN、diffusion model、DNA language model 或任何已经训练完成的启动子生成模型。

## 输入定义

最小输入：

| 字段 | 含义 |
| --- | --- |
| `gene_id` | 目标基因 ID，例如 `Si9g04210.1` |
| `gene_sequence` | 目标基因序列或候选基因相关序列 |
| `gene_function` | 基因功能描述，例如 flavonoid-related candidate gene |
| `species` | 物种，例如 foxtail_millet |
| `target_expression_level` | 目标表达强度，例如 high / medium / low |
| `target_tissue_or_condition` | 目标组织、时期或条件，可为空但建议填写 |

后续可扩展输入：

- 目标表达窗口
- 可用载体或转化体系
- 组织特异性表达需求
- stress / light / metabolite response 需求
- 禁止 motif、限制性酶切位点或合成约束

## 输出定义

规划输出：

| 文件 | 说明 |
| --- | --- |
| `promoter_candidates.fasta` | 候选启动子序列。当前 scaffold 不生成真实候选序列，只写空占位说明。 |
| `promoter_candidate_table.tsv` | 候选启动子表。当前只写 `not_generated_scaffold` 记录，不提供可实验使用序列。 |
| `promoter_design_report.md` | 任务说明、输入摘要、当前限制和后续路线。 |
| `promoter_validation_plan.md` | 实验验证计划，包括 reporter assay、转基因验证和表达检测。 |
| `manifest.json` | workflow 状态、输入、输出和 warning。 |

## 当前限制

- 当前 workflow 是 promoter design task scaffold，不是训练完成的 promoter generator。
- 当前不能直接输出未经验证的可用启动子。
- 当前不训练模型，不调用真实大模型，不调用外部 API。
- 当前不实现 GAN、diffusion 或 DNA language model。
- 当前不伪造 promoter sequence，不伪造文献 DOI。
- 启动子设计需要高可信 promoter activity 数据集和实验验证。
- 生信数据可作为弱标签或辅助数据，不能替代实验活性标签。

## 与现有任务的关系

- Flavonoid Marker Recommendation 负责从多组学 evidence 推荐候选 SNP/InDel/KASP/CAPS 标记。
- LangGraph workflow 负责把现有规则化 agents 编排为可追踪 graph。
- Deep Agents POC 负责验证未来更高层 agent harness 的接入方式。
- Promoter Design Module 是后续设计型任务扩展，用于从候选基因、功能和表达目标出发，准备启动子数据和生成模型边界。

当前 promoter scaffold 不改变黄酮标记推荐主线，也不替代现有 LangGraph / Deep Agents 入口。未来可把 promoter design 作为新的 graph node 或独立设计 workflow 接入。

## 后续路线

1. Dataset inventory：整理高可信实验验证启动子数据和生信辅助数据。
2. Promoter activity predictor：训练或评估启动子活性预测模型。
3. Motif annotation：标注核心 promoter motif、组织特异或诱导响应 motif。
4. Sequence optimization：在约束下优化候选序列。
5. Synthetic promoter generation：在高可信数据和模型评估成熟后生成候选启动子。
6. Experimental validation：通过 STARR-seq、MPRA、LUC reporter assay、稳定转基因和表达检测验证候选序列。
