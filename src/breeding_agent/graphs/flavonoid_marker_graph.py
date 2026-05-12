"""Optional LangGraph workflow for flavonoid marker recommendation.

本文件定义“谷子黄酮候选标记推荐”的 LangGraph 图结构和每个图节点的具体执行逻辑。

它位于 graphs 层，作用介于 workflow 层和 agents 层之间：

- workflows/flavonoid_marker_langgraph.py：
  负责接收 UI / CLI 参数、构建初始 state、调用本文件中的 graph、
  写 manifest.json，并检查输出文件是否存在。

- graphs/flavonoid_marker_graph.py：
  也就是当前文件，负责定义 LangGraph 节点顺序、节点函数、
  graph state 的读写规则，以及 graph_trace 追踪信息。

- agents/：
  负责具体业务 agent，例如 LiteratureAgent、MarkerRecommendationAgent、
  ValidationAgent、ReviewerAgent、FinalQAAgent。

当前 LangGraph 主流程是：

load_evidence_node输入层
evidence_dir
variant_calling_dir
literature_results_path
target_genes
LLM reviewer config
        ↓
load_evidence_node
检查 evidence 文件 + 加载外部 literature JSONL
        ↓
aggregate_candidates_node
聚合 transcriptomics / metabolomics / annotation / variant / literature evidence
        ↓
build_agent_context_node
把候选基因、变异证据、文献结果、warning 组装成 agent_context
        ↓
literature_agent_node
文献分析 + DOI 来源管理 + literature_query_plan 生成
        ↓
marker_recommendation_agent_node
候选 SNP/InDel/KASP/CAPS 类型建议
        ↓
validation_agent_node
群体验证、Sanger、KASP、qRT-PCR、LC-MS/MS 等验证方案
        ↓
reviewer_agent_node
规则审阅 + 可选 LLM Reviewer 增强
        ↓
final_qa_agent_node
硬性 QA：三基因、群体、DOI、标记类型、边界
        ↓
report_node
生成 flavonoid_marker_report.md
        ↓
write_outputs_node
写 qa_check.json + literature_query_plan.jsonl/tsv
        ↓
outputs/
report / qa_check / graph_trace / graph_state / manifest / query_plan

每一步不是孤立脚本，而是围绕同一个 state 流转。
前面节点产生的 candidate_rows、literature_analysis、allowed_report_dois、
validation_plan_text 等都会进入后续节点。
state 可以理解为这条工作流的“共享工作单”。每个节点都在这张工作单上读写字段。

注意：
当前图节点主要编排规则化业务 agent。
本地 LLM 只可选增强 ReviewerAgent 的审阅文本；
LLM 不直接生成 SNP/InDel/KASP/CAPS 结论。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from breeding_agent.agents.context_builder import build_flavonoid_agent_context
from breeding_agent.agents.flavonoid_final_qa_agent import FlavonoidFinalQAAgent
from breeding_agent.agents.flavonoid_literature_agent import (
    FlavonoidLiteratureAgent,
)
from breeding_agent.agents.flavonoid_marker_recommendation_agent import (
    FlavonoidMarkerRecommendationAgent,
)
from breeding_agent.agents.flavonoid_reviewer_agent import FlavonoidReviewerAgent
from breeding_agent.agents.flavonoid_validation_agent import FlavonoidValidationAgent
from breeding_agent.graphs.state import FlavonoidGraphState
from breeding_agent.integration.flavonoid_marker_aggregator import (
    ANNOTATION_EVIDENCE,
    GENOME_VARIANT_EVIDENCE,
    LITERATURE_EVIDENCE,
    METABOLOME_EVIDENCE,
    REQUIRED_GENE_IDS,
    TRANSCRIPTOME_EVIDENCE,
    aggregate_flavonoid_marker_candidates,
)
from breeding_agent.literature.loader import load_literature_results, records_to_dicts
from breeding_agent.literature.query_plan import write_literature_query_plan
from breeding_agent.llm.executor import run_llm_reviewer
from breeding_agent.reports.flavonoid_marker_report import (
    render_flavonoid_marker_report,
)


# LangGraph 未安装时的统一提示语。
#
# workflow 层会根据这个提示判断是否可以进入 sequential fallback：
# - 如果错误是 LangGraph 未安装，则按节点顺序 fallback 执行；
# - 如果是其他 RuntimeError，则继续抛出，避免掩盖真实错误。
LANGGRAPH_INSTALL_MESSAGE = (
    "LangGraph is not installed. Install with: pip install langgraph"
)


def build_flavonoid_marker_graph():
    """构建 LangGraph StateGraph 应用。

    这里采用 lazy import，也就是在函数内部导入 langgraph。

    这样做的原因：
    - 项目可以在没有安装 LangGraph 的环境中被 import；
    - 只有真正调用 build_flavonoid_marker_graph() 时才要求 langgraph 可用；
    - workflow 层可以捕获 ImportError 转换后的 RuntimeError，并执行 fallback。

    Returns:
        编译后的 LangGraph graph app。

    Raises:
        RuntimeError:
            如果 langgraph 未安装，则抛出包含 LANGGRAPH_INSTALL_MESSAGE 的错误。
    """

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError(LANGGRAPH_INSTALL_MESSAGE) from exc

    # StateGraph 的 state 类型由 FlavonoidGraphState 定义。
    # 所有节点都接收一个 state dict，并返回更新后的 state dict。
    graph = StateGraph(FlavonoidGraphState)

    # 节点顺序对应业务流水线：
    # evidence -> aggregation -> context -> literature -> recommendation ->
    # validation -> reviewer -> QA -> report -> outputs.
    graph.add_node("load_evidence_node", load_evidence_node)
    graph.add_node("aggregate_candidates_node", aggregate_candidates_node)
    graph.add_node("build_agent_context_node", build_agent_context_node)
    graph.add_node("literature_agent_node", literature_agent_node)
    graph.add_node("marker_recommendation_agent_node", marker_recommendation_agent_node)
    graph.add_node("validation_agent_node", validation_agent_node)
    graph.add_node("reviewer_agent_node", reviewer_agent_node)
    graph.add_node("final_qa_agent_node", final_qa_agent_node)
    graph.add_node("report_node", report_node)
    graph.add_node("write_outputs_node", write_outputs_node)

    # 当前是线性图，没有分支。
    # 每个节点执行完后进入下一个节点。
    graph.add_edge(START, "load_evidence_node")
    graph.add_edge("load_evidence_node", "aggregate_candidates_node")
    graph.add_edge("aggregate_candidates_node", "build_agent_context_node")
    graph.add_edge("build_agent_context_node", "literature_agent_node")
    graph.add_edge("literature_agent_node", "marker_recommendation_agent_node")
    graph.add_edge("marker_recommendation_agent_node", "validation_agent_node")
    graph.add_edge("validation_agent_node", "reviewer_agent_node")
    graph.add_edge("reviewer_agent_node", "final_qa_agent_node")
    graph.add_edge("final_qa_agent_node", "report_node")
    graph.add_edge("report_node", "write_outputs_node")
    graph.add_edge("write_outputs_node", END)

    return graph.compile()


def load_evidence_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """检查 evidence 文件是否存在，并加载可选 literature JSONL。

    入口检查节点，这个节点只做轻量检查，只做输入检查和外部文献结果加载。
    真正的 evidence 解析和候选聚合在后面的 aggregate_candidates_node 中做。

    输入：
        evidence_dir
        literature_results_path

    1. 检查 evidence_dir 中是否存在必需 evidence 文件；
    2. 如果传入 literature_results_path，则尝试读取 JSONL 文献结果；
    3. 初始化 target_genes；
    4. 追加 graph_trace。

    注意：
        这里不解析 evidence 的具体内容。
        真正的 evidence 解析和业务解释发生在后续聚合节点和 agent 节点中。

    输出到 state：
        warnings
        literature_results
        target_genes
        graph_trace

    """

    # evidence_dir 是多组学 evidence 文件目录。
    evidence_dir = Path(str(state["evidence_dir"]))

    # 读取已有 warnings，避免覆盖前序状态。
    warnings = _warnings(state)

    # 当前规则版聚合期望的 evidence 文件。
    required = [
        TRANSCRIPTOME_EVIDENCE,
        METABOLOME_EVIDENCE,
        ANNOTATION_EVIDENCE,
        GENOME_VARIANT_EVIDENCE,
        LITERATURE_EVIDENCE,
    ]

    # 检查缺失文件。
    missing = [name for name in required if not (evidence_dir / name).exists()]
    warnings.extend(f"Evidence file missing: {evidence_dir / name}" for name in missing)

    # 可选外部文献结果 JSONL。
    # 这个文件通常来自 agri-breeding-literature-pipeline 的导出结果。
    literature_results_path = _optional_path(state.get("literature_results_path"))
    literature_results: list[dict[str, Any]] = []

    if literature_results_path is not None:
        if literature_results_path.exists():
            literature_results = records_to_dicts(
                load_literature_results(literature_results_path)
            )
        else:
            warnings.append(f"Literature results JSONL missing: {literature_results_path}")

    # 更新 state。
    state["warnings"] = warnings
    state["literature_results"] = literature_results

    # 如果 state 里还没有 target_genes，则使用默认 REQUIRED_GENE_IDS。
    state.setdefault("target_genes", list(REQUIRED_GENE_IDS))

    # 记录当前节点执行信息，用于 graph_trace.json 和 node_decision_table.tsv。
    _append_trace(
        state,
        node_name="load_evidence_node",
        input_summary=(
            f"evidence_dir={evidence_dir}; literature_results={literature_results_path}"
        ),
        output_summary=(
            f"checked={len(required)} missing={len(missing)} "
            f"literature_results={len(literature_results)}"
        ),
        warnings=[f"missing={name}" for name in missing],
        limitations=["Validates evidence file presence only; parsing happens downstream."],
    )
    return state


def aggregate_candidates_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """调用规则化聚合器，生成候选标记表和候选行。

    这个节点是 evidence 聚合的核心入口。

    它调用 aggregate_flavonoid_marker_candidates()，读取 evidence_dir 中的：
    - transcriptome evidence；
    - metabolome evidence；
    - annotation evidence；
    - literature evidence；
    - genome variant evidence；
    - 可选 candidate-region variant calling 结果。

    输出的是候选 evidence，输出会写入 state：
    - candidate_table_path；
    - candidate_rows；
    - literature_rows；
    - _variant_evidence_rows；
    - warnings。

    这个节点把转录组、代谢组、功能注释、文献 seed evidence
    和候选区域变异 evidence 聚合到三个候选基因上，形成后续 agent 可以使用的候选行。
    """

    result = aggregate_flavonoid_marker_candidates(
        evidence_dir=Path(str(state["evidence_dir"])),
        outdir=Path(str(state["outdir"])),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
    )

    warnings = _warnings(state)
    warnings.extend(str(warning) for warning in result.warnings)

    state["warnings"] = warnings
    state["candidate_table_path"] = str(result.candidate_file)
    state["candidate_rows"] = result.candidate_rows
    state["literature_rows"] = result.literature_rows

    # 私有字段，用于后续 context_builder 接入 variant calling evidence。
    state["_variant_evidence_rows"] = result.variant_evidence_rows  # type: ignore[typeddict-unknown-key]

    _append_trace(
        state,
        node_name="aggregate_candidates_node",
        input_summary=f"evidence_dir={state['evidence_dir']}",
        output_summary=f"candidate_rows={len(result.candidate_rows)}",
        warnings=result.warnings,
        limitations=["Uses existing rule-based aggregator; no marker position fabrication."],
    )
    return state


def build_agent_context_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """构建多个 agent 共用的结构化上下文。

    输入：
    candidate_rows
    variant_evidence_rows
    literature_results
    warnings
    LLM reviewer config

    调用：
    build_flavonoid_agent_context()

    输出：
    这个节点把候选行、evidence 路径、variant evidence、文献结果、warnings 等信息
    统一整理为 agent_context，输出到 state。

    后续 LiteratureAgent、MarkerRecommendationAgent、ValidationAgent、
    ReviewerAgent、FinalQAAgent 都会读取这个 context。

    这一步相当于“把原始 evidence 变成 Agent 能理解的结构化业务上下文”。
    """

    # 保留先前 context 中的内部配置，例如 _llm_reviewer_config。
    prior_context = _as_mapping(state.get("agent_context", {}))

    context = build_flavonoid_agent_context(
        evidence_dir=Path(str(state["evidence_dir"])),
        candidate_rows=state.get("candidate_rows", []),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
        variant_evidence_rows=state.get("_variant_evidence_rows", []),  # type: ignore[typeddict-item]
        literature_results_path=_optional_path(state.get("literature_results_path")),
        literature_results=state.get("literature_results", []),
        warnings=state.get("warnings", []),
    )

    # 把 LLM Reviewer 配置从旧 context 转移到新 context。
    # 这样后续 reviewer_agent_node 可以知道是否启用 LLM。
    llm_config = _as_mapping(prior_context.get("_llm_reviewer_config", {}))
    if llm_config:
        context["_llm_reviewer_config"] = llm_config

    state["agent_context"] = context

    _append_trace(
        state,
        node_name="build_agent_context_node",
        input_summary="candidate rows and evidence TSV paths",
        output_summary=(
            "context keys="
            + ",".join(sorted(key for key in context.keys() if not key.startswith("_")))
        ),
        warnings=context.get("warnings", []),
        limitations=["Builds structured context only; no LLM call."],
    )
    return state


def literature_agent_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """运行 LiteratureAgent，生成文献分析、文献综述文本和检索 query plan。

    输入：
    agent_context
    literature_evidence.tsv
    literature_results_online.jsonl
    candidate genes
    trait/crop/marker keywords

    运行：
    FlavonoidLiteratureAgent.run_with_context()

    生成：
    LiteratureAgent 消费共享 agent_context，返回：
    - literature_rows；
    - literature_results；
    - literature_analysis；
    - literature_query_plan；
    - allowed_report_dois；
    - literature_review_text。
    输出到 state

    这些字段后续会用于：
    - 标记推荐；
    - 报告生成；
    - FinalQAAgent 的 DOI 防伪检查；
    - 导出 literature_query_plan 给外部文献流水线使用。

    LiteratureAgent 现在有两部分作用。第一，它读取已有 verified DOI evidence 和外部 PubMed 检索结果，
    做文献分析和相关性分层。第二，它根据当前生信 evidence 生成 literature_query_plan，
    后续可以交给 agri-breeding-literature-pipeline 做 PubMed 检索。

    这就是现在“生信 evidence 驱动文献查询”的关键节点。它把作物、性状、候选基因、注释、代谢物、marker 关键词
    组织成 query_plan，再把 PubMed 检索结果回流后做 high / medium / background 分层。
    但要注意：
        LLM 不能新增 DOI；
        文献结果只作为候选/背景支持；
        除非文献明确命中三个基因，否则不能写成三个基因的直接实验证据。
    """

    output = FlavonoidLiteratureAgent(Path(str(state["evidence_dir"]))).run_with_context(
        state["agent_context"]
    )

    payload = output.structured_payload

    state["literature_rows"] = _rows(payload.get("literature_rows", []))
    state["literature_results"] = _rows(payload.get("literature_results", []))
    state["literature_analysis"] = _as_mapping(payload.get("literature_analysis", {}))
    state["literature_query_plan"] = _rows(payload.get("literature_query_plan", []))
    state["allowed_report_dois"] = [
        str(item) for item in payload.get("allowed_report_dois", [])
    ]
    state["literature_review_text"] = str(payload.get("literature_review_text", ""))

    # 把 LiteratureAgent 的关键结果同步回 agent_context，
    # 供后续 MarkerRecommendationAgent / FinalQAAgent 使用。
    state["agent_context"] = {
        **state.get("agent_context", {}),
        "literature_results": state.get("literature_results", []),
        "literature_analysis": state.get("literature_analysis", {}),
        "literature_query_plan": state.get("literature_query_plan", []),
        "allowed_report_dois": state.get("allowed_report_dois", []),
        "literature_review_text": state.get("literature_review_text", ""),
    }

    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="literature_agent_node",
        input_summary="literature_evidence rows",
        output=output.to_dict(),
    )
    return state


def marker_recommendation_agent_node(
    state: FlavonoidGraphState,
) -> FlavonoidGraphState:
    """候选标记类型推荐节点。运行 MarkerRecommendationAgent，生成候选标记推荐文本。

    该 agent 读取 agent_context 中的候选基因、候选标记、variant status、
    文献分析、证据强度等信息，运行 FlavonoidMarkerRecommendationAgent.run_with_context()，
    输出 marker_recommendation_text、agent_outputs、graph_trace 到 state。

    这个节点根据前面聚合出的候选基因 evidence、变异状态、文献分析结果，给出 SNP/InDel/KASP/CAPS 的候选类型建议。
    比如 Si9g34380.1 如果有 PASS variant，可以建议优先复核其 KASP 转化潜力；
    但仍需要 flanking sequence、覆盖度检查和群体验证。

    注意：
        当前输出仍是候选推荐和下一步建议，
        不能表述为最终 KASP/CAPS 标记开发完成。
    """

    output = FlavonoidMarkerRecommendationAgent().run_with_context(
        state["agent_context"]
    )

    payload = output.structured_payload
    state["marker_recommendation_text"] = str(
        payload.get("marker_recommendation_text", "")
    )

    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="marker_recommendation_agent_node",
        input_summary="candidate rows with variant status",
        output=output.to_dict(),
    )
    return state


def validation_agent_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """后续验证方案节点。运行 ValidationAgent，生成后续验证方案文本。

    输入：
    agent_context
    candidate genes
    candidate marker recommendation
    variant status

    生成：
    validation_plan_text
    输出到 state

    该节点主要回答“下一步怎么验证”：
    - 后续需要哪些群体验证；
    - 需要哪些基因型-表型关联验证；
    - 是否需要更大群体；
    - 是否需要实验验证；
    - SNP/InDel/KASP/CAPS 初筛后如何继续推进。

    注意：
    它提出验证方案，不代表验证已经完成。
    """

    output = FlavonoidValidationAgent().run_with_context(state["agent_context"])

    payload = output.structured_payload
    state["validation_plan_text"] = str(payload.get("validation_plan_text", ""))

    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="validation_agent_node",
        input_summary="candidate genes",
        output=output.to_dict(),
    )
    return state


def reviewer_agent_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """审阅节点。运行 ReviewerAgent，并可选调用本地 LLM Reviewer 增强审阅意见。

    输入：
    draft report
    agent_context
    literature_review_text
    marker_recommendation_text
    validation_plan_text
    LLM reviewer config

    该节点分为两层：

    1. 规则 ReviewerAgent：
       始终执行，基于规则检查 draft report 的边界和问题。

    2. 可选 LLM Reviewer：
       如果 llm_reviewer_enabled=True，则调用 run_llm_reviewer()；
       LLM 只用于增强 reviewer notes；
       如果 LLM 失败或 OutputGuard 不通过，则 fallback 到规则 reviewer。

    输出到 state：
    reviewer_notes
    reviewer_warnings
    llm_reviewer_metadata
    agent_outputs
    graph_trace

    ReviewerAgent 不是让大模型直接改结论，而是先生成草稿报告，再由规则审阅器检查边界；
    如果启用本地 LLM，只用于补充审阅意见，而且要经过 OutputGuard，不通过就回退到规则审阅。

    重要边界：
        LLM 不直接生成候选标记结论；
        LLM 不允许新增 DOI；
        LLM 不允许越界声称最终 KASP/CAPS 或实验验证完成。
    """

    # 先渲染一个不含 reviewer notes / QA section 的草稿报告。
    # ReviewerAgent 会基于这个草稿进行审阅。
    draft_report = render_flavonoid_marker_report(
        evidence_dir=Path(str(state["evidence_dir"])),
        candidate_rows=state.get("candidate_rows", []),
        literature_rows=state.get("literature_rows", []),
        literature_analysis=state.get("literature_analysis", {}),
        warnings=state.get("warnings", []),
        literature_review_text=state.get("literature_review_text", ""),
        marker_recommendation_text=state.get("marker_recommendation_text", ""),
        validation_plan_text=state.get("validation_plan_text", ""),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
    )

    # 构造 reviewer 使用的上下文。
    context = {
        **state.get("agent_context", {}),
        "literature_review_text": state.get("literature_review_text", ""),
        "marker_recommendation_text": state.get("marker_recommendation_text", ""),
        "validation_plan_text": state.get("validation_plan_text", ""),
        "report_text": draft_report,
    }

    reviewer = FlavonoidReviewerAgent()

    # 先执行规则版 reviewer。
    rule_output = reviewer.run_with_context(context)
    rule_payload = rule_output.structured_payload

    # 从 context 中读取 LLM reviewer 配置。
    llm_config = _llm_reviewer_config_from_context(context)

    # 可选运行 LLM reviewer。
    llm_result = run_llm_reviewer(
        context=context,
        llm_config_path=llm_config.get("llm_config_path"),
        rule_reviewer_notes=str(rule_payload.get("reviewer_notes", "")),
        enabled=bool(llm_config.get("llm_reviewer_enabled", False)),
    )

    # 保存 LLM reviewer metadata。
    # 即使没有真正调用 LLM，也会记录 enabled/used/fallback 等状态。
    llm_metadata = llm_result.to_dict()
    context["_llm_reviewer_metadata"] = llm_metadata
    state["agent_context"] = context
    state["llm_reviewer_metadata"] = llm_metadata  # type: ignore[typeddict-unknown-key]

    # 将 LLM 审阅文本合并到 reviewer 输出中。
    # 如果 llm_result.llm_used=False，则只保留规则 reviewer。
    output = reviewer.add_llm_review(
        rule_output,
        llm_review_text=llm_result.content if llm_result.llm_used else "",
        llm_metadata=llm_metadata,
    )

    payload = output.structured_payload
    state["reviewer_notes"] = str(payload.get("reviewer_notes", ""))
    state["reviewer_warnings"] = [str(item) for item in payload.get("issues", [])]

    _add_agent_output(state, output.to_dict())

    llm_summary = _llm_metadata_summary(llm_metadata)
    _append_trace(
        state,
        node_name="reviewer_agent_node",
        agent_name=str(output.agent_name),
        input_summary="draft report without reviewer notes",
        output_summary=f"{output.summary} {llm_summary}",
        evidence_used=list(output.evidence_used),
        warnings=list(output.warnings),
        limitations=[*output.limitations, llm_summary],
        passed=_passed_from_payload(payload),
        extra_metadata=llm_metadata,
    )
    return state


def final_qa_agent_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """最终硬性 QA 节点。运行 FinalQAAgent，对最终报告内容做硬性 QA 检查。

    输入：
    report_without_qa
    allowed_report_dois
    literature_analysis
    agent_context

    该节点会先渲染一个包含 reviewer_notes、但不含 QA section 的报告文本，
    然后把这个报告交给 FlavonoidFinalQAAgent 检查。

    QA 检查通常关注：
    - 是否包含固定目标基因；
    - 是否包含 “群体”；
    - 是否包含 SNP/InDel/KASP/CAPS；
    - DOI 是否来自允许来源；
    - 是否出现 LLM 伪造 DOI；
    - 是否越界声称已经完成最终标记或实验验证。
    """

    report_without_qa = render_flavonoid_marker_report(
        evidence_dir=Path(str(state["evidence_dir"])),
        candidate_rows=state.get("candidate_rows", []),
        literature_rows=state.get("literature_rows", []),
        literature_analysis=state.get("literature_analysis", {}),
        warnings=state.get("warnings", []),
        literature_review_text=state.get("literature_review_text", ""),
        marker_recommendation_text=state.get("marker_recommendation_text", ""),
        validation_plan_text=state.get("validation_plan_text", ""),
        reviewer_notes=state.get("reviewer_notes", ""),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
    )

    output = FlavonoidFinalQAAgent().run_with_context(
        {
            **state.get("agent_context", {}),
            "report_text": report_without_qa,
            "allowed_report_dois": state.get("allowed_report_dois", []),
            "literature_analysis": state.get("literature_analysis", {}),
        }
    )

    state["qa_result"] = output.structured_payload

    _add_agent_output(state, output.to_dict())
    _append_trace_from_agent(
        state,
        node_name="final_qa_agent_node",
        input_summary="report text without QA section",
        output=output.to_dict(),
    )
    return state


def report_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """生成最终 Markdown 报告并写入 reports/flavonoid_marker_report.md。

    这个节点会把前序节点产出的所有文本和结构化结果合并：

    - candidate_rows；
    - literature_rows；
    - literature_analysis；
    - literature_review_text；
    - marker_recommendation_text；
    - validation_plan_text；
    - reviewer_notes；
    - qa_result；
    - warnings；
    - variant_calling_dir。

    最终调用 render_flavonoid_marker_report() 渲染完整报告。
    输出到 state：
    report_text
    report_path

    这个节点把前面所有 agent 的结构化结果和文本结果合成最终报告。
    报告里包括候选基因证据、文献分析、标记类型建议、验证方案、不确定性和 QA 结果。
    """

    report_text = render_flavonoid_marker_report(
        evidence_dir=Path(str(state["evidence_dir"])),
        candidate_rows=state.get("candidate_rows", []),
        literature_rows=state.get("literature_rows", []),
        literature_analysis=state.get("literature_analysis", {}),
        warnings=state.get("warnings", []),
        literature_review_text=state.get("literature_review_text", ""),
        marker_recommendation_text=state.get("marker_recommendation_text", ""),
        validation_plan_text=state.get("validation_plan_text", ""),
        reviewer_notes=state.get("reviewer_notes", ""),
        qa_result=state.get("qa_result", {}),
        variant_calling_dir=_optional_path(state.get("variant_calling_dir")),
    )

    report_path = Path(str(state["outdir"])) / "reports" / "flavonoid_marker_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    state["report_text"] = report_text
    state["report_path"] = str(report_path)

    _append_trace(
        state,
        node_name="report_node",
        input_summary="agent outputs and QA result",
        output_summary=f"report_path={report_path}",
        warnings=[],
        limitations=["Writes Markdown report from existing report renderer."],
    )
    return state


def write_outputs_node(state: FlavonoidGraphState) -> FlavonoidGraphState:
    """写出结构化输出。写出 QA 文件和 Literature query plan。

    输入：
    qa_result
    literature_query_plan
    report_path
    graph state

    写出：
    logs/qa_check.json
    literature/literature_query_plan.jsonl
    literature/literature_query_plan.tsv
    同时设置：
    literature_query_plan_jsonl_path
    literature_query_plan_tsv_path
    manifest_path

    这个节点负责持久化两个重要结果：

    1. qa_check.json
       保存 FinalQAAgent 的结构化 QA 结果。

    2. literature_query_plan
       保存 LiteratureAgent 生成的文献检索计划：
       - JSONL 格式；
       - TSV 格式。

    query plan 后续可以被 agri-breeding-literature-pipeline 读取，
    实现：
    生信 evidence → 动态文献检索计划 → 文献导出 JSONL → LiteratureAgent 分析。

    这个节点把最终 QA 和文献检索计划落盘。尤其 literature_query_plan
    可以被外部 agri-breeding-literature-pipeline 读取，实现“生信 evidence → 动态文献检索 → PubMed 结果回流”的闭环。
    """

    outdir = Path(str(state["outdir"]))

    qa_path = outdir / "logs" / "qa_check.json"
    manifest_path = outdir / "manifest.json"
    qa_path.parent.mkdir(parents=True, exist_ok=True)

    # 写出 QA 检查结果。
    _write_json(qa_path, state.get("qa_result", {}))

    # 写出文献检索 query plan。
    query_plan_paths = write_literature_query_plan(
        outdir=outdir,
        query_plan=state.get("literature_query_plan", []),
    )

    state["literature_query_plan_jsonl_path"] = str(query_plan_paths["jsonl"])
    state["literature_query_plan_tsv_path"] = str(query_plan_paths["tsv"])
    state["manifest_path"] = str(manifest_path)

    _append_trace(
        state,
        node_name="write_outputs_node",
        input_summary="report path, QA result, graph state",
        output_summary=(
            f"qa_check={qa_path}; manifest={manifest_path}; "
            f"literature_query_plan={query_plan_paths['jsonl']}"
        ),
        warnings=state.get("warnings", []),
        limitations=["Graph trace artifacts are written by workflow wrapper after graph completion."],
    )
    return state


def initial_graph_state(
    *,
    evidence_dir: Path,
    outdir: Path,
    variant_calling_dir: Path | None = None,
    target_genes: list[str] | None = None,
    llm_reviewer_enabled: bool = False,
    llm_config_path: Path | None = None,
    literature_results_path: Path | None = None,
) -> FlavonoidGraphState:
    """构建 LangGraph 初始 state。

    LangGraph 中每个节点都通过 state 传递信息。
    这个函数负责把 workflow 层传来的输入参数转换成统一 state 结构。

    初始 state 中包含：

    - 输入路径：
      evidence_dir、outdir、variant_calling_dir、literature_results_path；

    - 目标基因：
      target_genes；

    - agent_context：
      存放 LLM reviewer 配置等共享上下文；

    - 中间结果占位：
      candidate_rows、literature_rows、literature_analysis、qa_result 等；

    - 输出路径占位：
      candidate_table_path、report_path、manifest_path、query_plan_path 等；

    - 追踪字段：
      graph_trace、agent_outputs、warnings、errors。

    这样可以让后续节点只关注“读 state、改 state、返回 state”。
    """

    return {
        "evidence_dir": str(evidence_dir),
        "outdir": str(outdir),
        "variant_calling_dir": str(variant_calling_dir) if variant_calling_dir else None,
        "literature_results_path": (
            str(literature_results_path) if literature_results_path else None
        ),
        "target_genes": target_genes or list(REQUIRED_GENE_IDS),
        "agent_context": {
            "_llm_reviewer_config": {
                "llm_reviewer_enabled": bool(llm_reviewer_enabled),
                "llm_config_path": str(llm_config_path) if llm_config_path else None,
            }
        },
        "candidate_table_path": None,
        "candidate_rows": [],
        "literature_rows": [],
        "literature_results": [],
        "literature_analysis": {},
        "literature_query_plan": [],
        "literature_query_plan_jsonl_path": None,
        "literature_query_plan_tsv_path": None,
        "allowed_report_dois": [],
        "agent_outputs": [],
        "reviewer_warnings": [],
        "qa_result": {},
        "report_path": None,
        "manifest_path": None,
        "graph_trace": [],
        "errors": [],
        "warnings": [],
        "llm_reviewer_enabled": llm_reviewer_enabled,  # type: ignore[typeddict-unknown-key]
        "llm_config_path": str(llm_config_path) if llm_config_path else None,  # type: ignore[typeddict-unknown-key]
        "llm_reviewer_metadata": {},  # type: ignore[typeddict-unknown-key]
    }


def _append_trace_from_agent(
    state: FlavonoidGraphState,
    *,
    node_name: str,
    input_summary: str,
    output: dict[str, Any],
) -> None:
    """把 AgentOutput 转换成 graph_trace 记录。

    多个 agent 节点都会返回类似结构：
    - agent_name；
    - summary；
    - evidence_used；
    - warnings；
    - limitations；
    - structured_payload。

    该函数把这些字段统一转成 trace row，
    方便后续写出 node_decision_table.tsv 和 graph_trace.json。
    """

    _append_trace(
        state,
        node_name=node_name,
        agent_name=str(output.get("agent_name", "")),
        input_summary=input_summary,
        output_summary=str(output.get("summary", "")),
        evidence_used=[str(item) for item in output.get("evidence_used", [])],
        warnings=[str(item) for item in output.get("warnings", [])],
        limitations=[str(item) for item in output.get("limitations", [])],
        passed=_passed_from_payload(output.get("structured_payload", {})),
    )


def _append_trace(
    state: FlavonoidGraphState,
    *,
    node_name: str,
    input_summary: str,
    output_summary: str,
    agent_name: str = "",
    evidence_used: list[str] | None = None,
    warnings: list[str] | None = None,
    limitations: list[str] | None = None,
    passed: bool | None = None,
    extra_metadata: dict[str, object] | None = None,
) -> None:
    """向 state["graph_trace"] 追加一条节点执行记录。

    graph_trace 是解释 LangGraph 工作流的核心产物之一。
    它记录每个节点：

    - node_id；
    - node_name；
    - agent_name；
    - input_summary；
    - output_summary；
    - evidence_used；
    - warnings；
    - limitations；
    - passed；
    - extra metadata。

    后续 workflow wrapper 会把 graph_trace 写成：
    - graph_trace.json；
    - node_decision_table.tsv；
    - langgraph_summary.md。
    """

    trace = list(state.get("graph_trace", []))

    row = {
        "node_id": len(trace) + 1,
        "node_name": node_name,
        "agent_name": agent_name,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "evidence_used": evidence_used or [],
        "warnings": warnings or [],
        "limitations": limitations or [],
        "passed": passed,
    }

    if extra_metadata:
        row.update(extra_metadata)

    trace.append(row)
    state["graph_trace"] = trace


def _add_agent_output(state: FlavonoidGraphState, output: dict[str, Any]) -> None:
    """把单个 agent 的完整输出追加到 state["agent_outputs"]。

    agent_outputs 保留比 graph_trace 更完整的 agent 结果，
    方便调试和后续扩展。
    """

    outputs = list(state.get("agent_outputs", []))
    outputs.append(output)
    state["agent_outputs"] = outputs


def _warnings(state: FlavonoidGraphState) -> list[str]:
    """从 state 中读取 warnings，并统一转换为字符串列表。"""

    return [str(warning) for warning in state.get("warnings", [])]


def _optional_path(value: object) -> Path | None:
    """把可选路径字段转换为 Path 或 None。

    Args:
        value:
            可能是 None、空字符串、Path 或字符串路径。

    Returns:
        - 如果 value 为空，返回 None；
        - 否则返回 Path(value)。

    注意：
        这里不检查路径是否存在，只做类型转换。
    """

    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    return Path(text)


def _rows(value: object) -> list[dict[str, str]]:
    """确保某个对象是 list[dict] 形式的记录列表。

    如果 value 不是 list，则返回空列表；
    如果 list 中有非 dict 元素，则过滤掉。
    """

    if not isinstance(value, list):
        return []

    return [row for row in value if isinstance(row, dict)]


def _as_mapping(value: object) -> dict[str, object]:
    """把 dict-like 对象转成普通 dict。

    如果 value 不是 dict，则返回空字典。
    """

    return dict(value) if isinstance(value, dict) else {}


def _llm_reviewer_config_from_context(context: dict[str, object]) -> dict[str, object]:
    """从 agent_context 中提取 LLM Reviewer 配置。

    返回字段：
    - llm_reviewer_enabled；
    - llm_config_path。

    该配置由 initial_graph_state() 写入，
    在 reviewer_agent_node() 中读取。
    """

    config = _as_mapping(context.get("_llm_reviewer_config", {}))

    return {
        "llm_reviewer_enabled": bool(config.get("llm_reviewer_enabled", False)),
        "llm_config_path": config.get("llm_config_path"),
    }


def _passed_from_payload(payload: object) -> bool | None:
    """从 structured_payload 中提取 passed 字段。

    Args:
        payload:
            agent 的 structured_payload。

    Returns:
        - True / False：如果 payload["passed"] 是布尔值；
        - None：如果没有 passed 或 payload 不是 dict。
    """

    if not isinstance(payload, dict):
        return None

    value = payload.get("passed")
    if isinstance(value, bool):
        return value

    return None


def _llm_metadata_summary(metadata: dict[str, object]) -> str:
    """把 LLM Reviewer metadata 格式化成简短字符串。

    这个字符串会写入 reviewer_agent_node 的 graph_trace，
    用于快速说明：

    - 是否启用 LLM Reviewer；
    - 是否实际调用 LLM；
    - 是否使用 fallback；
    - 使用的模型；
    - OutputGuard 是否通过；
    - fallback 原因。
    """

    return (
        "llm_reviewer_enabled={llm_reviewer_enabled}; llm_used={llm_used}; "
        "fallback_used={fallback_used}; model={model}; guard_passed={guard_passed}; "
        "fallback_reason={fallback_reason}"
    ).format(
        llm_reviewer_enabled=str(metadata.get("llm_reviewer_enabled", False)).lower(),
        llm_used=str(metadata.get("llm_used", False)).lower(),
        fallback_used=str(metadata.get("fallback_used", True)).lower(),
        model=metadata.get("model", ""),
        guard_passed=str(metadata.get("guard_passed", False)).lower(),
        fallback_reason=metadata.get("fallback_reason", ""),
    )


def _write_json(path: Path, payload: object) -> None:
    """将对象写出为 JSON 文件。

    当前主要用于写出 qa_check.json。

    设计细节：
    - 自动创建父目录；
    - indent=2 方便阅读；
    - ensure_ascii=False 保留中文；
    - 文件末尾写入换行。
    """

    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")