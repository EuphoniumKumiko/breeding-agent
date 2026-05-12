"""Mini RNA-seq DEG workflow orchestration.

本文件负责“普通转录组差异表达分析”小型示例流程的编排。
它不是直接实现 featureCounts 或 limma-voom 的算法，而是把多个已有模块串起来：

1. 检查输入 BAM / GFF 文件和外部命令是否可用；
2. 调用 featureCounts 对 BAM 文件进行基因层面的 reads 计数；
3. 调用 R 脚本执行 limma-voom 差异表达分析；
4. 检查显著差异基因结果是否生成；
5. 生成面向用户的 Markdown 报告；
6. 将转录组 DEG 结果标准化为后续多组学聚合可复用的 evidence 表；
7. 基于标准化证据生成候选基因表和推荐报告；
8. 写出 run.log、manifest.json、commands.sh、checksums.sha256 等可追溯文件。

这个文件可以理解为 RNA-seq DEG 模块的“工作流调度层”：
- 上游：接收 CLI 或 Gradio 页面传入的 RnaSeqDegConfig；
- 中游：调用验证器、命令执行器、R 脚本和报告生成器；
- 下游：输出差异表达结果、报告和供多组学整合使用的标准化证据。
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from breeding_agent.core.command_runner import format_command, run_command
from breeding_agent.core.reproducibility import write_reproducibility_bundle
from breeding_agent.integration.candidate_aggregator import generate_candidate_gene_table
from breeding_agent.integration.recommendation_report import generate_recommendation_report
from breeding_agent.integration.transcriptomics_standardizer import (
    standardize_transcriptomics_deg,
)
from breeding_agent.reports.deg_report import DegReportConfig, generate_deg_report
from breeding_agent.validators.bam_validator import validate_bam_dir
from breeding_agent.validators.gff_validator import validate_gff
from breeding_agent.validators.tool_validator import validate_tools
from breeding_agent.validators.validation_result import ValidationResult


# -----------------------------
# 默认参数
# -----------------------------
# 默认 GFF 文件名。CLI / Gradio 未显式传入时会使用该文件。
DEFAULT_GFF = "genome.original_coords.gff"

# 默认比较组。这里表示 JM 与 LM 两组比较。
# 需要注意：代码后面专门提示 JM-LM 情况下 logFC < 0 代表 LM 组表达更高。
DEFAULT_CONTRAST = "JM-LM"

# 默认输出文件名前缀。R 脚本会据此生成：
# - JM_vs_LM.mini.significant_genes.tsv
# - JM_vs_LM.mini.all_genes.tsv
# - JM_vs_LM.mini.summary.txt
# - JM_vs_LM.mini.sample_info.tsv
DEFAULT_PREFIX = "JM_vs_LM.mini"

# 默认线程数，主要传给 featureCounts 的 -T 参数。
DEFAULT_THREADS = 4

# 默认输出目录。CLI / Gradio 未指定 outdir 时会把结果写到这里。
DEFAULT_OUTDIR = "outputs/demo_cli_run"

# featureCounts 输出的基因计数矩阵文件名。
COUNTS_FILENAME = "gene_counts_mini.txt"


@dataclass(frozen=True)
class RnaSeqDegConfig:
    """RNA-seq DEG 工作流的配置对象。

    这个 dataclass 用来统一承载 CLI、Gradio 或其他上层入口传入的参数。
    frozen=True 表示该配置对象创建后不可修改，有利于避免流程中途被意外改写。

    Attributes:
        bam_dir:
            BAM 文件所在目录。工作流会优先查找 *.mini.sorted.bam，找不到时退回查找 *.bam。
        gff:
            基因注释 GFF 文件。featureCounts 会使用它把 reads 汇总到基因或转录本注释上。
        contrast:
            差异分析比较组，例如 JM-LM。该字符串会传给 R 脚本。
        prefix:
            输出文件名前缀。用于组织 R 脚本输出和下游报告文件。
        trait:
            当前分析对应的性状名称。这里默认 unknown，后续标准化 evidence 时会写入。
        threads:
            featureCounts 使用的线程数。
        outdir:
            整个任务的输出目录。counts、DE 结果、报告、日志、manifest 都写在该目录下。
    """

    bam_dir: Path
    gff: Path = Path(DEFAULT_GFF)
    contrast: str = DEFAULT_CONTRAST
    prefix: str = DEFAULT_PREFIX
    trait: str = "unknown"
    threads: int = DEFAULT_THREADS
    outdir: Path = Path(DEFAULT_OUTDIR)


def find_bam_files(bam_dir: Path) -> list[Path]:
    """查找待分析的 BAM 文件。

    查找策略：
    1. 优先查找小型演示数据中的 *.mini.sorted.bam；
    2. 如果没有 mini BAM，则退回查找目录下所有 *.bam。

    这样做的原因是：
    - 项目演示/测试阶段通常使用 mini.sorted.bam；
    - 真实数据或其他数据包中可能只有普通 .bam 文件。

    Args:
        bam_dir: BAM 文件所在目录。

    Returns:
        排序后的 BAM 文件路径列表。

    Raises:
        FileNotFoundError: bam_dir 不存在。
        NotADirectoryError: bam_dir 存在但不是目录。
    """

    if not bam_dir.exists():
        raise FileNotFoundError(f"bam-dir does not exist: {bam_dir}")
    if not bam_dir.is_dir():
        raise NotADirectoryError(f"bam-dir is not a directory: {bam_dir}")

    # mini 数据优先，保证 demo / 单元测试使用的文件命名被优先识别。
    mini_bams = sorted(bam_dir.glob("*.mini.sorted.bam"))
    if mini_bams:
        return mini_bams

    # 如果没有 mini BAM，则使用目录中所有 .bam 文件作为输入。
    return sorted(bam_dir.glob("*.bam"))


def _repo_root() -> Path:
    """返回项目仓库根目录路径。

    当前文件路径通常类似：
    src/breeding_agent/workflows/rnaseq_deg.py

    Path(__file__).resolve().parents[3] 会回到项目根目录：
    - parents[0] -> workflows
    - parents[1] -> breeding_agent
    - parents[2] -> src
    - parents[3] -> 仓库根目录
    """

    return Path(__file__).resolve().parents[3]


def _r_script_path() -> Path:
    """返回 limma-voom 差异分析 R 脚本的路径。

    R 脚本被放在 workflows/rnaseq_deg/R/ 下。
    Python 负责调度和传参，真正的差异表达统计分析由该 R 脚本执行。
    """

    return (
        _repo_root()
        / "workflows"
        / "rnaseq_deg"
        / "R"
        / "differential_expression_limma_voom.R"
    )


def _ensure_inputs(config: RnaSeqDegConfig, bam_files: Iterable[Path]) -> list[Path]:
    """对关键输入进行存在性检查，并返回 BAM 文件列表。

    这里检查的是运行工作流必需的输入：
    - 至少找到一个 BAM 文件；
    - GFF 文件存在；
    - R 差异分析脚本存在。

    注意：更细粒度的格式检查由 _validate_workflow_inputs 调用各类 validator 完成。

    Args:
        config: RNA-seq DEG 工作流配置。
        bam_files: 已经由 find_bam_files 找到的 BAM 文件迭代器。

    Returns:
        BAM 文件路径列表。

    Raises:
        FileNotFoundError: 缺少 BAM、GFF 或 R 脚本时抛出。
    """

    # 先转成 list，避免传入的是生成器时只能迭代一次。
    bam_files = list(bam_files)
    if not bam_files:
        raise FileNotFoundError(
            f"No BAM files found in {config.bam_dir} "
            "(*.mini.sorted.bam first, then *.bam)."
        )
    if not config.gff.exists():
        raise FileNotFoundError(f"GFF file does not exist: {config.gff}")

    r_script = _r_script_path()
    if not r_script.exists():
        raise FileNotFoundError(f"R script does not exist: {r_script}")

    return bam_files


def _utc_now() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。

    使用 UTC 而不是本地时间，是为了增强不同机器、不同地区运行时的可追溯性。
    该时间会写入 manifest.json 和 run.log。
    """

    return datetime.now(timezone.utc).isoformat()


def _append_run_log(log_file: Path, message: str) -> None:
    """向 run.log 追加一行日志。

    Args:
        log_file: 日志文件路径。
        message: 要追加写入的日志内容。
    """

    # 确保 logs/ 目录存在。parents=True 可以递归创建父目录。
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")


def _write_manifest(manifest_file: Path, manifest: dict[str, object]) -> None:
    """写出 manifest.json。

    manifest 是本次运行的机器可读元数据，记录了：
    - 任务名称；
    - 运行状态；
    - 开始/结束时间；
    - 输入参数；
    - 调用过的外部命令；
    - 主要输出文件路径；
    - 失败时的错误信息。

    Args:
        manifest_file: manifest.json 输出路径。
        manifest: 待写出的 manifest 字典。
    """

    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with manifest_file.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _validate_workflow_inputs(config: RnaSeqDegConfig) -> ValidationResult:
    """执行工作流运行前的统一验证。

    验证内容来自三个 validator：
    1. validate_bam_dir：检查 BAM 目录和相关索引/文件情况；
    2. validate_gff：检查 GFF 文件是否存在及基本格式；
    3. validate_tools：检查 featureCounts、Rscript 等外部工具是否可用。

    Returns:
        ValidationResult，内部包含 warnings 和 errors。
        - warnings 会打印并写入日志，但不一定中断流程；
        - errors 会导致流程终止。
    """

    result = ValidationResult()
    result.extend(validate_bam_dir(config.bam_dir))
    result.extend(validate_gff(config.gff))
    result.extend(validate_tools())
    return result


def run_rnaseq_deg(config: RnaSeqDegConfig) -> Path:
    """运行 mini RNA-seq DEG 工作流。

    这是本文件的核心函数，负责从输入检查到最终报告生成的完整调度。

    主流程：
    1. 初始化输出路径、日志路径、manifest 元数据；
    2. 打印基本参数，创建输出目录；
    3. 验证输入文件和外部工具；
    4. 查找 BAM 文件；
    5. 调用 featureCounts 生成 counts 矩阵；
    6. 调用 Rscript 执行 limma-voom 差异分析；
    7. 检查显著差异基因文件是否生成；
    8. 生成 DEG Markdown 报告；
    9. 标准化转录组 evidence；
    10. 聚合候选基因并生成推荐报告；
    11. 成功时写出可复现性 bundle；失败时记录错误信息。

    Args:
        config: RNA-seq DEG 工作流配置。

    Returns:
        显著差异基因表路径，例如：
        outputs/demo_cli_run/mini_de/JM_vs_LM.mini.significant_genes.tsv

    Raises:
        subprocess.CalledProcessError:
            featureCounts 或 Rscript 命令执行失败时抛出。
        Exception:
            其他输入、输出或报告生成错误会继续向上抛出。
    """

    # -----------------------------
    # 1. 初始化运行时间与所有关键输出路径
    # -----------------------------
    start_time = _utc_now()
    log_file = config.outdir / "logs" / "run.log"
    manifest_file = config.outdir / "manifest.json"
    counts_dir = config.outdir / "counts"
    de_dir = config.outdir / "mini_de"

    # featureCounts 的基因计数矩阵输出。
    counts_file = counts_dir / COUNTS_FILENAME

    # R 脚本输出的显著差异基因表。
    significant_genes = de_dir / f"{config.prefix}.significant_genes.tsv"

    # 面向用户阅读的 DEG Markdown 报告。
    report_file = config.outdir / "reports" / "report.md"

    # 标准化转录组证据，供后续多组学聚合模块读取。
    standardized_evidence = config.outdir / "integration" / "standardized_evidence.tsv"

    # 候选基因聚合表。
    candidate_gene_table = config.outdir / "integration" / "candidate_gene_table.tsv"

    # 基于候选基因表生成的推荐报告。
    recommendation_report = config.outdir / "integration" / "recommendation_report.md"

    # 可复现性相关输出：命令记录和文件校验和。
    commands_sh = config.outdir / "provenance" / "commands.sh"
    checksums_sha256 = config.outdir / "provenance" / "checksums.sha256"

    # commands 用于记录本次运行调用过的外部命令。
    # 后续会写进 manifest，也会用于生成 commands.sh。
    commands: list[dict[str, str]] = []

    # manifest 是本次任务运行的完整元数据。
    # 注意 status 初始为 running，成功后改为 success，失败后改为 failed。
    manifest: dict[str, object] = {
        "task_name": "rnaseq_deg",
        "status": "running",
        "start_time": start_time,
        "end_time": None,
        "bam_dir": str(config.bam_dir),
        "gff": str(config.gff),
        "contrast": config.contrast,
        "prefix": config.prefix,
        "trait": config.trait,
        "threads": config.threads,
        "outdir": str(config.outdir),
        "commands": commands,
        "outputs": {
            "counts": str(counts_file),
            "significant_genes": str(significant_genes),
            "run_log": str(log_file),
            "report": str(report_file),
            "standardized_evidence": str(standardized_evidence),
            "candidate_gene_table": str(candidate_gene_table),
            "recommendation_report": str(recommendation_report),
            "commands_sh": str(commands_sh),
            "checksums_sha256": str(checksums_sha256),
        },
        "error_message": None,
    }

    # -----------------------------
    # 2. 打印任务基本信息，方便 CLI 和 Gradio 后端日志查看
    # -----------------------------
    print("[deg] Starting mini RNA-seq DEG workflow", flush=True)
    print(f"[deg] bam-dir: {config.bam_dir}", flush=True)
    print(f"[deg] gff: {config.gff}", flush=True)
    print(f"[deg] contrast: {config.contrast}", flush=True)
    print(f"[deg] prefix: {config.prefix}", flush=True)
    print(f"[deg] trait: {config.trait}", flush=True)
    print(f"[deg] threads: {config.threads}", flush=True)
    print(f"[deg] outdir: {config.outdir}", flush=True)

    # 对默认比较组做一个方向解释。
    # 这里的含义取决于 R 脚本中 contrast 的定义。
    if config.contrast == "JM-LM":
        print("[deg] contrast JM-LM: logFC < 0 means LM higher expression", flush=True)

    # 创建输出目录，并写入工作流开始日志。
    config.outdir.mkdir(parents=True, exist_ok=True)
    _append_run_log(log_file, f"[{start_time}] workflow started")

    try:
        # -----------------------------
        # 3. 输入与工具验证
        # -----------------------------
        validation = _validate_workflow_inputs(config)

        # warnings 不直接终止流程，但会显示在控制台并记录到 run.log。
        for warning in validation.warnings:
            print(f"[deg:warning] {warning}", flush=True)
            _append_run_log(log_file, f"[warning] {warning}")

        # errors 表示当前输入或环境不足以继续运行，直接终止。
        if validation.errors:
            for error in validation.errors:
                print(f"[deg:error] {error}", flush=True)
                _append_run_log(log_file, f"[error] {error}")
            raise ValueError("Input validation failed.")

        # -----------------------------
        # 4. 查找并确认 BAM、GFF、R 脚本等关键输入
        # -----------------------------
        bam_files = _ensure_inputs(config, find_bam_files(config.bam_dir))
        print(f"[deg] Found {len(bam_files)} BAM file(s)", flush=True)
        for bam in bam_files:
            print(f"[deg]   {bam}", flush=True)

        # 创建 counts 和差异分析结果目录。
        counts_dir.mkdir(parents=True, exist_ok=True)
        de_dir.mkdir(parents=True, exist_ok=True)

        # -----------------------------
        # 5. 构建并运行 featureCounts 命令
        # -----------------------------
        # 参数说明：
        # -T: 线程数；
        # -p: paired-end reads；
        # -t exon: 以 GFF/GTF 中 exon 作为 feature 类型；
        # -g Parent: 使用 Parent 属性将 exon 汇总到对应基因/转录本；
        # -a: 注释文件；
        # -o: 输出 counts 矩阵；
        # 最后追加所有 BAM 文件路径。
        featurecounts_command = [
            "featureCounts",
            "-T",
            str(config.threads),
            "-p",
            "-t",
            "exon",
            "-g",
            "Parent",
            "-a",
            str(config.gff),
            "-o",
            str(counts_file),
            *[str(bam) for bam in bam_files],
        ]

        # 记录命令，后续写入 manifest 和 commands.sh，便于复现。
        commands.append(
            {"name": "featureCounts", "command": format_command(featurecounts_command)}
        )
        print(f"[deg] Running featureCounts -> {counts_file}", flush=True)

        # run_command 内部封装 subprocess.run，并把 stdout/stderr 写入 run.log。
        run_command(featurecounts_command, log_file=log_file)

        # -----------------------------
        # 6. 构建并运行 Rscript limma-voom 差异分析命令
        # -----------------------------
        r_script = _r_script_path()
        r_command = [
            "Rscript",
            str(r_script),
            "--counts",
            str(counts_file),
            "--outdir",
            str(de_dir),
            "--prefix",
            config.prefix,
            "--contrast",
            config.contrast,
            "--fdr",
            "0.05",
            "--lfc",
            "1",
            "--min-count",
            "10",
            "--min-samples",
            "3",
        ]

        # 记录 Rscript 命令，便于后续复现和排错。
        commands.append({"name": "Rscript", "command": format_command(r_command)})
        print(f"[deg] Running limma-voom R workflow -> {de_dir}", flush=True)
        run_command(r_command, log_file=log_file)

        # -----------------------------
        # 7. 检查核心结果是否生成
        # -----------------------------
        print(f"[deg] Checking result: {significant_genes}", flush=True)
        if not significant_genes.exists():
            raise FileNotFoundError(
                f"Expected significant genes file was not created: {significant_genes}"
            )

        # -----------------------------
        # 8. 生成 DEG 结果报告
        # -----------------------------
        print(f"[deg] Generating report -> {report_file}", flush=True)
        generate_deg_report(
            DegReportConfig(
                task_name="rnaseq_deg",
                bam_dir=config.bam_dir,
                gff=config.gff,
                contrast=config.contrast,
                prefix=config.prefix,
                outdir=config.outdir,
                counts_file=counts_file,
                significant_genes_file=significant_genes,
                manifest_file=manifest_file,
                run_log_file=log_file,
            )
        )

        # -----------------------------
        # 9. 标准化转录组证据
        # -----------------------------
        # 该步骤把 DEG 结果转换为统一字段格式，方便后续多组学整合模块读取。
        # 例如后续 flavonoid marker recommendation 可以把转录组证据、代谢组证据、
        # 注释证据、文献证据等放到同一个候选基因评价体系中。
        print(f"[deg] Standardizing evidence -> {standardized_evidence}", flush=True)
        standardize_transcriptomics_deg(
            outdir=config.outdir,
            prefix=config.prefix,
            contrast=config.contrast,
            trait=config.trait,
        )

        # -----------------------------
        # 10. 候选基因聚合与推荐报告生成
        # -----------------------------
        print(f"[deg] Aggregating candidates -> {candidate_gene_table}", flush=True)
        generate_candidate_gene_table(outdir=config.outdir)

        print(f"[deg] Generating recommendation report -> {recommendation_report}", flush=True)
        generate_recommendation_report(outdir=config.outdir)

        # 全部步骤完成后标记成功，并返回显著差异基因表路径。
        manifest["status"] = "success"
        print("[deg] Workflow finished successfully", flush=True)
        return significant_genes

    except subprocess.CalledProcessError as exc:
        # -----------------------------
        # 外部命令失败处理
        # -----------------------------
        # 当 featureCounts 或 Rscript 返回非 0 退出码时，run_command 会抛出该异常。
        # 这里把失败命令和退出码记录到 manifest，方便定位是哪个外部工具失败。
        manifest["status"] = "failed"
        manifest["error_message"] = (
            f"Command failed with exit code {exc.returncode}: "
            f"{format_command(exc.cmd)}"
        )
        raise

    except Exception as exc:
        # -----------------------------
        # 其他异常处理
        # -----------------------------
        # 包括输入文件缺失、结果文件未生成、报告生成失败等非 subprocess 错误。
        # 统一写入 manifest 后继续向上抛出，保证 CLI / Gradio 能感知任务失败。
        manifest["status"] = "failed"
        manifest["error_message"] = str(exc)
        raise

    finally:
        # -----------------------------
        # 无论成功或失败都必须执行的收尾工作
        # -----------------------------
        end_time = _utc_now()
        manifest["end_time"] = end_time
        _append_run_log(log_file, f"[{end_time}] workflow ended: {manifest['status']}")

        # 写出 manifest.json，记录本次任务完整状态。
        _write_manifest(manifest_file, manifest)

        # 只有任务成功时，才写出可复现性 bundle。
        # 失败时某些输出文件可能不存在，如果强行计算校验和会引发二次错误。
        if manifest["status"] == "success":
            write_reproducibility_bundle(
                outdir=config.outdir,
                commands=commands,
                checksum_files=[
                    config.gff,
                    counts_file,
                    significant_genes,
                    standardized_evidence,
                    candidate_gene_table,
                    recommendation_report,
                    report_file,
                    manifest_file,
                ],
            )


def run_rnaseq_deg_task(config: RnaSeqDegConfig) -> Path:
    """CLI 和 Web UI 共用的公开入口。

    这个函数目前只是简单转调 run_rnaseq_deg(config)，但保留它有两个好处：
    1. 对外暴露一个更稳定、更语义化的入口名；
    2. 后续如果 Gradio / API 入口需要额外包装逻辑，可以在这里扩展，
       而不用改动核心 run_rnaseq_deg 函数。
    """

    return run_rnaseq_deg(config)
