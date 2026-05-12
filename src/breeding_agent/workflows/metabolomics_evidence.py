"""Workflow for package-derived metabolomics evidence analysis.

本文件是代谢组证据分析模块的“工作流调度层”。

它本身不直接实现代谢组统计分析算法，而是负责把下游模块串起来：

1. 接收 dataset_dir 和 outdir 配置；
2. 调用 build_metabolomics_evidence() 从数据包中提取/构建代谢组证据；
3. 调用 generate_metabolomics_report() 生成代谢组分析报告；
4. 记录 manifest.json，用于追踪本次运行状态、输入、输出、警告和错误信息；
5. 向 Gradio UI、测试用例或其他上层流程提供统一入口。

在当前项目架构中，这个文件对应：
Gradio 页面 / 测试入口
    ↓
MetabolomicsEvidenceConfig
    ↓
run_metabolomics_evidence_task()
    ↓
run_metabolomics_evidence_analysis()
    ↓
modules.metabolomics.metabolomics_evidence.build_metabolomics_evidence()
    ↓
reports.metabolomics_report.generate_metabolomics_report()
    ↓
outputs/gradio_metabolomics_run/metabolomics/
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.modules.metabolomics.metabolomics_evidence import (
    build_metabolomics_evidence,
)
from breeding_agent.reports.metabolomics_report import generate_metabolomics_report


# 默认输出目录。
# 如果 Gradio 或测试代码没有显式传入 outdir，
# 代谢组分析结果会默认写入 outputs/gradio_metabolomics_run。
DEFAULT_OUTDIR = "outputs/gradio_metabolomics_run"


@dataclass(frozen=True)
class MetabolomicsEvidenceConfig:
    """代谢组证据分析工作流配置。

    这个 dataclass 用来统一承载代谢组模块运行所需的输入参数。

    frozen=True 表示配置对象创建后不可修改，
    可以避免工作流运行过程中配置被意外改写。

    Attributes:
        dataset_dir:
            输入数据包目录。

            当前项目中通常指类似：
            data/private/flavonoid_marker_mini_5genes_50kb

            该目录下可能包含：
            - metabolome/metabolome_raw_3372.tsv
            - metabolome/target_gene_metabolite_network_edges.tsv
            - metabolome/target_gene_spls_coefficients.tsv
            - annotations/target_gene_evidence_summary.tsv
            等数据包文件。

        outdir:
            输出根目录。

            实际代谢组模块输出会进一步写入：
            outdir / "metabolomics"

            例如默认情况下为：
            outputs/gradio_metabolomics_run/metabolomics
    """

    dataset_dir: Path
    outdir: Path = Path(DEFAULT_OUTDIR)


def run_metabolomics_evidence_analysis(
    config: MetabolomicsEvidenceConfig,
) -> dict[str, object]:
    """运行代谢组证据分析，并写出结果文件。

    这是本文件的核心工作流函数。

    主流程：
    1. 初始化运行时间、输出目录和 manifest.json 路径；
    2. 创建 manifest 初始记录，状态为 running；
    3. 调用 build_metabolomics_evidence() 构建代谢组证据表；
    4. 调用 generate_metabolomics_report() 生成 Markdown 报告；
    5. 将报告路径和 manifest 路径写入 result["outputs"]；
    6. 成功时更新 manifest 状态、输出、警告和行数统计；
    7. 失败时记录错误信息并继续向上抛出异常；
    8. 无论成功或失败，finally 中都会写出 manifest.json。

    Args:
        config:
            代谢组证据分析配置，包含 dataset_dir 和 outdir。

    Returns:
        result:
            build_metabolomics_evidence() 返回的结果字典，并补充 report 和 manifest 输出路径。

            通常包含：
            - outputs: 主要输出文件路径；
            - warnings: 运行过程中的警告；
            - row_counts: 各输出表的行数统计。

    Raises:
        Exception:
            如果构建代谢组证据或生成报告失败，记录 manifest 后继续抛出。
            这样 Gradio UI 或测试代码可以感知任务失败。
    """

    # 记录任务开始时间。
    # 使用 UTC 时间可以避免不同机器、不同时区运行时产生歧义。
    start_time = _utc_now()

    # 实际输出目录。
    # 注意：config.outdir 是模块输出根目录，
    # 代谢组专属结果会写入其下的 metabolomics 子目录。
    output_dir = config.outdir / "metabolomics"

    # manifest.json 用于记录本次运行的完整元信息。
    manifest_file = output_dir / "manifest.json"

    # 初始化 manifest。
    # status 先标记为 running；
    # 成功后改为 success；
    # 失败后改为 failed。
    manifest: dict[str, object] = {
        "task_name": "metabolomics_evidence",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "dataset_dir": str(config.dataset_dir),
        "outdir": str(config.outdir),
        "outputs": {},
        "warnings": [],
        "error_message": None,
    }

    try:
        # 构建代谢组证据。
        #
        # 该函数是真正负责读取数据包、解析代谢组相关文件、
        # 生成候选代谢物表、网络边表、sPLS 系数表等结果的模块。
        #
        # 本 workflow 只负责调用它，并把结果继续交给报告生成模块。
        result = build_metabolomics_evidence(
            dataset_dir=config.dataset_dir,
            output_dir=output_dir,
        )

        # 基于 build_metabolomics_evidence() 的分析结果生成 Markdown 报告。
        #
        # report_file 通常类似：
        # outputs/gradio_metabolomics_run/metabolomics/metabolomics_report.md
        report_file = generate_metabolomics_report(
            output_dir=output_dir,
            analysis_result=result,
        )

        # 将报告路径写入 result["outputs"]。
        #
        # 这里使用 type: ignore[index] 的原因是：
        # result 的静态类型是 dict[str, object]，
        # 类型检查器无法确定 result["outputs"] 一定是可下标赋值的 dict。
        #
        # 但根据 build_metabolomics_evidence() 的约定，
        # result["outputs"] 应该是一个字典。
        result["outputs"]["report"] = str(report_file)  # type: ignore[index]

        # 同样把 manifest.json 路径也写入 outputs，
        # 方便 Gradio UI 或下游流程直接展示/读取。
        result["outputs"]["manifest"] = str(manifest_file)  # type: ignore[index]

        # 所有步骤成功后，更新 manifest 状态。
        manifest["status"] = "success"

        # 将分析模块返回的 warnings、outputs、row_counts 写入 manifest。
        # 这样用户可以通过 manifest.json 追踪：
        # - 哪些文件被生成；
        # - 有哪些警告；
        # - 每个结果表有多少行。
        manifest["warnings"] = result["warnings"]
        manifest["outputs"] = result["outputs"]
        manifest["row_counts"] = result["row_counts"]

        return result

    except Exception as exc:
        # 如果任意步骤失败，记录失败状态和错误信息。
        #
        # 注意这里不会吞掉异常，而是继续 raise。
        # 这样上层调用者，例如 Gradio UI，可以显示完整错误信息。
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise

    finally:
        # finally 块无论成功还是失败都会执行。
        #
        # 这保证了即使中途失败，也会写出 manifest.json，
        # 方便后续排查到底失败在哪一步。
        manifest["end_time"] = _utc_now()
        _write_json(manifest_file, manifest)


def run_metabolomics_evidence_task(
    config: MetabolomicsEvidenceConfig,
) -> dict[str, object]:
    """测试和 UI 共用的公开入口。

    当前这个函数只是简单调用 run_metabolomics_evidence_analysis(config)。

    保留这一层包装的好处是：
    1. 对外提供稳定入口名；
    2. Gradio、测试代码或未来 CLI 都可以统一调用它；
    3. 后续如果需要增加 UI 专属逻辑、参数转换或前置校验，
       可以在这里扩展，而不需要改动核心分析函数。
    """

    return run_metabolomics_evidence_analysis(config)


def _utc_now() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。

    manifest.json 中的 start_time 和 end_time 都使用这个函数生成。

    使用 UTC 的好处：
    - 便于跨机器、跨环境比较运行时间；
    - 避免本地时区差异造成记录混乱；
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

    该函数会自动创建父目录，因此即使 output_dir 尚不存在，
    也可以正常写出 manifest.json。
    """

    # 确保输出目录存在。
    # parents=True 表示递归创建父目录；
    # exist_ok=True 表示目录已存在时不报错。
    path.parent.mkdir(parents=True, exist_ok=True)

    # ensure_ascii=False 用于保留中文字符，
    # indent=2 让 JSON 文件更易读。
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")