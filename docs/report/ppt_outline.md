# breeding-agent 组会汇报 PPT Outline

适用场景：科研组会 / 项目阶段汇报  
画幅：16:9  
风格：白底、深蓝/灰色主色、少装饰、图多于字、每页 3-5 个核心信息点  
硬性边界：所有表述严格限定在当前仓库真实状态，不把候选推荐写成最终实验结果。

## Deck Logic

1. 先说明当前项目已经支持哪些本地任务入口。
2. 再说明代码层怎样把数据处理、证据聚合、Agent、QA 和展示分开。
3. 接着展示固定输入、固定候选基因、统计值和 DOI 的来源。
4. 最后说明 LangGraph、LLM Reviewer、Gradio、Deep Agents POC、Lobster-style benchmark 和 Promoter Design scaffold 的边界。

## Slide Plan

### 1. 项目当前能本地生成候选标记建议，但不输出最终实验标记

**Visual:** application architecture diagram  
**Core message:** 当前可运行入口覆盖 DEG 复现、黄酮候选标记推荐、候选区域变异 calling、LangGraph 运行和 Gradio 展示。  
**On-slide points:**

- 研究对象固定为谷子黄酮相关候选标记推荐。
- 默认流程读取本地文件，不调用外部 API。
- 输出是候选建议、报告和验证计划，不是定稿标记。

### 2. 代码层把数据处理、Agent 编排、QA 和展示分开实现

**Visual:** technical architecture diagram  
**Core message:** 核心业务逻辑保留在 `workflows/`、`integration/`、`agents/`、`graphs/`、`llm/` 和 `reports/`，Gradio 只触发和展示。  
**On-slide points:**

- `integration/` 聚合 evidence 并生成候选表。
- `graphs/` 承载 LangGraph 主线多 Agent 编排。
- `llm/` 只服务 ReviewerAgent 的可选审阅增强。
- `FinalQAAgent` 和 `output_guard` 负责发布前检查。

### 3. 学长 mini 数据包先转换为标准 evidence，再进入报告生成

**Visual:** data-flow diagram  
**Core message:** 原始 BAM、代谢组、基因组、注释和文献证据先进入标准 evidence 表，再由 workflow 读取。  
**On-slide points:**

- 转录组输入：`bam/` 中所有文件；代谢组输入：`metabolome_raw_3372.tsv`。
- 基因组输入：`genome.fa` 和 `genome.gff`；功能注释输入：`local_region_emapper_annotations.tsv`。
- 文献证据只读取已验证 DOI，不新增 DOI。
- `variant_status=not_called` 时不写具体 SNP/InDel 位置。

### 4. 三个高优先基因已有统计证据，但还不是育种验证结论

**Visual:** compact evidence table  
**Core message:** `Si9g04210.1`、`Si5g31340.1`、`Si9g34380.1` 均有表达差异和代谢相关证据。  
**On-slide points:**

- `Si9g04210.1`: log2FC -6.5426, padj 5.62e-158, Green higher。
- `Si5g31340.1`: log2FC 1.5744, padj 4.71e-07, Golden higher。
- `Si9g34380.1`: log2FC 3.2050, padj 8.95e-14, Golden higher。
- 这些是 package-derived evidence，不等同于大群体验证。

### 5. 规则化 aggregation 只给候选标记类型建议，不写最终标记结论

**Visual:** evidence-to-report flow  
**Core message:** 规则 workflow 聚合 transcriptomics、metabolomics、annotation、literature 和 variant evidence，并通过 QA 检查输出。  
**On-slide points:**

- SNP/InDel/KASP/CAPS 是候选类型建议；KASP/CAPS 表只是 preliminary screening。
- `variant_status=not_called` 时不能写具体 SNP/InDel 位置。
- 必须保留“群体”关联验证建议。
- 固定建议：优先围绕三个基因开发候选 SNP/InDel/KASP 标记，再用更大群体数据验证关联。

### 6. LangGraph 是主线多 Agent 编排层，默认仍运行规则 Agent

**Visual:** LangGraph node sequence  
**Core message:** LangGraph 负责任务节点和 Agent 顺序，不承担模型推理；旧 CLI 保持可用。  
**On-slide points:**

- 节点覆盖 evidence load、aggregation、context、agent、review、QA 和 report。
- 每个 node 记录 trace、warnings、limitations 和 passed 状态。
- Deep Agents 是并行 POC，不替代 LangGraph。

### 7. LLM 目前只增强 ReviewerAgent，OutputGuard 和 FinalQAAgent 负责拦截风险

**Visual:** guardrail pipeline  
**Core message:** 本地 OpenAI-compatible LLM 只增强 reviewer notes，不能直接生成 marker 结论。  
**On-slide points:**

- 只有 `reviewer_agent_node` 可选调用本地 LLM。
- 请求必须传 `chat_template_kwargs.enable_thinking=false`。
- output_guard 拦截伪造 DOI、伪造位点、LowQual 优先化和 KASP/CAPS 过度表述。
- 失败、空输出或 guard 不通过时回退到规则 ReviewerAgent，再进入 FinalQAAgent。

### 8. Candidate variant calling 提供候选区域初筛证据，不能替代 WGS/GBS 群体验证

**Visual:** variant evidence boundary diagram  
**Core message:** Genomics Candidate Variant Calling MVP 只在候选区域内解析真实 VCF 位点并做 PASS/LowQual 分层。  
**On-slide points:**

- workflow 使用 `samtools` / `bcftools`，只写 VCF 中真实存在的位点。
- PASS SNP 可进入后续 KASP 转化潜力复核。
- LowQual 只保留可追溯记录，不能直接优先开发。
- 后续仍需 WGS/GBS 群体变异 calling 和基因型-黄酮含量关联验证。

### 9. Gradio 只负责展示和触发，不承载核心 evidence 逻辑

**Visual:** UI-to-backend boundary diagram  
**Core message:** Gradio 通过 Tab 展示结果并触发 workflow；核心分析仍在后端模块。  
**On-slide points:**

- 后端业务逻辑保留在 `workflows/`、`integration/`、`agents/`、`graphs/`。
- Gradio 可展示 LLM reviewer 状态，但不展示本地配置文件内容。
- 当前 Gradio 不替代 CLI，也不重新实现核心分析。

### 10. Deep Agents、Lobster-style benchmark 和 Promoter Design 都保持 POC / scaffold 边界

**Visual:** maturity matrix  
**Core message:** 这些模块提供后续扩展入口，但当前不能写成真实运行或实验完成。  
**On-slide points:**

- Deep Agents POC 不调用真实 LLM、不替代 LangGraph。
- Lobster-style benchmark 只是 reference benchmark，不是外部 AI run。
- Promoter Design 只定义 schema、数据盘点和占位输出，不生成真实 promoter sequence。
- manifest、QA 和 reviewer notes 保留边界说明。

### 11. 下一阶段应优先补候选位点复核和群体验证证据

**Visual:** roadmap with validation gates  
**Core message:** 当前项目已经能生成可追溯候选建议，下一步应补齐变异位点复核、标记转化检查和群体验证。  
**On-slide points:**

- 复核候选区域 PASS SNP/InDel 的 coverage、flanking sequence 和 KASP/CAPS 可转化性。
- 扩展 WGS/GBS 群体 variant calling，并与黄酮含量做关联验证。
- 对高优先基因补充 qRT-PCR、LC-MS/MS、Sanger 或目标区域验证。
- 报告发布前继续保留 OutputGuard、FinalQAAgent 和人工 review。

## Speaker Notes

- 不要说“标记定稿”；只能说“给出候选类型建议”和“preliminary screening”。
- 不要说“完成 WGS/GBS 群体验证”；只能说“后续需要更大群体验证”。
- 不要说“完成实验验证”；只能说“验证计划已生成”。
- 不要说“真实运行 Lobster AI”；当前是 Lobster-style reference benchmark。
- 不要说“真实 promoter design”；当前是 Promoter Design scaffold。
- 必须说明 LLM 目前只增强 ReviewerAgent。
- 必须说明 LangGraph 是主线多 Agent 编排层。
- 必须说明 Gradio 是展示层。
- 必须说明 OutputGuard 和 FinalQAAgent 做兜底。
