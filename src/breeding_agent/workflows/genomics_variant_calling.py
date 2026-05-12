"""Workflow orchestration for candidate-region genomics variant calling.

本文件是“候选区域基因组变异检测”模块的 workflow 调度层。

它负责把 variant calling 相关的多个步骤串联起来：

1. 解析默认输入路径，输入数据包：
   - BAM 目录；
   - 参考基因组 FASTA；
   - 候选区域 BED；
   - GFF 注释文件。

2. 检查运行环境和输入文件：
   - 检查 samtools / bcftools 等外部工具；
   - 检查 BAM、FASTA、regions.bed 是否存在；
   - 检查 BAM 索引和参考基因组索引。

3. 调用 modules.genomics.variant_calling 中的底层函数：
   - ensure_reference_index()
   - ensure_bam_indexes()
   - call_candidate_region_variants()
   - build_variant_tables_from_vcf()

4. 在候选区域内执行 variant calling，生成结构化输出：
   - raw / filtered VCF；
   - candidate_variants.tsv；
   - snp_candidates.tsv；
   - indel_candidates.tsv；
   - kasp_candidate_sites.tsv；
   - caps_candidate_sites.tsv；
   - genomics_variant_calling_report.md；
   - manifest.json；
   - run.log。

5. 记录可追溯信息：
   - 输入路径；
   - 使用的外部工具；
   - 执行过的命令；
   - 输出文件；
   - 变异数量统计；
   - 覆盖到的目标基因；
   - 错误信息。

注意：
当前模块是候选区域 variant calling，不等同于完整 WGS/GBS 群体变异检测。
它产出的 KASP/CAPS 表也只是 preliminary screening，不是最终引物设计或酶切方案。
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from breeding_agent.modules.genomics.variant_calling import (
    CommandResult,
    build_variant_tables_from_vcf,
    call_candidate_region_variants,
    ensure_bam_indexes,
    ensure_reference_index,
    require_tools,
    validate_variant_calling_inputs,
)
from breeding_agent.reports.genomics_variant_report import (
    generate_genomics_variant_report,
)


# 默认数据包目录。
#
# 该目录通常包含：
# - bam/
# - genome.fa
# - genome.bam_compatible.fa.gz
# - genome.gff
# - genome.original_coords.gff
# - regions/regions.bed
# - annotations/
#
# 当前默认值对应谷子黄酮候选标记 mini 数据包。
DEFAULT_DATASET_DIR = "data/private/flavonoid_marker_mini_5genes_50kb"

# 默认输出目录。
#
# 变异检测相关输出会写到该目录下的多个子目录中，例如：
# - outputs/genomics_variant_calling/variants/
# - outputs/genomics_variant_calling/tables/
# - outputs/genomics_variant_calling/logs/
# - outputs/genomics_variant_calling/reports/
DEFAULT_OUTDIR = "outputs/genomics_variant_calling"


@dataclass(frozen=True)
class GenomicsVariantCallingConfig:
    """候选区域变异检测 workflow 的配置对象。

    这个 dataclass 用于统一承载 variant calling 所需的路径参数。

    frozen=True 表示配置对象创建后不可修改，
    可以避免 workflow 运行过程中输入路径被意外改写。

    Attributes:
        dataset_dir:
            数据包根目录。

            如果用户没有单独指定 bam_dir、reference_fasta、
            regions_bed 或 gff，则会从 dataset_dir 下推导默认路径。

        bam_dir:
            BAM 文件目录。

            如果为 None，则默认使用：
            dataset_dir / "bam"

        reference_fasta:
            参考基因组 FASTA。

            如果为 None，则调用 _default_reference(dataset_dir) 自动选择：
            1. 优先使用 genome.bam_compatible.fa.gz；
            2. 如果不存在，则使用 genome.fa。

        regions_bed:
            候选区域 BED 文件。

            如果为 None，则默认使用：
            dataset_dir / "regions" / "regions.bed"

            该文件用于限制 variant calling 只在候选区域内进行，
            避免全基因组扫描造成不必要计算开销。

        gff:
            基因注释文件。

            如果为 None，则调用 _default_gff(dataset_dir) 自动选择：
            1. 优先使用 genome.original_coords.gff；
            2. 如果不存在，则使用 genome.gff。

            GFF 主要用于后续把变异位点关联到候选基因或候选区域。

        outdir:
            输出目录。

            默认是 outputs/genomics_variant_calling。
    """

    dataset_dir: Path = Path(DEFAULT_DATASET_DIR)
    bam_dir: Path | None = None
    reference_fasta: Path | None = None
    regions_bed: Path | None = None
    gff: Path | None = None
    outdir: Path = Path(DEFAULT_OUTDIR)


def run_genomics_variant_calling(
    config: GenomicsVariantCallingConfig,
) -> dict[str, object]:
    """运行候选区域 variant calling，并写出全部结果。

    这是本文件的核心 workflow 函数。

    主流程：

    1. 初始化运行时间、输出目录、日志路径和 manifest；
    2. 根据 config 和 dataset_dir 推导默认输入路径；
    3. 检查 samtools / bcftools 等依赖工具；
    4. 校验 BAM、FASTA、regions.bed 等输入；
    5. 确保参考基因组索引存在；
    6. 确保 BAM 索引存在；
    7. 调用候选区域 variant calling；
    8. 从 filtered VCF 构建候选变异表、SNP 表、InDel 表、KASP/CAPS 初筛表；
    9. 生成 Markdown 报告；
    10. 成功时写入 outputs、commands、counts、covered_target_genes；
    11. 失败时记录错误；
    12. finally 中无论成功失败都写出 run.log 和 manifest.json。

    Args:
        config:
            GenomicsVariantCallingConfig 配置对象。

    Returns:
        result:
            结构化运行结果字典，包含：
            - task_name
            - inputs
            - outputs
            - commands
            - warnings
            - counts
            - covered_target_genes

    Raises:
        subprocess.CalledProcessError:
            外部命令执行失败时抛出，例如 samtools / bcftools 返回非 0 状态码。

        Exception:
            输入校验、文件生成、表格构建或报告生成失败时抛出。
    """

    # 记录 workflow 开始时间。
    # 使用 UTC 时间有利于跨机器、跨环境追踪。
    start_time = _utc_now()

    # 展开用户目录。
    # 例如 ~/projects/... 会被转换为实际绝对路径。
    dataset_dir = config.dataset_dir.expanduser()
    outdir = config.outdir.expanduser()

    # variant calling 原始输出目录。
    # 通常用于存放 raw VCF、filtered VCF 等文件。
    variants_dir = outdir / "variants"

    # 表格输出目录。
    # 通常用于存放 candidate_variants.tsv、snp_candidates.tsv 等。
    tables_dir = outdir / "tables"

    # 日志目录。
    logs_dir = outdir / "logs"
    log_file = logs_dir / "run.log"

    # manifest.json 记录本次运行的完整元数据。
    manifest_file = outdir / "manifest.json"

    # commands 用于保存实际执行过的外部命令。
    # CommandResult 通常包含命令名称和渲染后的命令字符串。
    commands: list[CommandResult] = []

    # warnings 用于记录非致命警告。
    warnings: list[str] = []

    # -----------------------------
    # 1. 解析输入路径
    # -----------------------------

    # 如果用户没有显式指定 bam_dir，则默认使用 dataset_dir/bam。
    bam_dir = (config.bam_dir or dataset_dir / "bam").expanduser()

    # 如果用户显式指定 reference_fasta，则使用用户路径；
    # 否则从数据包中自动选择默认参考基因组。
    reference_fasta = (
        config.reference_fasta.expanduser()
        if config.reference_fasta
        else _default_reference(dataset_dir)
    )

    # 如果用户显式指定 regions_bed，则使用用户路径；
    # 否则默认读取 dataset_dir/regions/regions.bed。
    regions_bed = (
        config.regions_bed.expanduser()
        if config.regions_bed
        else dataset_dir / "regions" / "regions.bed"
    )

    # 如果用户显式指定 gff，则使用用户路径；
    # 否则从数据包中自动选择默认 GFF。
    gff = config.gff.expanduser() if config.gff else _default_gff(dataset_dir)

    # 记录所有解析后的输入路径。
    # 这些信息会写入 result 和 manifest，便于后续复现和排错。
    inputs = {
        "dataset_dir": str(dataset_dir),
        "bam_dir": str(bam_dir),
        "reference_fasta": str(reference_fasta),
        "regions_bed": str(regions_bed),
        "gff": str(gff),
    }

    # 初始化 manifest。
    # status 初始为 running；
    # 成功后改为 success；
    # 失败后改为 failed。
    manifest: dict[str, object] = {
        "task_name": "genomics_variant_calling",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "inputs": inputs,
        "outputs": {},
        "commands": [],
        "warnings": warnings,
        "error_message": None,
    }

    # 创建输出根目录和日志目录。
    outdir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 写入 workflow 开始日志。
    _append_log(log_file, f"[{start_time}] genomics variant calling started")

    try:
        # -----------------------------
        # 2. 检查外部工具
        # -----------------------------
        #
        # require_tools() 通常会检查 samtools、bcftools 等命令是否可用。
        # 如果缺失必要工具，会抛出异常。
        tools = require_tools()

        # 将工具检查结果写入 manifest。
        manifest["tools"] = tools

        # -----------------------------
        # 3. 校验输入文件
        # -----------------------------
        #
        # validate_variant_calling_inputs() 会检查：
        # - BAM 目录是否存在；
        # - 是否能找到 BAM 文件；
        # - reference_fasta 是否存在；
        # - regions_bed 是否存在；
        #
        # 返回值 bam_files 是后续要参与 variant calling 的 BAM 文件列表。
        bam_files = validate_variant_calling_inputs(
            bam_dir=bam_dir,
            reference_fasta=reference_fasta,
            regions_bed=regions_bed,
        )

        # -----------------------------
        # 4. 确保参考基因组索引存在
        # -----------------------------
        #
        # 对 samtools/bcftools 来说，FASTA 通常需要 .fai 索引。
        # 如果索引不存在，ensure_reference_index() 会调用外部命令生成。
        #
        # 执行过的命令会追加到 commands，并写入 run.log。
        ensure_reference_index(
            reference_fasta=reference_fasta,
            log_file=log_file,
            commands=commands,
        )

        # -----------------------------
        # 5. 确保 BAM 索引存在
        # -----------------------------
        #
        # BAM 通常需要 .bai 索引才能按区域快速读取。
        # 如果缺失索引，ensure_bam_indexes() 会调用 samtools index 生成。
        ensure_bam_indexes(
            bam_files=bam_files,
            log_file=log_file,
            commands=commands,
        )

        # -----------------------------
        # 6. 在候选区域内执行 variant calling
        # -----------------------------
        #
        # call_candidate_region_variants() 是核心变异检测步骤。
        # 它会基于：
        # - BAM 文件；
        # - 参考基因组；
        # - 候选区域 BED；
        # 调用 samtools/bcftools 等工具生成 VCF。
        #
        # 返回值 vcf_outputs 通常包含 raw_vcf、filtered_vcf 等路径。
        vcf_outputs = call_candidate_region_variants(
            bam_files=bam_files,
            reference_fasta=reference_fasta,
            regions_bed=regions_bed,
            variants_dir=variants_dir,
            log_file=log_file,
            commands=commands,
        )

        # -----------------------------
        # 7. 从 filtered VCF 构建候选变异表
        # -----------------------------
        #
        # build_variant_tables_from_vcf() 负责把 VCF 转换为更适合展示和下游使用的 TSV 表：
        # - candidate_variants.tsv
        # - snp_candidates.tsv
        # - indel_candidates.tsv
        # - kasp_candidate_sites.tsv
        # - caps_candidate_sites.tsv
        #
        # gff 用于将变异关联到基因或候选区域；
        # regions_bed 用于保留候选区域上下文。
        table_result = build_variant_tables_from_vcf(
            vcf_path=vcf_outputs["filtered_vcf"],
            tables_dir=tables_dir,
            gff=gff,
            regions_bed=regions_bed,
        )

        # -----------------------------
        # 8. 组装结构化 result
        # -----------------------------
        #
        # result 是 workflow 返回给 Gradio、CLI 或测试代码的结果。
        # 它比 manifest 更偏向“业务结果”，manifest 更偏向“运行记录”。
        result: dict[str, object] = {
            "task_name": "genomics_variant_calling",
            "inputs": inputs,
            "outputs": {
                # vcf_outputs 中的 Path 转为字符串，便于 JSON 序列化。
                **{key: str(value) for key, value in vcf_outputs.items()},

                # table_result["outputs"] 通常已经是字符串路径字典。
                **table_result["outputs"],  # type: ignore[arg-type]

                # 运行日志和 manifest 路径也放入 outputs，方便 UI 展示。
                "run_log": str(log_file),
                "manifest": str(manifest_file),
            },
            "commands": [
                {"name": command.name, "command": command.rendered}
                for command in commands
            ],
            "warnings": warnings,

            # counts 记录变异数量统计。
            # 例如 candidate_variants、snps、indels、pass_variants、lowqual_variants 等。
            "counts": table_result["counts"],

            # covered_target_genes 记录当前变异结果覆盖到了哪些目标基因。
            "covered_target_genes": table_result["covered_target_genes"],
        }

        # -----------------------------
        # 9. 生成 Markdown 报告
        # -----------------------------
        #
        # 报告会基于 result 中的 counts、outputs、covered_target_genes 等信息生成。
        report_file = generate_genomics_variant_report(outdir=outdir, result=result)

        # 将报告路径补充进 result["outputs"]。
        result["outputs"]["report"] = str(report_file)  # type: ignore[index]

        # -----------------------------
        # 10. 更新 manifest 成功状态
        # -----------------------------
        manifest["status"] = "success"
        manifest["outputs"] = result["outputs"]
        manifest["commands"] = result["commands"]
        manifest["counts"] = result["counts"]
        manifest["covered_target_genes"] = result["covered_target_genes"]

        return result

    except subprocess.CalledProcessError as exc:
        # -----------------------------
        # 外部命令失败处理
        # -----------------------------
        #
        # 当 samtools / bcftools 等外部命令返回非 0 状态码时，
        # 底层函数通常会抛出 subprocess.CalledProcessError。
        #
        # 这里记录：
        # - workflow 状态 failed；
        # - 已执行命令；
        # - 失败命令和退出码。
        manifest["status"] = "failed"
        manifest["commands"] = [
            {"name": command.name, "command": command.rendered}
            for command in commands
        ]
        manifest["error_message"] = (
            f"Command failed with exit code {exc.returncode}: {' '.join(exc.cmd)}"
        )
        raise

    except Exception as exc:
        # -----------------------------
        # 其他异常处理
        # -----------------------------
        #
        # 包括：
        # - 输入文件缺失；
        # - 工具缺失；
        # - VCF 表格解析失败；
        # - 报告生成失败；
        # - 其他 Python 层错误。
        #
        # 记录错误信息后继续向上抛出，
        # 让 CLI、Gradio 或测试框架可以感知失败。
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise

    finally:
        # -----------------------------
        # 收尾逻辑：无论成功或失败都会执行
        # -----------------------------
        #
        # 1. 记录结束时间；
        # 2. 向 run.log 写入结束状态；
        # 3. 写出 manifest.json。
        #
        # 这样即使中途失败，也能留下可追溯记录。
        end_time = _utc_now()
        manifest["end_time"] = end_time
        _append_log(log_file, f"[{end_time}] workflow ended: {manifest['status']}")
        _write_json(manifest_file, manifest)


def run_genomics_variant_calling_task(
    config: GenomicsVariantCallingConfig,
) -> dict[str, object]:
    """CLI、Gradio 和测试代码共用的公开 workflow 入口。

    当前函数只是简单调用 run_genomics_variant_calling(config)。

    保留这一层包装的好处：

    1. 对外暴露稳定的函数名；
    2. UI、CLI、测试可以统一调用；
    3. 后续如果要增加额外参数转换、日志或前置检查，
       可以在这里扩展，而不用改动核心 workflow 函数。
    """

    return run_genomics_variant_calling(config)


def _default_reference(dataset_dir: Path) -> Path:
    """根据数据包内容选择默认参考基因组 FASTA。

    优先级：

    1. 如果存在 genome.bam_compatible.fa.gz，则优先使用它；
    2. 否则使用 genome.fa。

    为什么优先使用 genome.bam_compatible.fa.gz：

    - BAM 文件比对时使用的参考序列名称和坐标系统必须与 FASTA 一致；
    - 如果数据包提供了 bam_compatible 版本，说明它更适合当前 BAM 文件；
    - 使用不兼容的参考基因组可能导致区域提取、variant calling 或坐标解释异常。
    """

    bam_compatible = dataset_dir / "genome.bam_compatible.fa.gz"
    if bam_compatible.exists():
        return bam_compatible
    return dataset_dir / "genome.fa"


def _default_gff(dataset_dir: Path) -> Path:
    """根据数据包内容选择默认 GFF 注释文件。

    优先级：

    1. 如果存在 genome.original_coords.gff，则优先使用它；
    2. 否则使用 genome.gff。

    genome.original_coords.gff 通常用于保留原始坐标体系，
    便于将候选变异重新解释到原始基因组注释上。
    """

    original = dataset_dir / "genome.original_coords.gff"
    if original.exists():
        return original
    return dataset_dir / "genome.gff"


def _utc_now() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。

    用于 manifest.json 中的 start_time 和 end_time。

    使用 UTC 的好处：

    - 避免不同时区造成时间记录混乱；
    - 方便不同服务器、虚拟机和本地环境之间对齐日志；
    - 更适合写入可复现性记录。
    """

    return datetime.now(timezone.utc).isoformat()


def _append_log(log_file: Path, message: str) -> None:
    """向 run.log 追加一行日志。

    Args:
        log_file:
            日志文件路径。

        message:
            要追加写入的日志内容。

    该函数会自动创建日志目录。
    """

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """将字典写出为 JSON 文件。

    Args:
        path:
            输出 JSON 文件路径。

        payload:
            需要写出的字典对象。

    用途：
        当前主要用于写出 manifest.json。

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