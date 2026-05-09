# Promoter Dataset Inventory

适用读者：准备收集 promoter activity 数据、设计数据分层和后续模型训练数据集的同学。  
阅读目标：区分高可信实验标签、弱标签和纯生信辅助数据，避免把 scaffold 说成生成模型。

## 目标

本模板用于后续整理 promoter design 所需数据。当前项目不会把弱标签或纯生信预测结果当作高可信实验标签，也不会在缺少实验验证数据时声称生成可直接使用的启动子。

## 高可信实验验证数据类型

| 数据类型 | 可信度 | 主要用途 | 注意事项 |
| --- | --- | --- | --- |
| STARR-seq | 高 | 大规模评估 enhancer / promoter-like 片段活性 | 需要明确文库设计、细胞/组织体系和统计重复 |
| MPRA | 高 | 并行测定大量候选调控序列活性 | barcode 设计、测序深度和批次效应必须记录 |
| LUC reporter assay | 高 | 对少量候选 promoter 做定量验证 | 样本量小但解释性强，适合重点候选确认 |
| 稳定转基因验证 | 最高 | 验证真实植株背景下表达强度和组织特异性 | 成本高、周期长，是最终应用前关键证据 |

## 生信辅助数据类型

| 数据类型 | 用途 | 可信边界 |
| --- | --- | --- |
| `genome.fa` | 提取 upstream / intergenic candidate promoter regions | 只提供序列来源，不等同于活性标签 |
| `genome.gff` | 定位基因结构、TSS 附近区域、上下游坐标 | 注释版本会影响 promoter 定义 |
| RNA-seq expression | 推断表达强度、组织或条件相关性 | 是表达相关证据，不是 promoter 活性实验证据 |
| TSS annotation | 定义核心 promoter 窗口 | TSS 精度决定核心启动子边界可信度 |
| motif databases | 标注 cis-regulatory motif | motif 命中不等于功能验证 |

## 数据质量分层

| Tier | 数据类型 | 可信度 | 适合用途 |
| --- | --- | --- | --- |
| Tier 1 | 稳定转基因、LUC reporter 等明确实验验证活性数据 | 最高 | 模型 gold label、重点候选验证、最终报告核心证据 |
| Tier 2 | STARR-seq、MPRA 等高通量 reporter 数据 | 高 | 训练 promoter activity predictor、筛选候选调控片段 |
| Tier 3 | RNA-seq 表达相关、TSS 附近序列、共表达推断 | 中 | 弱标签、候选区域优先级、特征辅助 |
| Tier 4 | motif 扫描、纯生信预测、跨物种保守性推断 | 低 | 特征解释、候选过滤、假设生成 |

## 为什么不能把弱标签当作高可信标签

RNA-seq 高表达、motif 命中或 TSS 附近序列只能说明候选 promoter 可能相关，不能证明该序列在目标体系中具备期望的启动子活性。如果把 Tier 3 / Tier 4 当作 Tier 1 标签训练生成模型，模型会学习表达相关偏差、注释偏差和 motif database 偏差，最终输出无法直接支撑实验应用。

因此后续 promoter generator 必须明确：

- 训练标签来自哪个 Tier。
- 弱标签是否只作为辅助特征。
- 验证集是否包含独立实验活性数据。
- 生成序列是否经过 motif、重复序列、GC、限制性位点、脱靶和实验体系约束检查。

## Inventory 表字段建议

| 字段 | 说明 |
| --- | --- |
| `record_id` | 数据记录 ID |
| `species` | 物种 |
| `gene_id` | 相关基因 |
| `sequence_id` | promoter 或 candidate regulatory sequence ID |
| `sequence_source` | genome / synthetic / cloned fragment |
| `assay_type` | STARR-seq / MPRA / LUC / stable_transgenic / RNA-seq / motif_scan |
| `activity_measure` | 活性指标或表达指标 |
| `condition` | 组织、时期、处理或实验体系 |
| `tier` | Tier 1-4 |
| `doi` | 已核验 DOI；未知时留空，不伪造 |
| `limitations` | 数据限制 |
