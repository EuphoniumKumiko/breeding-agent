"""Workflow orchestration for flavonoid marker evidence aggregation.

本文件是“谷子黄酮候选标记推荐”规则版聚合流程的 workflow 调度层。

它负责把已经生成好的多组学 evidence 交给 FlavonoidCentralHost，
再由 agent 层完成候选标记推荐、QA 检查和报告生成。

整体调用链可以理解为：

Gradio UI / CLI
        ↓
FlavonoidMarkerAggregationConfig
        ↓
run_flavonoid_marker_aggregation_task()
        ↓
run_flavonoid_marker_aggregation()
        ↓
FlavonoidCentralHost(...).run()
        ↓
generate_flavonoid_marker_report_from_agent_result()
        ↓
qa_check.json / manifest.json / flavonoid_marker_report.md

当前 workflow 的主要职责：

1. 接收 evidence_dir、outdir、target_genes、variant_calling_dir；
2. 调用 FlavonoidCentralHost 运行规则化 agent 聚合逻辑；
3. 收集 agent_result 中的 warnings、candidate_file、qa_result 等信息；
4. 生成 候选标记表、最终 Markdown 报告 flavonoid_marker_report.md；
5. 写出 qa_check.json；
6. 写出 manifest.json；
7. 向 CLI / Gradio 返回最终报告路径。

注意：
这个 workflow 本身不直接做 SNP/InDel calling，
也不直接设计 KASP/CAPS 标记。
它只是读取已有 evidence 和可选 variant calling 结果，
然后给出候选标记推荐和边界受控的报告，
输出仍应表述为 preliminary candidate marker recommendation
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.agents.flavonoid_central_host import (
    FlavonoidCentralHost,
)
from breeding_agent.reports.flavonoid_marker_report import (
    generate_flavonoid_marker_report_from_agent_result,
)


# 默认输出目录。
#
# 如果 CLI / Gradio 没有显式传入 outdir，
# 黄酮候选标记推荐结果会默认写入：
#
# outputs/flavonoid_marker_from_package/
#
# 典型输出包括：
# - reports/flavonoid_marker_report.md
# - integration/flavonoid_marker_candidates.tsv
# - logs/qa_check.json
# - manifest.json
DEFAULT_OUTDIR = "outputs/flavonoid_marker_from_package"


@dataclass(frozen=True)
class FlavonoidMarkerAggregationConfig:
    """谷子黄酮候选标记聚合 workflow 配置。

    这个 dataclass 用于统一承载黄酮候选标记推荐流程所需的输入参数。

    frozen=True 表示配置对象创建后不可修改，
    可以避免 workflow 运行过程中被意外改写。

    Attributes:
        evidence_dir:
            evidence 文件所在目录。

            通常由 create_evidence_from_package() 生成，例如：
            outputs/flavonoid_marker_from_package/evidence

            该目录中通常包含：
            - transcriptome_evidence.tsv
            - metabolome_evidence.tsv
            - annotation_evidence.tsv
            - genome_variant_evidence.tsv
            - literature_evidence.tsv

        outdir:
            输出目录。

            默认是：
            outputs/flavonoid_marker_from_package

            报告、候选表、QA 文件和 manifest 都写在这里。

        target_genes:
            可选的目标基因列表。

            如果为 None，则 FlavonoidCentralHost 内部通常会使用默认目标基因，
            例如：
            - Si9g04210.1
            - Si5g31340.1
            - Si9g34380.1

        variant_calling_dir:
            可选的候选区域变异检测输出目录。

            如果提供且目录有效，agent 层可以读取：
            - candidate_variants.tsv
            - snp_candidates.tsv
            - indel_candidates.tsv
            - kasp_candidate_sites.tsv
            - caps_candidate_sites.tsv

            如果为 None，则保持不接入 variant calling evidence 的原流程。

            注意：
            即使接入该目录，也只能说明存在候选 SNP/InDel/KASP/CAPS 初筛证据，
            不能声称已经完成最终 KASP/CAPS 标记开发。
    """

    evidence_dir: Path
    outdir: Path = Path(DEFAULT_OUTDIR)
    target_genes: list[str] | None = None
    variant_calling_dir: Path | None = None


def run_flavonoid_marker_aggregation(
    config: FlavonoidMarkerAggregationConfig,
) -> Path:
    """运行黄酮候选标记 evidence 聚合、报告生成、QA 和 manifest 写出。

    这是本文件的核心 workflow 函数。

    主流程：

    1. 初始化开始时间、输出目录、QA 文件路径和 manifest 路径；
    2. 构建 manifest 初始记录，状态为 running；
    3. 打印 workflow 基本参数；
    4. 创建 outdir 和 logs 目录；
    5. 调用 FlavonoidCentralHost(...).run() 执行 agent 聚合；
    6. 收集 agent_result 中的 warnings；
    7. 根据 agent_result 生成最终 Markdown 报告；
    8. 将 qa_result 写入 qa_check.json；
    9. 成功时更新 manifest 中的 outputs、warnings、agent_layer 等字段；
    10. 失败时记录 error_message；
    11. finally 中无论成功失败都写出 manifest.json。

    Args:
        config:
            黄酮候选标记聚合 workflow 配置。

    Returns:
        report_file:
            最终 Markdown 报告路径，通常是：
            outdir / "reports" / "flavonoid_marker_report.md"

    Raises:
        Exception:
            如果 evidence 读取、agent 聚合、报告生成或 QA 写出失败，
            会记录 manifest 后继续向上抛出异常。
            这样 CLI / Gradio 能够感知失败并展示错误信息。
    """

    # 记录 workflow 开始时间。
    # 使用 UTC 时间，便于跨机器、跨环境追踪。
    start_time = _utc_now()

    # 输出目录和 evidence 输入目录。
    outdir = config.outdir
    evidence_dir = config.evidence_dir

    # QA 检查结果输出路径。
    # qa_check.json 用于记录最终报告是否满足硬性要求，
    # 例如是否包含目标基因、关键词、DOI、marker 类型和边界声明等。
    qa_file = outdir / "logs" / "qa_check.json"

    # manifest.json 记录本次 workflow 的完整运行元数据。
    manifest_file = outdir / "manifest.json"

    # 初始化 manifest。
    #
    # status 初始为 running；
    # 成功后改为 success；
    # 失败后改为 failed。
    manifest: dict[str, object] = {
        "task_name": "flavonoid_marker_aggregation",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "evidence_dir": str(evidence_dir),
        "outdir": str(outdir),

        # variant_calling_dir 是可选输入。
        # 如果接入候选区域变异检测结果，这里记录路径；
        # 如果不接入，则为 None。
        "variant_calling_dir": (
            str(config.variant_calling_dir) if config.variant_calling_dir else None
        ),

        "outputs": {},
        "warnings": [],
        "error_message": None,
    }

    # 打印 workflow 基本信息，方便 CLI 或 Gradio 后端日志查看。
    print("[flavonoid-markers] Starting aggregation workflow", flush=True)
    print(f"[flavonoid-markers] evidence-dir: {evidence_dir}", flush=True)
    print(f"[flavonoid-markers] outdir: {outdir}", flush=True)

    # 创建输出目录和 logs 目录。
    outdir.mkdir(parents=True, exist_ok=True)
    qa_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # -----------------------------
        # 1. 运行 CentralHost agent 聚合层
        # -----------------------------
        #
        # FlavonoidCentralHost 是当前规则版黄酮候选标记推荐的核心 agent 调度入口。
        #
        # 它通常负责：
        # - 读取 evidence_dir 中的多组学 evidence；
        # - 围绕 target_genes 聚合转录组、代谢组、注释、文献和变异证据；
        # - 调用 LiteratureAgent / MarkerRecommendationAgent /
        #   ValidationAgent / ReviewerAgent / FinalQAAgent 等规则化 agent；
        # - 生成候选标记表；
        # - 生成 QA 结果；
        # - 返回 agent_result。
        #
        # 当前 workflow 不直接参与这些业务判断，只负责调度和记录结果。
        agent_result = FlavonoidCentralHost(
            evidence_dir=evidence_dir,
            outdir=outdir,
            target_genes=config.target_genes,
            variant_calling_dir=config.variant_calling_dir,
        ).run()

        # -----------------------------
        # 2. 收集并打印 warnings
        # -----------------------------
        #
        # agent_result["warnings"] 可能包括：
        # - 某些 evidence 文件缺失；
        # - variant_calling_dir 不存在；
        # - 某些目标基因缺少证据；
        # - 某些结果只能作为 preliminary evidence。
        warnings = [str(warning) for warning in agent_result["warnings"]]

        for warning in warnings:
            print(f"[flavonoid-markers:warning] {warning}", flush=True)

        # -----------------------------
        # 3. 生成最终 Markdown 报告
        # -----------------------------
        #
        # 报告生成函数会读取 agent_result 中的候选标记、证据摘要、
        # 文献证据、验证建议、reviewer 结论和 QA 边界信息，
        # 然后渲染为 flavonoid_marker_report.md。
        report_file = generate_flavonoid_marker_report_from_agent_result(
            outdir=outdir,
            agent_result=agent_result,
        )

        # -----------------------------
        # 4. 写出 QA 检查结果
        # -----------------------------
        #
        # qa_result 通常来自 FinalQAAgent 或类似 QA 层。
        # 它用于检查最终输出是否满足项目硬性要求。
        #
        # 例如：
        # - 是否包含 Si9g04210.1 / Si5g31340.1 / Si9g34380.1；
        # - 是否包含 “群体”；
        # - 是否包含 DOI；
        # - 是否包含 SNP/InDel/KASP/CAPS；
        # - 是否避免过度声称最终标记开发完成。
        qa_result = agent_result["qa_result"]
        _write_json(qa_file, qa_result)

        # -----------------------------
        # 5. 更新 manifest 成功状态
        # -----------------------------
        manifest["status"] = "success"
        manifest["warnings"] = warnings

        # outputs 记录本次流程生成的关键文件。
        manifest["outputs"] = {
            "candidate_table": str(agent_result["candidate_file"]),
            "report": str(report_file),
            "qa_check": str(qa_file),
            "manifest": str(manifest_file),
        }

        # agent_layer 记录本次使用的 agent 层信息。
        # 例如是否使用规则 agent、有哪些 agent 节点、版本或模式等。
        manifest["agent_layer"] = agent_result["agent_layer"]

        # 记录 agent 层实际使用或识别到的 variant_calling_dir。
        # 这有助于确认本次报告是否接入了候选变异检测 evidence。
        manifest["variant_calling_dir"] = agent_result.get("variant_calling_dir")

        # 打印关键输出路径和 QA 状态，便于命令行查看。
        print(
            f"[flavonoid-markers] candidates: {agent_result['candidate_file']}",
            flush=True,
        )
        print(f"[flavonoid-markers] report: {report_file}", flush=True)
        print(f"[flavonoid-markers] qa_check: {qa_file}", flush=True)
        print(
            f"[flavonoid-markers] qa passed: {qa_result.get('passed')}",
            flush=True,
        )

        # 返回最终报告路径。
        return report_file

    except Exception as exc:
        # -----------------------------
        # 失败处理
        # -----------------------------
        #
        # 包括但不限于：
        # - evidence_dir 不存在；
        # - evidence 文件格式错误；
        # - CentralHost 聚合失败；
        # - 报告生成失败；
        # - qa_check 写出失败。
        #
        # 这里只记录 manifest，异常继续向上抛出，
        # 让 CLI / Gradio / 测试框架能够显示失败信息。
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise

    finally:
        # -----------------------------
        # 收尾逻辑
        # -----------------------------
        #
        # 无论成功还是失败，都会：
        # 1. 写入 end_time；
        # 2. 写出 manifest.json。
        #
        # 这样即使中途失败，也能留下运行记录，便于排查。
        manifest["end_time"] = _utc_now()
        _write_json(manifest_file, manifest)


def run_flavonoid_marker_aggregation_task(
    config: FlavonoidMarkerAggregationConfig,
) -> Path:
    """CLI、Gradio 和未来 UI 共用的公开 workflow 入口。

    当前函数只是简单调用 run_flavonoid_marker_aggregation(config)。

    保留这一层包装的好处：

    1. 对外暴露稳定入口名；
    2. CLI、Gradio、测试代码可以统一调用；
    3. 后续如果要增加额外参数转换、前置校验或日志逻辑，
       可以在这里扩展，而不用改动核心 workflow 函数。
    """

    return run_flavonoid_marker_aggregation(config)


def _utc_now() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。

    用于 manifest.json 中的 start_time 和 end_time。

    使用 UTC 的好处：

    - 避免本地时区差异造成记录混乱；
    - 方便在不同服务器、虚拟机、本地环境之间对齐日志；
    - 更适合作为可追溯运行记录。
    """

    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """将字典写出为 JSON 文件。

    Args:
        path:
            输出 JSON 文件路径。

        payload:
            需要写出的字典对象。

    当前主要用于写出：
    - qa_check.json
    - manifest.json

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