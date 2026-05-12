"""Workflow wrapper for optional LangGraph flavonoid marker recommendation.

本文件是“LangGraph 版谷子黄酮候选标记推荐流程”的 workflow 包装层。

它的定位不同于旧版 flavonoid_marker_aggregation.py：

- flavonoid_marker_aggregation.py：
  传统规则 workflow，直接调用 FlavonoidCentralHost 聚合 evidence。

- flavonoid_marker_langgraph.py：
  LangGraph workflow 包装层，负责构建 graph state，
  通过 LangGraph 节点编排多个业务 agent；
  如果当前环境没有安装 LangGraph，则自动走 sequential fallback，
  也就是按固定节点顺序逐个执行。

整体调用链可以理解为：

Gradio UI / CLI
        ↓
FlavonoidMarkerLangGraphConfig
        ↓
run_flavonoid_marker_langgraph_task()
        ↓
initial_graph_state()
        ↓
_invoke_graph_or_fallback()
        ↓
LangGraph graph.invoke(initial_state)
或 sequential fallback node-by-node
        ↓
write_langgraph_trace_reports()
        ↓
manifest.json / graph_trace.json / node_decision_table.tsv /
langgraph_summary.md / graph_state_final.json / final report / qa_check.json

当前 workflow 的主要职责：

1. 接收 evidence_dir、variant_calling_dir、literature_results、LLM reviewer 配置；
2. 构建初始 graph state；
3. 优先尝试运行 LangGraph；
4. 如果 LangGraph 未安装，则按节点顺序执行 fallback；
5. 写出 graph trace、节点决策表、summary 和 final state；
6. 收集输出路径、QA 结果、LLM reviewer metadata；
7. 写出 manifest.json；
8. 检查关键输出文件是否存在。

注意：
当前流程仍是规则化 breeding-agent workflow。
LLM Reviewer 是可选增强，并且只用于 ReviewerAgent 的审阅文本增强；
它不直接生成 SNP/InDel/KASP/CAPS 结论。
最终输出仍需要经过 OutputGuard / FinalQAAgent 等边界检查。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.graphs.flavonoid_marker_graph import (
    LANGGRAPH_INSTALL_MESSAGE,
    aggregate_candidates_node,
    build_flavonoid_marker_graph,
    build_agent_context_node,
    final_qa_agent_node,
    initial_graph_state,
    literature_agent_node,
    load_evidence_node,
    marker_recommendation_agent_node,
    report_node,
    reviewer_agent_node,
    validation_agent_node,
    write_outputs_node,
)
from breeding_agent.reports.langgraph_trace_report import (
    write_langgraph_trace_reports,
)


# LangGraph workflow 默认输出目录。
#
# 典型输出结构：
# outputs/flavonoid_marker_langgraph/
#   manifest.json
#   graph/
#     graph_trace.json
#     graph_state_final.json
#     node_decision_table.tsv
#     langgraph_summary.md
#   reports/
#     flavonoid_marker_report.md
#   logs/
#     qa_check.json
#   literature/
#     literature_query_plan.jsonl
#     literature_query_plan.tsv
DEFAULT_LANGGRAPH_OUTDIR = "outputs/flavonoid_marker_langgraph"


@dataclass(frozen=True)
class FlavonoidMarkerLangGraphConfig:
    """LangGraph 版黄酮候选标记推荐 workflow 的输入配置。

    这个 dataclass 用于统一承载 LangGraph workflow 的所有输入参数。

    Attributes:
        evidence_dir:
            多组学 evidence 文件目录。

            通常包括：
            - transcriptome_evidence.tsv
            - metabolome_evidence.tsv
            - annotation_evidence.tsv
            - genome_variant_evidence.tsv
            - literature_evidence.tsv

        outdir:
            LangGraph workflow 输出目录。

            默认是：
            outputs/flavonoid_marker_langgraph

        variant_calling_dir:
            可选的 candidate-region variant calling 输出目录。

            如果提供，workflow 可以接入：
            - candidate_variants.tsv
            - snp_candidates.tsv
            - indel_candidates.tsv
            - kasp_candidate_sites.tsv
            - caps_candidate_sites.tsv

            如果为 None，则不接入变异检测 evidence。

        literature_results:
            可选的外部文献检索结果 JSONL 文件。

            当前 LiteratureAgent v2/v3 只读取该 JSONL 和 verified DOI evidence；
            不在 Gradio/LangGraph 流程里直接调用外部 API。

        target_genes:
            可选目标基因列表。

            如果为 None，graph state 内部通常会使用默认目标基因：
            - Si9g04210.1
            - Si5g31340.1
            - Si9g34380.1

        use_llm_reviewer:
            是否启用本地 LLM Reviewer。

            注意：
            该选项只增强 ReviewerAgent 的审阅说明；
            不允许 LLM 直接生成最终 SNP/InDel/KASP/CAPS 结论。

        llm_config:
            本地 LLM Reviewer 配置文件路径。

            例如：
            configs/llm.local.yaml

            只有 use_llm_reviewer=True 且路径存在时才有意义。
    """

    evidence_dir: Path
    outdir: Path = Path(DEFAULT_LANGGRAPH_OUTDIR)
    variant_calling_dir: Path | None = None
    literature_results: Path | None = None
    target_genes: list[str] | None = None
    use_llm_reviewer: bool = False
    llm_config: Path | None = None


def run_flavonoid_marker_langgraph_task(
    config: FlavonoidMarkerLangGraphConfig,
) -> dict[str, object]:
    """运行 LangGraph 版黄酮候选标记推荐流程，并写出 graph artifacts。

    这是本文件的核心 workflow 函数。

    主流程：

    1. 展开并解析输入路径；
    2. 初始化 manifest.json；
    3. 调用 initial_graph_state() 构建初始 graph state；
    4. 调用 _invoke_graph_or_fallback()：
       - 如果 LangGraph 可用，则 graph.invoke(initial_state)；
       - 如果未安装 LangGraph，则顺序执行各节点 fallback；
    5. 调用 write_langgraph_trace_reports() 写出 graph 追踪文件；
    6. 汇总 candidate_table、report、qa_check、query plan、trace outputs 等路径；
    7. 更新 manifest 状态、outputs、warnings、qa_result、agent_layer 等；
    8. 写出 manifest.json；
    9. 检查关键输出路径是否存在；
    10. 返回 final_state、outputs、qa_result、llm_reviewer metadata。

    Args:
        config:
            LangGraph workflow 配置。

    Returns:
        result:
            一个结构化字典，包含：
            - final_state
            - outputs
            - qa_result
            - llm_reviewer

    Raises:
        Exception:
            如果 evidence 读取、graph 执行、fallback 执行、报告生成、
            trace 写出或输出文件检查失败，会记录 manifest 后继续抛出异常。
    """

    # 记录开始时间。
    start_time = _utc_now()

    # 将输出目录、evidence 目录等路径展开为绝对路径。
    # expanduser() 处理 ~；
    # resolve() 转为绝对路径，便于 manifest 记录和下游读取。
    outdir = config.outdir.expanduser().resolve()
    evidence_dir = config.evidence_dir.expanduser().resolve()

    # 可选 variant calling 输出目录。
    variant_calling_dir = (
        config.variant_calling_dir.expanduser().resolve()
        if config.variant_calling_dir
        else None
    )

    # 可选文献结果 JSONL 路径。
    literature_results = (
        config.literature_results.expanduser().resolve()
        if config.literature_results
        else None
    )

    # 可选本地 LLM 配置路径。
    llm_config = (
        config.llm_config.expanduser().resolve()
        if config.llm_config
        else None
    )

    # manifest.json 路径。
    manifest_path = outdir / "manifest.json"

    # 确保输出目录存在。
    outdir.mkdir(parents=True, exist_ok=True)

    # 初始化 manifest。
    #
    # 这里的 agent_layer 很关键：
    # 它明确记录当前流程是否使用 LangGraph、是否使用 LLM、
    # 是否使用外部 API、是否使用 Deep Agents。
    #
    # 这样报告和答辩时可以清楚说明项目边界：
    # - LangGraph 是编排层；
    # - LLM 只增强 ReviewerAgent；
    # - 不调用外部 API；
    # - 不使用 Deep Agents 真实依赖；
    # - 主流程仍是规则化业务 agent。
    manifest: dict[str, object] = {
        "task_name": "flavonoid_marker_langgraph",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "evidence_dir": str(evidence_dir),
        "outdir": str(outdir),
        "variant_calling_dir": str(variant_calling_dir) if variant_calling_dir else None,
        "literature_results": str(literature_results) if literature_results else None,
        "outputs": {},
        "warnings": [],
        "error_message": None,
        "agent_layer": {
            # The workflow is still rule-based; LLM reviewer support is optional
            # and isolated to reviewer-note enhancement only.
            "mode": "langgraph_rule_based_agents",
            "uses_llm": bool(config.use_llm_reviewer),
            "llm_reviewer_enabled": bool(config.use_llm_reviewer),
            "llm_config": str(llm_config) if llm_config else None,
            "uses_external_api": False,
            "uses_deep_agents": False,
            "uses_langgraph": True,
        },
    }

    try:
        # -----------------------------
        # 1. 构建初始 graph state
        # -----------------------------
        #
        # initial_graph_state() 会把所有输入路径、目标基因、LLM reviewer 设置等
        # 封装成 LangGraph 节点可以共享和传递的 state。
        #
        # 后续每个节点都会读取 state、写回 state。
        initial_state = initial_graph_state(
            evidence_dir=evidence_dir,
            outdir=outdir,
            variant_calling_dir=variant_calling_dir,
            literature_results_path=literature_results,
            target_genes=config.target_genes,
            llm_reviewer_enabled=config.use_llm_reviewer,
            llm_config_path=llm_config,
        )

        # -----------------------------
        # 2. 调用 LangGraph 或 fallback
        # -----------------------------
        #
        # 如果 langgraph 包可用：
        #     build_flavonoid_marker_graph().invoke(initial_state)
        #
        # 如果 langgraph 未安装：
        #     按固定节点顺序 sequential fallback 执行。
        #
        # 返回：
        # - final_state：最终 graph state；
        # - langgraph_dependency_available：是否真正使用了 LangGraph 依赖。
        final_state, langgraph_dependency_available = _invoke_graph_or_fallback(
            initial_state
        )

        # -----------------------------
        # 3. 写出 graph trace 和可视化追踪报告
        # -----------------------------
        #
        # write_langgraph_trace_reports() 通常会生成：
        # - graph_trace.json
        # - graph_state_final.json
        # - node_decision_table.tsv
        # - langgraph_summary.md
        #
        # 这些文件用于解释每个节点做了什么、输入输出是什么、有哪些 warning。
        trace_outputs = write_langgraph_trace_reports(
            outdir=outdir,
            final_state=final_state,
        )

        # -----------------------------
        # 4. 汇总关键输出路径
        # -----------------------------
        #
        # final_state 中保存了候选表、报告、query plan 等路径；
        # trace_outputs 中保存了 graph 追踪产物路径。
        outputs: dict[str, str] = {
            "candidate_table": _path_text(final_state.get("candidate_table_path")),
            "report": _path_text(final_state.get("report_path")),
            "qa_check": str((outdir / "logs" / "qa_check.json").resolve()),
            "manifest": str(manifest_path.resolve()),
            "literature_query_plan_jsonl": _path_text(
                final_state.get("literature_query_plan_jsonl_path")
            ),
            "literature_query_plan_tsv": _path_text(
                final_state.get("literature_query_plan_tsv_path")
            ),
            **{key: str(value) for key, value in trace_outputs.items()},
        }

        # -----------------------------
        # 5. 更新 manifest 成功状态
        # -----------------------------
        manifest["status"] = "success"
        manifest["outputs"] = outputs
        manifest["warnings"] = final_state.get("warnings", [])
        manifest["qa_result"] = final_state.get("qa_result", {})

        # 记录 LiteratureAgent 生成的 query plan 数量。
        # 这个字段可以证明“生信 evidence → 动态文献检索 query plan”的链路。
        manifest["literature_query_plan_count"] = len(
            final_state.get("literature_query_plan", [])
        )

        # 记录 LLM Reviewer 实际使用情况。
        manifest["llm_reviewer"] = _llm_reviewer_metadata(final_state)

        # 更新 agent_layer 中 LangGraph 依赖是否可用的信息。
        #
        # 如果当前环境未安装 LangGraph：
        # - langgraph_dependency_available=False；
        # - uses_langgraph=False；
        # - 但 workflow 仍通过 sequential fallback 完成。
        manifest["agent_layer"]["langgraph_dependency_available"] = (
            langgraph_dependency_available
        )
        manifest["agent_layer"]["uses_langgraph"] = langgraph_dependency_available

        # 记录 graph trace 节点数量。
        manifest["graph_trace_nodes"] = len(final_state.get("graph_trace", []))

        # 成功时写入结束时间并写出 manifest。
        manifest["end_time"] = _utc_now()
        _write_json(manifest_path, manifest)

        # 检查关键输出文件是否真实存在。
        # 这一步可以防止 workflow 返回 success 但关键文件缺失。
        _assert_output_paths_exist(outputs)

        # 返回结构化结果给 Gradio / CLI / 测试代码。
        result: dict[str, object] = {
            "final_state": final_state,
            "outputs": outputs,
            "qa_result": final_state.get("qa_result", {}),
            "llm_reviewer": _llm_reviewer_metadata(final_state),
        }
        return result

    except Exception as exc:
        # -----------------------------
        # 失败处理
        # -----------------------------
        #
        # 记录 failed 和错误信息。
        # 异常继续向上抛出，方便 Gradio / CLI / 测试捕获并显示。
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise

    finally:
        # -----------------------------
        # 非成功情况下的 manifest 收尾
        # -----------------------------
        #
        # 注意：
        # 成功分支中已经提前写过 manifest，并且状态为 success。
        # 因此这里仅在非 success 时补写 end_time 和 manifest。
        if manifest.get("status") != "success":
            manifest["end_time"] = _utc_now()
            _write_json(manifest_path, manifest)


def _utc_now() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。

    用于 manifest.json 中的 start_time 和 end_time。

    使用 UTC 的好处：
    - 避免不同时区造成时间记录混乱；
    - 方便跨虚拟机、服务器、本地环境对齐日志；
    - 更适合作为可追溯运行记录。
    """

    return datetime.now(timezone.utc).isoformat()


def _invoke_graph_or_fallback(initial_state: dict[str, object]) -> tuple[dict[str, object], bool]:
    """优先调用 LangGraph；如果未安装 LangGraph，则执行 sequential fallback。

    Args:
        initial_state:
            初始 graph state。

    Returns:
        二元组：
        - final_state:
          执行完成后的最终 state；
        - langgraph_dependency_available:
          True 表示真正使用了 LangGraph；
          False 表示 LangGraph 未安装，使用顺序 fallback。

    设计意义：
        这个函数保证项目即使在没有安装 LangGraph 的环境中也能跑通。
        对演示和测试很重要，因为不同机器可能没有安装 langgraph 包。

    fallback 节点顺序：

        1. load_evidence_node
        2. aggregate_candidates_node
        3. build_agent_context_node
        4. literature_agent_node
        5. marker_recommendation_agent_node
        6. validation_agent_node
        7. reviewer_agent_node
        8. final_qa_agent_node
        9. report_node
        10. write_outputs_node

    这基本对应 LangGraph 图中的主要业务流程。
    """

    try:
        # 尝试构建真正的 LangGraph graph。
        graph = build_flavonoid_marker_graph()

    except RuntimeError as exc:
        # 如果 RuntimeError 不是“LangGraph 未安装”导致的，则继续抛出。
        # 这样不会误吞其他真实错误。
        if LANGGRAPH_INSTALL_MESSAGE not in str(exc):
            raise

        # LangGraph 未安装时，执行 sequential fallback。
        #
        # state 会被每个节点依次读取和更新。
        state = initial_state

        for node in [
            load_evidence_node,
            aggregate_candidates_node,
            build_agent_context_node,
            literature_agent_node,
            marker_recommendation_agent_node,
            validation_agent_node,
            reviewer_agent_node,
            final_qa_agent_node,
            report_node,
            write_outputs_node,
        ]:
            state = node(state)  # type: ignore[arg-type, assignment]

        # 添加 fallback warning，明确记录本次并没有真正使用 LangGraph。
        warnings = list(state.get("warnings", []))
        warnings.append(LANGGRAPH_INSTALL_MESSAGE + "; executed sequential fallback.")
        state["warnings"] = warnings

        return state, False

    # 如果 LangGraph 可用，正常调用 graph.invoke(initial_state)。
    return graph.invoke(initial_state), True


def _write_json(path: Path, payload: object) -> None:
    """将对象写出为 JSON 文件。

    Args:
        path:
            输出 JSON 文件路径。

        payload:
            可 JSON 序列化的对象。

    当前主要用于写 manifest.json。

    设计细节：
    - 自动创建父目录；
    - indent=2 让 JSON 更易读；
    - ensure_ascii=False 保留中文字符；
    - 末尾写入换行，符合常见文本文件习惯。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _path_text(value: object) -> str:
    """把路径类对象或路径字符串标准化为绝对路径字符串。

    Args:
        value:
            可能是 Path、字符串或 None。

    Returns:
        如果 value 为空，返回空字符串；
        否则返回 expanduser + resolve 后的路径字符串。

    用途：
        final_state 中某些路径字段可能是 Path，也可能是字符串。
        该函数统一转换，方便写入 outputs 和 manifest。
    """

    if not value:
        return ""
    return str(Path(str(value)).expanduser().resolve())


def _assert_output_paths_exist(outputs: dict[str, str]) -> None:
    """检查 LangGraph workflow 的关键输出文件是否存在。

    Args:
        outputs:
            输出路径字典。

    Raises:
        FileNotFoundError:
            如果关键输出缺失，则抛出异常。

    检查原因：
        workflow 不能只看函数是否返回 success，
        还必须确认关键文件真实落盘。
        否则 Gradio 页面刷新时会出现“成功但文件不存在”的假成功状态。

    必须存在的输出包括：
    - graph_trace
    - graph_state_final
    - node_decision_table
    - langgraph_summary
    - report
    - qa_check
    - manifest
    - literature_query_plan_jsonl
    - literature_query_plan_tsv
    """

    required_keys = [
        "graph_trace",
        "graph_state_final",
        "node_decision_table",
        "langgraph_summary",
        "report",
        "qa_check",
        "manifest",
        "literature_query_plan_jsonl",
        "literature_query_plan_tsv",
    ]

    # 收集缺失的关键输出。
    missing = [
        f"{key}: {outputs.get(key, '')}"
        for key in required_keys
        if not outputs.get(key) or not Path(outputs[key]).exists()
    ]

    if missing:
        raise FileNotFoundError(
            "LangGraph workflow output path(s) missing: " + "; ".join(missing)
        )


def _llm_reviewer_metadata(final_state: object) -> dict[str, object]:
    """从 final_state 中提取 LLM Reviewer 元数据。

    Args:
        final_state:
            LangGraph workflow 最终 state。

    Returns:
        LLM Reviewer metadata 字典。

    该函数按多个位置尝试读取 metadata：

    1. final_state["llm_reviewer_metadata"]
       这是最直接的位置。

    2. final_state["agent_context"]["_llm_reviewer_metadata"]
       某些节点可能把 LLM reviewer 信息写入 agent_context。

    3. final_state["graph_trace"] 中 reviewer_agent_node 的记录
       如果前两个位置没有，则从 trace 里恢复关键信息。

    记录字段通常包括：
    - llm_reviewer_enabled
    - llm_used
    - fallback_used
    - model
    - guard_passed
    - fallback_reason
    - guard_reasons

    这些信息用于：
    - manifest.json；
    - Gradio LLM Reviewer Status；
    - 项目边界说明。
    """

    # final_state 必须是 dict，否则无法读取 metadata。
    if not isinstance(final_state, dict):
        return {}

    # 1. 优先读取直接字段。
    direct = final_state.get("llm_reviewer_metadata")
    if isinstance(direct, dict):
        return direct

    # 2. 尝试从 agent_context 中读取。
    agent_context = final_state.get("agent_context")
    if isinstance(agent_context, dict):
        metadata = agent_context.get("_llm_reviewer_metadata")
        if isinstance(metadata, dict):
            return metadata

    # 3. 尝试从 graph_trace 的 reviewer_agent_node 记录中提取。
    for row in final_state.get("graph_trace", []):
        if isinstance(row, dict) and row.get("node_name") == "reviewer_agent_node":
            return {
                key: row.get(key)
                for key in [
                    "llm_reviewer_enabled",
                    "llm_used",
                    "fallback_used",
                    "model",
                    "guard_passed",
                    "fallback_reason",
                    "guard_reasons",
                ]
                if key in row
            }

    return {}