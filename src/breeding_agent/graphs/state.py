"""State schema for optional LangGraph flavonoid marker workflow.

本文件定义 LangGraph 版谷子黄酮候选标记推荐流程的 state schema。

在 LangGraph 中，每个节点之间不是通过函数参数逐个传值，
而是共享并逐步更新一个 state 字典。
state 可以理解为这条工作流的“共享工作单”。每个节点都在这张工作单上读写字段。
不是靠文件名乱传，也不是靠自然语言上下文传，
而是通过 FlavonoidGraphState 这个结构化 state 传递。每个节点读取 state 中已有字段，再写入新的结构化字段。

也就是说，整个流程可以理解为：

initial_graph_state()
        ↓
load_evidence_node(state)
        ↓
aggregate_candidates_node(state)
        ↓
build_agent_context_node(state)
        ↓
literature_agent_node(state)
        ↓
marker_recommendation_agent_node(state)
        ↓
validation_agent_node(state)
        ↓
reviewer_agent_node(state)
        ↓
final_qa_agent_node(state)
        ↓
report_node(state)
        ↓
write_outputs_node(state)

每个节点都会读取 state 中已有字段，并写入新的字段。
本文件中的 FlavonoidGraphState 就是对这个 state 的结构约束。

初始 state 主要包含：
evidence_dir：多组学 evidence 目录
outdir：输出目录
variant_calling_dir：候选区域变异 evidence 目录
literature_results_path：外部文献检索结果 JSONL
target_genes：Si9g04210.1、Si5g31340.1、Si9g34380.1
agent_context：给各个 agent 共用的上下文
candidate_rows：候选基因/标记行
literature_analysis：文献分析结果
literature_query_plan：文献检索计划
allowed_report_dois：报告允许出现的 DOI
qa_result：最终 QA 结果
report_path：最终报告路径
graph_trace：节点执行记录
warnings / errors：警告和错误

"""

from __future__ import annotations

from typing import Any, TypedDict

'''
这里使用 TypedDict 只是为了类型提示和代码可读性，不会在运行时强制校验字段。
'''
class FlavonoidGraphState(TypedDict, total=False):
    """LangGraph 节点之间传递的 JSON 可序列化状态对象。

    total=False 表示该 TypedDict 中的字段都是可选字段。

    这样设计的原因是：
    - 不同节点负责写入不同字段；
    - 初始 state 只包含一部分字段；
    - 随着 graph 执行，后续节点逐渐补充 candidate_rows、literature_analysis、
      reviewer_notes、qa_result、report_path 等字段；
    - 某些字段只有在启用特定功能时才会存在，例如 literature_results_path、
      variant_calling_dir、LLM reviewer metadata 等。

    设计原则：
    - 尽量使用 str、list、dict、None 等 JSON 友好类型；
    - 避免在 state 中直接保存复杂 Python 对象；
    - 方便最终写出 graph_state_final.json 和 graph_trace.json。
    """

    # -----------------------------
    # 基础输入路径
    # -----------------------------

    # evidence 文件目录。
    #
    # 通常包含：
    # - transcriptome_evidence.tsv
    # - metabolome_evidence.tsv
    # - annotation_evidence.tsv
    # - genome_variant_evidence.tsv
    # - literature_evidence.tsv
    evidence_dir: str

    # LangGraph workflow 输出目录。
    #
    # 典型输出包括：
    # - graph/graph_trace.json
    # - graph/graph_state_final.json
    # - graph/node_decision_table.tsv
    # - graph/langgraph_summary.md
    # - reports/flavonoid_marker_report.md
    # - logs/qa_check.json
    # - manifest.json
    outdir: str

    # 可选 candidate-region variant calling 输出目录。
    #
    # 如果提供，后续聚合器和 context_builder 可以读取：
    # - candidate_variants.tsv
    # - snp_candidates.tsv
    # - indel_candidates.tsv
    # - kasp_candidate_sites.tsv
    # - caps_candidate_sites.tsv
    #
    # 如果为 None，则不接入候选变异检测 evidence。
    variant_calling_dir: str | None

    # 可选外部文献检索结果 JSONL 路径。
    #
    # 通常来自 agri-breeding-literature-pipeline 的导出结果。
    # LiteratureAgent 会读取该 JSONL，但不会在本流程中直接调用外部 API。
    literature_results_path: str | None

    # 当前 workflow 关注的目标基因列表。
    #
    # 默认通常是：
    # - Si9g04210.1
    # - Si5g31340.1
    # - Si9g34380.1
    target_genes: list[str]

    # -----------------------------
    # Agent 共享上下文
    # -----------------------------

    # 多个 agent 共用的结构化上下文。
    #
    # build_agent_context_node 会把候选表、evidence 路径、variant evidence、
    # literature results、warnings 等整理到这里。
    #
    # 后续 agent 主要从 agent_context 中读取业务输入。
    agent_context: dict[str, Any]

    # -----------------------------
    # 候选标记聚合结果
    # -----------------------------

    # 候选标记表路径。
    #
    # 通常指向：
    # outdir / integration / flavonoid_marker_candidates.tsv
    candidate_table_path: str | None

    # 候选标记记录列表。
    #
    # aggregate_candidates_node 写入该字段。
    # 后续 MarkerRecommendationAgent、ValidationAgent、报告生成器都会使用。
    candidate_rows: list[dict[str, str]]

    # literature_evidence.tsv 中读取或聚合出的文献 evidence 行。
    #
    # 这是项目内部 verified DOI / seed literature evidence 的一部分。
    literature_rows: list[dict[str, str]]

    # 外部 literature_results JSONL 读取后的文献结果。
    #
    # 例如来自 PubMed export 的真实检索结果，或 demo fixture 结果。
    # LiteratureAgent 会进一步区分 real external result 和 demo fixture。
    literature_results: list[dict[str, Any]]

    # LiteratureAgent 生成的结构化文献分析结果。
    #
    # 通常包含：
    # - literature_result_count
    # - literature_query_count
    # - verified_doi_count
    # - real_result_count
    # - demo_result_count
    # - doi_sources
    # - relevance_counts
    # 等。
    literature_analysis: dict[str, Any]

    # LiteratureAgent 根据候选基因和证据动态生成的文献检索计划。
    #
    # 后续会被 write_outputs_node 写成：
    # - literature_query_plan.jsonl
    # - literature_query_plan.tsv
    #
    # 这样外部文献流水线可以读取这些 query，执行在线或离线文献检索。
    literature_query_plan: list[dict[str, Any]]

    # 文献 query plan 的 JSONL 输出路径。
    literature_query_plan_jsonl_path: str | None

    # 文献 query plan 的 TSV 输出路径。
    literature_query_plan_tsv_path: str | None

    # 最终报告允许出现的 DOI 列表。
    #
    # FinalQAAgent 会用它检查报告中 DOI 是否来自允许来源，
    # 防止 LLM 或报告生成过程产生虚构 DOI。
    allowed_report_dois: list[str]

    # -----------------------------
    # 各 agent 生成的文本片段
    # -----------------------------

    # LiteratureAgent 生成的文献综述/文献分析文本。
    literature_review_text: str

    # MarkerRecommendationAgent 生成的候选标记推荐文本。
    #
    # 这里应保持 preliminary candidate marker recommendation 的边界，
    # 不能声称已经完成最终 KASP/CAPS 标记开发。
    marker_recommendation_text: str

    # ValidationAgent 生成的后续验证方案文本。
    #
    # 通常包括：
    # - 更大群体；
    # - 基因型-黄酮含量关联；
    # - 表型验证；
    # - 实验验证；
    # - KASP/CAPS 后续复核。
    validation_plan_text: str

    # ReviewerAgent 生成的审阅意见。
    #
    # 如果启用 LLM Reviewer，该字段可能包含规则 reviewer + LLM reviewer 的合并结果；
    # 如果 LLM 未启用或 fallback，则主要来自规则 reviewer。
    reviewer_notes: str

    # 所有 agent 的完整输出列表。
    #
    # 每个元素通常包含：
    # - agent_name
    # - summary
    # - evidence_used
    # - warnings
    # - limitations
    # - structured_payload
    agent_outputs: list[dict[str, Any]]

    # ReviewerAgent 发现的问题或警告。
    reviewer_warnings: list[str]

    # -----------------------------
    # QA 与报告结果
    # -----------------------------

    # FinalQAAgent 的结构化 QA 结果。
    #
    # 通常包含：
    # - passed
    # - missing_items
    # - doi_sources
    # - no_llm_generated_doi
    # - unexpected_dois
    # - literature_result_count
    # - literature_query_count
    # 等。
    qa_result: dict[str, Any]

    # 最终 Markdown 报告文本。
    #
    # report_node 生成并写入 report_path。
    report_text: str

    # 最终报告文件路径。
    #
    # 通常是：
    # outdir / reports / flavonoid_marker_report.md
    report_path: str | None

    # workflow manifest 文件路径。
    #
    # 通常是：
    # outdir / manifest.json
    manifest_path: str | None

    # -----------------------------
    # 图执行追踪与诊断信息
    # -----------------------------

    # 图节点执行追踪记录。
    #
    # 每个节点会通过 _append_trace() 追加一条记录，包括：
    # - node_id
    # - node_name
    # - agent_name
    # - input_summary
    # - output_summary
    # - evidence_used
    # - warnings
    # - limitations
    # - passed
    #
    # 后续会写成 graph_trace.json 和 node_decision_table.tsv。
    graph_trace: list[dict[str, Any]]

    # 错误信息列表。
    #
    # 当前主要作为预留字段，方便未来节点不直接抛异常，
    # 而是把部分可恢复错误写入 state。
    errors: list[str]

    # 警告信息列表。
    #
    # 例如：
    # - evidence 文件缺失；
    # - literature_results JSONL 缺失；
    # - variant_calling_dir 不存在；
    # - LangGraph 未安装并使用 sequential fallback；
    # - 某些证据只能作为 preliminary evidence。
    warnings: list[str]