"""Workflow for package-derived genomics region analysis.

本文件是基因组候选区域分析模块的“工作流调度层”。

它本身不直接解析 genome.fa、genome.gff 或注释文件，
而是负责调用下游 modules 层的真实业务函数，并组织输出结果。

整体流程可以理解为：

Gradio UI / 测试代码
        ↓
GenomicsRegionConfig
        ↓
run_genomics_region_task()
        ↓
run_genomics_region_analysis()
        ↓
modules.genomics.genomics_region.build_genomics_region_analysis()
        ↓
reports.genomics_report.generate_genomics_report()
        ↓
outputs/gradio_genomics_run/genomics/

当前模块主要职责：

1. 接收 dataset_dir 和 outdir；
2. 调用 build_genomics_region_analysis() 生成基因组候选区域相关表；
3. 调用 generate_genomics_report() 生成 Markdown 报告；
4. 写出 manifest.json，记录输入、输出、运行状态、警告和错误；
5. 为 Gradio 页面和测试代码提供统一入口。

注意：
当前 genomics_region 模块主要是“候选区域 / 注释 / marker readiness 整理”，
并不等同于完整的 WGS/GBS 群体变异检测，也不会直接产出最终 KASP/CAPS 标记。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.modules.genomics.genomics_region import (
    build_genomics_region_analysis,
)
from breeding_agent.reports.genomics_report import generate_genomics_report


# 默认输出目录。
#
# 如果 Gradio 或测试代码没有显式传入 outdir，
# 基因组候选区域分析结果会默认写入：
#
# outputs/gradio_genomics_run/genomics/
DEFAULT_OUTDIR = "outputs/gradio_genomics_run"


@dataclass(frozen=True)
class GenomicsRegionConfig:
    """基因组候选区域分析工作流配置。

    这个 dataclass 用于统一承载 genomics region workflow 的输入参数。

    frozen=True 表示配置对象创建后不可修改，
    可以避免工作流执行过程中配置被意外改写。

    Attributes:
        dataset_dir:
            输入数据包目录。

            当前项目中通常指：
            data/private/flavonoid_marker_mini_5genes_50kb

            该目录下可能包含：
            - genome.fa
            - genome.gff
            - genome.original_coords.gff
            - genome.bam_compatible.fa.gz
            - annotations/local_region_emapper_annotations.tsv
            - annotations/target_gene_emapper_annotations.tsv
            - annotations/target_gene_evidence_summary.tsv
            - target_genes.tsv
            等文件。

        outdir:
            输出根目录。

            实际 genomics region 模块输出会进一步写入：
            outdir / "genomics"

            例如默认情况下为：
            outputs/gradio_genomics_run/genomics
    """

    dataset_dir: Path
    outdir: Path = Path(DEFAULT_OUTDIR)


def run_genomics_region_analysis(
    config: GenomicsRegionConfig,
) -> dict[str, object]:
    """运行基因组候选区域分析，并写出结果文件。

    这是本文件的核心 workflow 函数。

    主流程：

    1. 初始化运行时间、输出目录和 manifest.json 路径；
    2. 创建 manifest 初始记录，状态为 running；
    3. 调用 build_genomics_region_analysis() 构建候选区域分析结果；
    4. 调用 generate_genomics_report() 生成 Markdown 报告；
    5. 将 report 和 manifest 路径补充到 result["outputs"]；
    6. 成功时把状态、输出、警告、行数统计写入 manifest；
    7. 失败时记录错误信息，并继续向上抛出异常；
    8. 无论成功或失败，都在 finally 中写出 manifest.json。

    Args:
        config:
            基因组候选区域分析配置，包含 dataset_dir 和 outdir。

    Returns:
        result:
            build_genomics_region_analysis() 返回的结构化结果字典，
            并补充 report 和 manifest 输出路径。

            通常包含：
            - outputs: 输出文件路径；
            - warnings: 运行过程中的警告；
            - row_counts: 输出表行数统计；
            - target_genes: 目标基因列表；
            - regions / annotations / marker readiness 相关摘要。

    Raises:
        Exception:
            如果候选区域分析或报告生成失败，会记录 manifest 后继续抛出。
            这样 Gradio UI 或测试代码可以捕获并展示失败原因。
    """

    # 记录任务开始时间。
    # 使用 UTC 时间可以避免本地时区差异，便于跨机器追踪运行记录。
    start_time = _utc_now()

    # 实际输出目录。
    #
    # config.outdir 是模块输出根目录，
    # genomics region 专属结果统一放在 outdir/genomics 下。
    output_dir = config.outdir / "genomics"

    # manifest.json 用于记录本次运行的完整元信息。
    manifest_file = output_dir / "manifest.json"

    # 初始化 manifest。
    #
    # status 初始为 running；
    # 成功后改为 success；
    # 失败后改为 failed。
    manifest: dict[str, object] = {
        "task_name": "genomics_region",
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
        # 执行真正的基因组候选区域分析。
        #
        # build_genomics_region_analysis() 属于 modules 层，
        # 负责读取数据包中的基因组/注释相关文件，
        # 生成 target_gene_regions.tsv、annotation_summary.tsv、
        # marker_readiness.tsv 等结构化输出。
        #
        # workflow 层只负责调用它，并管理输出目录和运行记录。
        result = build_genomics_region_analysis(
            dataset_dir=config.dataset_dir,
            output_dir=output_dir,
        )

        # 基于分析结果生成 Markdown 报告。
        #
        # report_file 通常类似：
        # outputs/gradio_genomics_run/genomics/genomics_report.md
        report_file = generate_genomics_report(
            output_dir=output_dir,
            analysis_result=result,
        )

        # 将报告路径写入 result["outputs"]。
        #
        # type: ignore[index] 的原因：
        # result 的静态类型是 dict[str, object]，
        # 类型检查器无法确定 result["outputs"] 一定是可下标赋值的 dict。
        # 但根据 build_genomics_region_analysis() 的返回约定，
        # result["outputs"] 应该是一个字典。
        result["outputs"]["report"] = str(report_file)  # type: ignore[index]

        # 同样把 manifest.json 路径也写入 outputs，
        # 方便 Gradio UI 或下游流程直接读取和展示。
        result["outputs"]["manifest"] = str(manifest_file)  # type: ignore[index]

        # 所有步骤成功后，更新 manifest 状态。
        manifest["status"] = "success"

        # 将分析结果中的 warnings、outputs、row_counts 写入 manifest。
        #
        # 这样后续可以通过 manifest.json 追踪：
        # - 哪些文件被生成；
        # - 是否有输入缺失或其他警告；
        # - 每张结果表有多少行。
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
        # 方便后续排查失败发生在哪一步。
        manifest["end_time"] = _utc_now()
        _write_json(manifest_file, manifest)


def run_genomics_region_task(config: GenomicsRegionConfig) -> dict[str, object]:
    """测试和 UI 共用的公开入口。

    当前这个函数只是简单调用 run_genomics_region_analysis(config)。

    保留这一层包装的好处：

    1. 对外提供稳定入口名；
    2. Gradio、测试代码或未来 CLI 可以统一调用；
    3. 后续如果需要增加 UI 专属参数转换、前置校验或日志逻辑，
       可以在这里扩展，而不用修改核心分析函数。
    """

    return run_genomics_region_analysis(config)


def _utc_now() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。

    manifest.json 中的 start_time 和 end_time 都使用这个函数生成。

    使用 UTC 的好处：

    - 避免本地时区差异造成记录混乱；
    - 便于跨机器、跨环境对比运行时间；
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
    #
    # parents=True 表示递归创建父目录；
    # exist_ok=True 表示目录已存在时不报错。
    path.parent.mkdir(parents=True, exist_ok=True)

    # ensure_ascii=False 用于保留中文字符；
    # indent=2 让 manifest.json 更易读；
    # 末尾额外写入换行，符合常见文本文件习惯。
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")