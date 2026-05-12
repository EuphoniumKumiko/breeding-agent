# 当前项目边界说明

这份文档适合在组会前最后确认一次，避免把项目能力讲过头。

## 1. 可以讲的

- 谷子黄酮候选标记推荐
- 多组学 evidence 整合
- LiteratureAgent v3 query_plan 生成和文献回流
- 文献相关性分层
- 候选 SNP/InDel/KASP/CAPS 建议
- 后续验证方案
- QA 和 report 边界检查

## 2. 不能讲的

- 不能说 KASP/CAPS 标记开发已经完成
- 不能说 WGS/GBS 群体验证已经完成
- 不能说湿实验验证已经完成
- 不能把 demo DOI 当真实 PubMed evidence
- 不能把 LLM reviewer 说成新的证据来源
- 不能编造 DOI、位点坐标或 promoter 序列

## 3. RNA-seq DEG 模块和黄酮推荐模块的区别

这两个模块是相关但不同的：

- RNA-seq DEG 模块：可以从 BAM / GFF 直接跑 featureCounts + limma-voom，产出差异表达结果。
- 黄酮候选标记推荐模块：主要读取已经生成好的 evidence package，再做整合推荐和边界检查。

所以组会里要明确：

- DEG 是“表达层面的统计分析”
- 黄酮推荐是“基于多组学证据的候选标记建议”

## 4. 为什么页面里会看到原始文件名

页面保留 `bam/`、`metabolome_raw_3372.tsv`、`genome.fa`、`genome.gff` 等名字，不代表它们是未处理输出。

它们只是输入溯源标记，帮助大家回答三个问题：

- 证据从哪里来
- 后续怎么复核
- 如果结果有疑问，应该回到哪个原始输入

## 5. 老师常见问题 Q&A

### Q1：这是不是一个真正的 AI 发现新标记系统？

A：不是。它主要是规则化、可复现的 evidence 整合和推荐系统，LLM 只用于受限的 reviewer note 辅助，而且不能凭空造 DOI，也不能改变证据边界。

### Q2：为什么文献里有 `DEMO_ONLY`？

A：那是 demo fixture 的显式标记。它保留流程可视化，但不计入真实 evidence。

### Q3：为什么还要做 larger population 验证？

A：因为当前结果仍然是候选级别。真正的群体关联和稳定性验证必须在更大群体上完成。

### Q4：为什么要区分 high / medium / background？

A：为了避免把所有检索结果都写成直接支持。分层后更容易看出哪些文献更贴近目标基因，哪些只是背景。

### Q5：这个项目的最终输出是什么？

A：当前阶段的最终输出是报告、QA、query plan 和候选推荐，不是最终育种结论。
