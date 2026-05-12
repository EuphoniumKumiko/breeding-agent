"""Candidate-region variant calling helpers for genomics MVP.

本文件是候选区域变异检测模块的底层工具函数集合。

它属于 modules 层，主要负责真正执行和解析 genomics variant calling 相关逻辑：
- 检查 samtools / bcftools 是否安装；
- 查找 BAM 文件；
- 检查输入 FASTA、BED 是否存在；
- 为参考基因组生成 faidx 索引；
- 为 BAM 文件生成 .bai 索引；
- 调用 bcftools mpileup / call / filter 在候选区域内检测变异；
- 解析 VCF，生成 candidate_variants.tsv，构建候选 SNP / InDel / KASP / CAPS 初筛表；
- 根据 GFF / BED 给变异位点添加目标基因或候选区域注释。

它与 workflow 层的关系是：

workflows/genomics_variant_calling.py
        ↓
调用本文件中的 require_tools()
调用 validate_variant_calling_inputs()
调用 ensure_reference_index()
调用 ensure_bam_indexes()
调用 call_candidate_region_variants()
调用 build_variant_tables_from_vcf()
        ↓
生成 VCF、TSV 表和统计结果
        ↓
workflow 层再生成 manifest.json、run.log 和 Markdown 报告

注意：
当前模块只做 candidate-region variant calling MVP。
可以产出候选 SNP/InDel 位点。可以给出 KASP 初筛状态、CAPS/dCAPS enzyme screening 提示
它不是完整 WGS/GBS 群体变异检测流程；
KASP/CAPS 结果也只是 preliminary screening，
不是最终 KASP 引物设计或 CAPS 酶切方案。
"""

from __future__ import annotations

import csv
import gzip
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


# 当前谷子黄酮候选标记任务中固定关注的三个目标基因。
#
# read_gene_intervals() 会在 GFF attributes 中查找这些基因 ID；
# build_variant_tables_from_vcf() 会统计哪些目标基因被候选变异覆盖。
TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")


# candidate_variants.tsv / snp_candidates.tsv / indel_candidates.tsv 的统一列名。
#
# 这些列描述一个 VCF 变异记录转换后的候选标记信息：
# - chrom / pos / ref / alt: 变异基本坐标和等位基因；
# - variant_type: SNP、INDEL 或 MIXED；
# - qual / filter / depth: VCF 中的质量、过滤状态和深度；
# - source_vcf: 来源 VCF；
# - nearest_or_target_gene: 目标基因 ID 或候选区域名称；
# - marker_implication: 对标记开发的初步解释。
CANDIDATE_VARIANT_COLUMNS = [
    "chrom",
    "pos",
    "ref",
    "alt",
    "variant_type",
    "qual",
    "filter",
    "depth",
    "source_vcf",
    "nearest_or_target_gene",
    "marker_implication",
]


# kasp_candidate_sites.tsv 的列名。
#
# 该表只从 SNP 候选位点生成。
# 当前逻辑不会直接输出 KASP 引物，只判断是否适合进入 KASP 初步复核。
KASP_COLUMNS = [
    "chrom",
    "pos",
    "ref",
    "alt",
    "gene_id",
    "kasp_readiness",
    "reason",
]


# caps_candidate_sites.tsv 的列名。
#
# 该表不会直接判断具体限制性内切酶。
# 当前只提示：需要进一步筛查该变异是否改变酶切识别位点。
CAPS_COLUMNS = [
    "chrom",
    "pos",
    "ref",
    "alt",
    "gene_id",
    "caps_status",
    "reason",
]


class VariantCallingError(RuntimeError):
    """候选区域 variant calling 的基础异常类型。

    后续如果需要区分更多错误类型，可以继承这个类。
    例如：
    - MissingToolError
    - InvalidVcfError
    - InvalidRegionError
    """


class MissingToolError(VariantCallingError):
    """缺少必要外部工具时抛出的异常。

    当前主要用于 samtools / bcftools 不存在的情况。
    Gradio 页面会捕获该异常，并提示用户安装对应工具。
    """


@dataclass(frozen=True)
class CommandResult:
    """记录一次外部命令调用。

    Attributes:
        name:
            命令的简短名称，例如 "samtools faidx"、"bcftools mpileup"。

        command:
            实际执行的命令参数列表。
            使用 list[str] 而不是 shell 字符串，可以避免 shell 注入风险。
    """

    name: str
    command: list[str]

    @property
    def rendered(self) -> str:
        """将命令列表渲染成可读字符串。

        主要用于写入 manifest.json 或 run.log，
        方便用户复现和排查问题。
        """

        return " ".join(self.command)


def require_tools(tools: tuple[str, ...] = ("samtools", "bcftools")) -> dict[str, str]:
    """检查必要外部工具是否可用。

    Args:
        tools:
            需要检查的命令名称列表。
            默认检查 samtools 和 bcftools。

    Returns:
        resolved:
            工具名到可执行文件路径的映射。
            例如：
            {
                "samtools": "/home/li/micromamba/envs/.../bin/samtools",
                "bcftools": "/home/li/micromamba/envs/.../bin/bcftools"
            }

    Raises:
        MissingToolError:
            如果缺少任意必要工具，则抛出异常并给出安装建议。
    """

    resolved = {}
    missing = []

    # shutil.which 会在 PATH 中查找命令。
    # 找到则返回完整路径，找不到则返回 None。
    for tool in tools:
        path = shutil.which(tool)
        if path:
            resolved[tool] = path
        else:
            missing.append(tool)

    # 只要有工具缺失，就终止流程。
    # 因为后续索引构建、mpileup、call、filter 都依赖这些命令。
    if missing:
        raise MissingToolError(
            "Required tool(s) not found: "
            + ", ".join(missing)
            + ". Install samtools and bcftools, for example with "
            "`micromamba install -c bioconda samtools bcftools`."
        )

    return resolved


def find_bam_files(bam_dir: Path) -> list[Path]:
    """在指定目录中查找 BAM 文件。

    Args:
        bam_dir:
            BAM 文件所在目录。

    Returns:
        排序后的 BAM 文件路径列表。

    Raises:
        FileNotFoundError:
            BAM 目录不存在，或目录中没有 .bam 文件。

        NotADirectoryError:
            bam_dir 存在但不是目录。
    """

    if not bam_dir.exists():
        raise FileNotFoundError(f"BAM directory does not exist: {bam_dir}")
    if not bam_dir.is_dir():
        raise NotADirectoryError(f"BAM path is not a directory: {bam_dir}")

    # 当前 variant calling 模块查找所有 *.bam 文件。
    # 这里不限定 *.mini.sorted.bam，因为它面向候选区域变异检测，可能接入更多 BAM 命名。
    bam_files = sorted(bam_dir.glob("*.bam"))

    if not bam_files:
        raise FileNotFoundError(f"No BAM files found in: {bam_dir}")

    return bam_files


def validate_variant_calling_inputs(
    *,
    bam_dir: Path,
    reference_fasta: Path,
    regions_bed: Path,
) -> list[Path]:
    """校验候选区域 variant calling 的关键输入。

    Args:
        bam_dir:
            BAM 文件目录。

        reference_fasta:
            参考基因组 FASTA。

        regions_bed:
            候选区域 BED 文件。

    Returns:
        bam_files:
            查找到的 BAM 文件列表。

    Raises:
        FileNotFoundError:
            缺少 BAM、参考基因组或 regions.bed 时抛出。
    """

    # 查找 BAM 文件，同时检查 bam_dir 是否存在。
    bam_files = find_bam_files(bam_dir)

    # 检查参考基因组 FASTA。
    if not reference_fasta.exists():
        raise FileNotFoundError(f"Reference FASTA does not exist: {reference_fasta}")

    # 检查候选区域 BED。
    if not regions_bed.exists():
        raise FileNotFoundError(f"Regions BED does not exist: {regions_bed}")

    return bam_files


def ensure_reference_index(
    *,
    reference_fasta: Path,
    log_file: Path,
    commands: list[CommandResult],
) -> Path:
    """确保参考基因组 FASTA 存在 samtools faidx 索引。

    samtools / bcftools 按区域读取 FASTA 时通常需要 .fai 索引。

    Args:
        reference_fasta:
            参考基因组 FASTA 路径。

        log_file:
            外部命令日志文件。

        commands:
            用于记录本次运行执行过的命令。

    Returns:
        fai:
            FASTA 索引文件路径，通常是 reference_fasta + ".fai"。
    """

    # .fai 索引路径。
    fai = Path(str(reference_fasta) + ".fai")

    # 如果索引已存在，直接复用，不重复生成。
    if fai.exists():
        return fai

    # 如果索引不存在，则调用 samtools faidx 生成。
    command = ["samtools", "faidx", str(reference_fasta)]
    run_logged_command(command, log_file=log_file)

    # 记录命令，便于 manifest 和复现。
    commands.append(CommandResult(name="samtools faidx", command=command))

    return fai


def ensure_bam_indexes(
    *,
    bam_files: list[Path],
    log_file: Path,
    commands: list[CommandResult],
) -> list[Path]:
    """确保每个 BAM 文件都有索引。

    BAM 按区域读取需要 .bai 索引。
    samtools 常见索引命名有两种：
    - sample.bam.bai
    - sample.bai

    本函数会同时检查这两种形式。
    如果都不存在，则调用 samtools index 生成。

    Args:
        bam_files:
            BAM 文件列表。

        log_file:
            外部命令日志文件。

        commands:
            用于记录执行过的外部命令。

    Returns:
        index_paths:
            每个 BAM 对应的索引路径列表。
    """

    index_paths = []

    for bam in bam_files:
        # 默认 samtools index 输出形式：sample.bam.bai。
        default_index = Path(str(bam) + ".bai")

        # 另一种常见索引命名：sample.bai。
        alternate_index = bam.with_suffix(".bai")

        # 如果默认索引存在，直接使用。
        if default_index.exists():
            index_paths.append(default_index)
            continue

        # 如果 alternate index 存在，也可以使用。
        if alternate_index.exists():
            index_paths.append(alternate_index)
            continue

        # 两种索引都不存在，则调用 samtools index。
        command = ["samtools", "index", str(bam)]
        run_logged_command(command, log_file=log_file)
        commands.append(CommandResult(name="samtools index", command=command))

        # samtools index 默认生成 sample.bam.bai。
        index_paths.append(default_index)

    return index_paths


def call_candidate_region_variants(
    *,
    bam_files: list[Path],
    reference_fasta: Path,
    regions_bed: Path,
    variants_dir: Path,
    log_file: Path,
    commands: list[CommandResult],
) -> dict[str, Path]:
    """调用 bcftools 在候选区域内进行 variant calling。

    该函数执行三个外部命令：

    1. bcftools mpileup
       根据 BAM、参考基因组和候选区域 BED 生成 mpileup BCF。

    2. bcftools call
       从 mpileup BCF 中调用变异，生成 raw VCF。

    3. bcftools filter
       对 raw VCF 进行简单质量过滤：
       - QUAL < 20 的变异标记为 LowQual；
       - 其他变异保留 PASS。

    Args:
        bam_files:
            输入 BAM 文件列表。

        reference_fasta:
            参考基因组 FASTA。

        regions_bed:
            候选区域 BED 文件。

        variants_dir:
            VCF / BCF 输出目录。

        log_file:
            外部命令日志文件。

        commands:
            用于记录执行过的命令。

    Returns:
        包含三个输出路径的字典：
        - mpileup_bcf
        - raw_vcf
        - filtered_vcf
    """

    variants_dir.mkdir(parents=True, exist_ok=True)

    # 中间 mpileup BCF 文件。
    mpileup_bcf = variants_dir / "candidate_regions.mpileup.bcf"

    # 未过滤的 raw VCF。
    raw_vcf = variants_dir / "candidate_regions.raw.vcf.gz"

    # 过滤后的 VCF。
    filtered_vcf = variants_dir / "candidate_regions.filtered.vcf.gz"

    # bcftools mpileup：
    # -f 指定参考基因组；
    # -R 指定候选区域 BED；
    # -Ou 输出未压缩 BCF；
    # -o 指定输出文件；
    # 最后追加所有 BAM 文件。
    mpileup_command = [
        "bcftools",
        "mpileup",
        "-f",
        str(reference_fasta),
        "-R",
        str(regions_bed),
        "-Ou",
        "-o",
        str(mpileup_bcf),
        *[str(path) for path in bam_files],
    ]

    # bcftools call：
    # -m 使用 multiallelic caller；
    # -v 只输出 variant sites；
    # -Oz 输出 bgzip 压缩 VCF。
    call_command = [
        "bcftools",
        "call",
        "-mv",
        "-Oz",
        "-o",
        str(raw_vcf),
        str(mpileup_bcf),
    ]

    # bcftools filter：
    # -s LowQual 表示不满足条件的记录 FILTER 标记为 LowQual；
    # -e QUAL<20 表示 QUAL 小于 20 的记录被标记；
    # -Oz 输出压缩 VCF。
    filter_command = [
        "bcftools",
        "filter",
        "-s",
        "LowQual",
        "-e",
        "QUAL<20",
        "-Oz",
        "-o",
        str(filtered_vcf),
        str(raw_vcf),
    ]

    # 顺序执行三个命令，并记录到 log 和 commands。
    for name, command in [
        ("bcftools mpileup", mpileup_command),
        ("bcftools call", call_command),
        ("bcftools filter", filter_command),
    ]:
        run_logged_command(command, log_file=log_file)
        commands.append(CommandResult(name=name, command=command))

    return {
        "mpileup_bcf": mpileup_bcf,
        "raw_vcf": raw_vcf,
        "filtered_vcf": filtered_vcf,
    }


def run_logged_command(command: list[str], *, log_file: Path) -> None:
    """执行外部命令，并把 stdout / stderr 追加到日志文件。

    Args:
        command:
            要执行的命令列表。

        log_file:
            日志文件路径。

    Raises:
        subprocess.CalledProcessError:
            命令返回非 0 退出码时抛出。

    设计说明：
        这里使用 subprocess.run(command, shell=False)，
        command 是 list[str]，不是字符串。
        这样更安全，也更适合处理路径中包含空格的情况。
    """

    log_file.parent.mkdir(parents=True, exist_ok=True)

    with log_file.open("a", encoding="utf-8") as log:
        # 先把命令本身写入日志。
        log.write("$ " + " ".join(command) + "\n")

        # stdout 和 stderr 都写入同一个 log 文件。
        completed = subprocess.run(
            command,
            stdout=log,
            stderr=log,
            text=True,
            check=False,
        )

        # 写入退出码。
        log.write(f"[exit_code] {completed.returncode}\n")

    # 非 0 退出码表示命令失败，向上抛异常。
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, command)


def build_variant_tables_from_vcf(
    *,
    vcf_path: Path,
    tables_dir: Path,
    gff: Path | None,
    regions_bed: Path | None,
) -> dict[str, object]:
    """解析 VCF 记录，并写出候选标记相关表格。

    该函数是 VCF -> TSV 的核心转换步骤。

    输入：
    - filtered VCF；
    - GFF 注释；
    - regions.bed 候选区域。

    输出：
    - candidate_variants.tsv：所有候选变异；
    - snp_candidates.tsv：SNP 候选；
    - indel_candidates.tsv：InDel 候选；
    - kasp_candidate_sites.tsv：SNP 到 KASP 的初筛结果；
    - caps_candidate_sites.tsv：变异到 CAPS/dCAPS 的初筛提示。

    注意：
        KASP/CAPS 表只是初步筛选和提醒，
        不代表最终引物设计或酶切方案。
    """

    tables_dir.mkdir(parents=True, exist_ok=True)

    # 从 GFF 中读取目标基因区间。
    # 如果 gff 为空或不存在，则返回空列表。
    gene_intervals = read_gene_intervals(gff) if gff else []

    # 从 BED 中读取候选区域区间。
    # 如果 regions_bed 为空或不存在，则返回空列表。
    region_intervals = read_bed_intervals(regions_bed) if regions_bed else []

    # 解析 VCF，得到候选变异记录列表。
    candidate_rows = parse_vcf_candidate_variants(
        vcf_path=vcf_path,
        gene_intervals=gene_intervals,
        region_intervals=region_intervals,
    )

    # 拆分 SNP 和 InDel。
    snp_rows = [row for row in candidate_rows if row["variant_type"] == "SNP"]
    indel_rows = [row for row in candidate_rows if row["variant_type"] == "INDEL"]

    # 从 SNP 候选生成 KASP 初筛表。
    kasp_rows = build_kasp_candidate_rows(snp_rows)

    # 从所有候选变异生成 CAPS 初筛表。
    caps_rows = build_caps_candidate_rows(candidate_rows)

    # 定义输出文件路径。
    candidate_file = tables_dir / "candidate_variants.tsv"
    snp_file = tables_dir / "snp_candidates.tsv"
    indel_file = tables_dir / "indel_candidates.tsv"
    kasp_file = tables_dir / "kasp_candidate_sites.tsv"
    caps_file = tables_dir / "caps_candidate_sites.tsv"

    # 写出所有 TSV 表。
    write_tsv(candidate_file, CANDIDATE_VARIANT_COLUMNS, candidate_rows)
    write_tsv(snp_file, CANDIDATE_VARIANT_COLUMNS, snp_rows)
    write_tsv(indel_file, CANDIDATE_VARIANT_COLUMNS, indel_rows)
    write_tsv(kasp_file, KASP_COLUMNS, kasp_rows)
    write_tsv(caps_file, CAPS_COLUMNS, caps_rows)

    # 统计当前候选变异覆盖到哪些固定目标基因。
    covered_genes = sorted(
        {
            row["nearest_or_target_gene"]
            for row in candidate_rows
            if row["nearest_or_target_gene"] in TARGET_GENES
        }
    )

    # 按 FILTER 状态统计 PASS / LowQual。
    pass_variants = [row for row in candidate_rows if is_pass_variant(row)]
    lowqual_variants = [row for row in candidate_rows if not is_pass_variant(row)]

    pass_snps = [row for row in snp_rows if is_pass_variant(row)]
    lowqual_snps = [row for row in snp_rows if not is_pass_variant(row)]

    pass_indels = [row for row in indel_rows if is_pass_variant(row)]
    lowqual_indels = [row for row in indel_rows if not is_pass_variant(row)]

    return {
        "candidate_rows": candidate_rows,
        "snp_rows": snp_rows,
        "indel_rows": indel_rows,
        "kasp_rows": kasp_rows,
        "caps_rows": caps_rows,
        "covered_target_genes": covered_genes,
        "outputs": {
            "candidate_variants": str(candidate_file),
            "snp_candidates": str(snp_file),
            "indel_candidates": str(indel_file),
            "kasp_candidate_sites": str(kasp_file),
            "caps_candidate_sites": str(caps_file),
        },
        "counts": {
            "candidate_variants": len(candidate_rows),
            "snps": len(snp_rows),
            "indels": len(indel_rows),
            "kasp_candidate_sites": len(kasp_rows),
            "caps_candidate_sites": len(caps_rows),
            "pass_variants": len(pass_variants),
            "lowqual_variants": len(lowqual_variants),
            "pass_snps": len(pass_snps),
            "lowqual_snps": len(lowqual_snps),
            "pass_indels": len(pass_indels),
            "lowqual_indels": len(lowqual_indels),
            "kasp_preliminary_pass": count_rows_by_value(
                kasp_rows, "kasp_readiness", "preliminary_pass"
            ),
            "kasp_low_quality_review_required": count_rows_by_value(
                kasp_rows, "kasp_readiness", "low_quality_review_required"
            ),
            "caps_pass_variant_requires_enzyme_screening": count_rows_by_value(
                caps_rows, "caps_status", "pass_variant_requires_enzyme_screening"
            ),
            "caps_low_quality_variant_requires_review": count_rows_by_value(
                caps_rows, "caps_status", "low_quality_variant_requires_review"
            ),
        },
    }


def parse_vcf_candidate_variants(
    *,
    vcf_path: Path,
    gene_intervals: list[dict[str, object]] | None = None,
    region_intervals: list[dict[str, object]] | None = None,
) -> list[dict[str, str]]:
    """将 VCF 记录解析为候选变异表行。

    Args:
        vcf_path:
            VCF 文件路径，可以是普通文本 VCF，也可以是 .gz 压缩 VCF。

        gene_intervals:
            目标基因区间列表，通常来自 GFF。

        region_intervals:
            候选区域区间列表，通常来自 regions.bed。

    Returns:
        candidate variant rows。

    解析逻辑：
        - 跳过空行和以 # 开头的 VCF header；
        - 至少需要 8 列标准 VCF 字段；
        - 提取 CHROM、POS、REF、ALT、QUAL、FILTER、INFO；
        - 从 INFO 或 FORMAT/sample 字段提取 depth；
        - 根据 GFF/BED 注释目标基因或候选区域；
        - 根据 REF/ALT 判断 SNP、INDEL 或 MIXED；
        - 写入 marker_implication。
    """

    rows = []

    gene_intervals = gene_intervals or []
    region_intervals = region_intervals or []

    with open_text_maybe_gzip(vcf_path) as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue

            fields = line.rstrip("\n").split("\t")

            # 标准 VCF 至少包含 8 个固定字段：
            # CHROM POS ID REF ALT QUAL FILTER INFO
            if len(fields) < 8:
                continue

            chrom, pos, _id, ref, alt, qual, filt, info = fields[:8]

            # depth 可能在 INFO/DP 中，也可能在 FORMAT/sample 的 DP 中。
            depth = extract_depth(info, fields[8:])

            # 根据位点坐标匹配目标基因或候选区域。
            gene_id = annotate_gene_or_region(
                chrom=chrom,
                pos=int(pos),
                gene_intervals=gene_intervals,
                region_intervals=region_intervals,
            )

            # 根据 REF/ALT 判断变异类型。
            variant_type = classify_variant(ref, alt)

            rows.append(
                {
                    "chrom": chrom,
                    "pos": pos,
                    "ref": ref,
                    "alt": alt,
                    "variant_type": variant_type,
                    "qual": qual,
                    "filter": filt,
                    "depth": depth,
                    "source_vcf": str(vcf_path),
                    "nearest_or_target_gene": gene_id,
                    "marker_implication": marker_implication(variant_type),
                }
            )

    return rows


def open_text_maybe_gzip(path: Path):
    """打开普通文本文件或 gzip 压缩文本文件。

    Args:
        path:
            输入文件路径。

    Returns:
        文本读取 handle。

    用途：
        VCF 可能是：
        - .vcf
        - .vcf.gz

        该函数统一处理两种情况。
    """

    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")

    return path.open("r", encoding="utf-8", errors="replace")


def classify_variant(ref: str, alt: str) -> str:
    """根据 VCF 的 REF / ALT 判断变异类型。

    Args:
        ref:
            REF 等位基因。

        alt:
            ALT 等位基因，可能包含逗号分隔的多个 ALT。

    Returns:
        - "SNP"
        - "INDEL"
        - "MIXED"

    判断规则：
        - 如果 REF 和所有 ALT 长度都是 1，则为 SNP；
        - 如果任一 ALT 与 REF 长度不同，则为 INDEL；
        - 其他情况归为 MIXED。
    """

    # 支持多等位 ALT，例如 A,C。
    alts = [item for item in alt.split(",") if item]

    if alts and all(len(ref) == 1 and len(item) == 1 for item in alts):
        return "SNP"

    if alts and any(len(ref) != len(item) for item in alts):
        return "INDEL"

    return "MIXED"


def marker_implication(variant_type: str) -> str:
    """根据变异类型给出标记开发含义说明。

    注意：
        这里不是最终标记设计，
        只是对 SNP / InDel / MIXED 的初步解释。
    """

    if variant_type == "SNP":
        return (
            "SNP candidate from bcftools VCF; preliminary KASP conversion possible "
            "after manual flanking-sequence review."
        )

    if variant_type == "INDEL":
        return (
            "InDel candidate from bcftools VCF; review size and flanking sequence "
            "before marker conversion."
        )

    return "Mixed or complex variant from bcftools VCF; manual review required."


def build_kasp_candidate_rows(
    snp_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """从 SNP 候选表构建 KASP 初筛表。

    KASP 通常基于稳定、清晰的双等位 SNP 进行开发。
    因此当前 MVP 逻辑只从 SNP 中筛 KASP 候选。

    判断规则：
        - 多等位 SNP：not_recommended；
        - PASS 双等位 SNP：preliminary_pass；
        - LowQual 或未通过过滤 SNP：low_quality_review_required。

    注意：
        preliminary_pass 不等于最终 KASP 标记。
        后续仍需：
        - 检查侧翼序列；
        - 设计和筛查引物；
        - 在更大群体中验证基因型和表型关联；
        - 做实验验证。
    """

    rows = []

    for row in snp_rows:
        alt = row["alt"]

        if "," in alt:
            readiness = "not_recommended"
            reason = "Multi-allelic SNP; first MVP does not recommend direct KASP design."

        elif is_pass_variant(row):
            readiness = "preliminary_pass"
            reason = (
                "Biallelic PASS SNP from VCF; suitable for preliminary KASP review "
                "after flanking-sequence and population validation."
            )

        else:
            readiness = "low_quality_review_required"
            reason = (
                "SNP is present in VCF but did not pass filtering; do not prioritize "
                "for KASP until coverage, quality, and flanking sequence are manually "
                "reviewed."
            )

        rows.append(
            {
                "chrom": row["chrom"],
                "pos": row["pos"],
                "ref": row["ref"],
                "alt": row["alt"],
                "gene_id": row["nearest_or_target_gene"],
                "kasp_readiness": readiness,
                "reason": reason,
            }
        )

    return rows


def build_caps_candidate_rows(
    candidate_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """构建 CAPS/dCAPS 初筛表。

    CAPS/dCAPS 设计依赖变异是否影响限制性内切酶识别位点。
    当前代码没有读取限制性内切酶库，也没有计算酶切位点变化，
    因此绝不能直接声称某个位点就是 CAPS 标记。

    当前逻辑只输出“需要 enzyme screening”的提示：

    - PASS 变异：
      pass_variant_requires_enzyme_screening

    - LowQual 变异：
      low_quality_variant_requires_review

    这能保证报告边界安全：
    不虚构酶切位点，不输出最终 CAPS 方案。
    """

    rows = []

    for row in candidate_rows:
        if is_pass_variant(row):
            status = "pass_variant_requires_enzyme_screening"
            reason = (
                "Do not assume an enzyme site. Screen whether this variant changes "
                "a restriction enzyme recognition sequence before CAPS/dCAPS design."
            )
        else:
            status = "low_quality_variant_requires_review"
            reason = (
                "Do not assume an enzyme site. Screen whether this variant changes "
                "a restriction enzyme recognition sequence before CAPS/dCAPS design. "
                "LowQual variants require manual quality review before marker "
                "prioritization."
            )

        rows.append(
            {
                "chrom": row["chrom"],
                "pos": row["pos"],
                "ref": row["ref"],
                "alt": row["alt"],
                "gene_id": row["nearest_or_target_gene"],
                "caps_status": status,
                "reason": reason,
            }
        )

    return rows


def is_pass_variant(row: dict[str, str]) -> bool:
    """判断一个 VCF 变异记录是否为 PASS。

    Args:
        row:
            候选变异记录。

    Returns:
        如果 FILTER 字段为 PASS，则返回 True。
    """

    return row.get("filter", "") == "PASS"


def count_rows_by_value(rows: list[dict[str, str]], key: str, value: str) -> int:
    """统计表格记录中某一列等于指定值的行数。

    Args:
        rows:
            表格行列表，每一行是 dict。

        key:
            要检查的字段名。

        value:
            目标字段值。

    Returns:
        满足 row[key] == value 的记录数量。
    """

    return sum(1 for row in rows if row.get(key) == value)


def extract_depth(info: str, remaining_fields: list[str]) -> str:
    """从 VCF INFO 或 FORMAT/sample 字段中提取测序深度 DP。

    Args:
        info:
            VCF 第 8 列 INFO 字段。

        remaining_fields:
            VCF 第 9 列及之后的字段。
            通常包括：
            - FORMAT
            - 每个样本的 genotype 字段

    Returns:
        depth 字符串。
        如果无法提取，则返回空字符串。

    提取优先级：
        1. INFO 字段中的 DP；
        2. FORMAT/sample 字段中的 DP，总和所有样本的 DP；
        3. 如果都不存在，则返回空字符串。
    """

    # 优先从 INFO 字段中提取 DP。
    info_values = parse_info(info)
    if info_values.get("DP"):
        return info_values["DP"]

    # 如果没有 FORMAT/sample 字段，则无法进一步提取。
    if not remaining_fields:
        return ""

    # remaining_fields[0] 是 FORMAT，例如 GT:PL:DP。
    format_keys = remaining_fields[0].split(":")

    if "DP" not in format_keys:
        return ""

    dp_index = format_keys.index("DP")

    # 对所有样本的 DP 求和。
    depths = []
    for sample_field in remaining_fields[1:]:
        sample_values = sample_field.split(":")
        if dp_index < len(sample_values) and sample_values[dp_index].isdigit():
            depths.append(int(sample_values[dp_index]))

    return str(sum(depths)) if depths else ""


def parse_info(info: str) -> dict[str, str]:
    """解析 VCF INFO 字段。

    Args:
        info:
            VCF INFO 字段，例如：
            DP=30;AF1=0.5;INDEL

    Returns:
        字典形式的 INFO 信息。

        有等号的字段：
            DP=30 -> {"DP": "30"}

        没有等号的 flag 字段：
            INDEL -> {"INDEL": "true"}
    """

    values = {}

    for item in info.split(";"):
        if not item:
            continue

        if "=" in item:
            key, value = item.split("=", 1)
            values[key] = value
        else:
            values[item] = "true"

    return values


def read_gene_intervals(gff: Path) -> list[dict[str, object]]:
    """从 GFF 中读取目标基因区间。

    当前逻辑只关心 TARGET_GENES 中的三个目标基因。
    它不会解析全部基因，而是在 GFF attributes 字段中查找目标基因 ID。

    Args:
        gff:
            GFF 注释文件路径。

    Returns:
        目标基因区间列表，每个元素包括：
        - chrom
        - start
        - end
        - gene_id

    如果 GFF 不存在，则返回空列表。
    """

    if not gff.exists():
        return []

    intervals = []

    with gff.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue

            fields = line.rstrip("\n").split("\t")

            # 标准 GFF 至少 9 列。
            if len(fields) < 9:
                continue

            chrom, _source, _feature, start, end, _score, _strand, _phase, attrs = fields

            # 从 attributes 字段中识别是否包含目标基因 ID。
            gene_id = target_gene_from_attributes(attrs)

            if not gene_id:
                continue

            intervals.append(
                {
                    "chrom": chrom,
                    "start": int(start),
                    "end": int(end),
                    "gene_id": gene_id,
                }
            )

    return intervals


def target_gene_from_attributes(attributes: str) -> str:
    """从 GFF attributes 字段中识别目标基因 ID。

    Args:
        attributes:
            GFF 第 9 列 attributes 字符串。

    Returns:
        如果 attributes 中包含 TARGET_GENES 中任意基因 ID，
        则返回该 gene_id；否则返回空字符串。

    注意：
        当前采用简单字符串包含匹配。
        对 mini 数据包和固定目标基因足够直接，
        但如果未来扩展到全基因组通用解析，可以改成更严格的 ID/Parent 字段解析。
    """

    for gene_id in TARGET_GENES:
        if gene_id in attributes:
            return gene_id

    return ""


def read_bed_intervals(path: Path) -> list[dict[str, object]]:
    """读取 BED 区间，并将 start 转为 1-based inclusive 坐标。

    Args:
        path:
            BED 文件路径。

    Returns:
        区间列表，每个元素包括：
        - chrom
        - start
        - end
        - name

    BED 坐标说明：
        BED start 通常是 0-based；
        VCF POS 通常是 1-based；
        为了后续和 VCF POS 比较，这里将 BED start + 1。
    """

    if not path.exists():
        return []

    intervals = []

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")

        for row in reader:
            if len(row) < 3:
                continue

            name = row[3] if len(row) > 3 else ""

            intervals.append(
                {
                    "chrom": row[0],
                    "start": int(row[1]) + 1,
                    "end": int(row[2]),
                    "name": name,
                }
            )

    return intervals


def annotate_gene_or_region(
    *,
    chrom: str,
    pos: int,
    gene_intervals: list[dict[str, object]],
    region_intervals: list[dict[str, object]],
) -> str:
    """给一个变异位点注释目标基因或候选区域名称。

    Args:
        chrom:
            变异所在染色体。

        pos:
            VCF POS，1-based 坐标。

        gene_intervals:
            从 GFF 读取到的目标基因区间。

        region_intervals:
            从 BED 读取到的候选区域区间。

    Returns:
        注释字符串：

        1. 如果变异落在某个目标基因区间内，返回 gene_id；
        2. 否则，如果变异落在某个候选区域内，返回 region name；
        3. 如果 region name 为空，则返回 "candidate_region"；
        4. 如果都匹配不到，返回空字符串。

    设计意图：
        优先标注具体目标基因；
        其次标注候选区域；
        避免无注释位点直接丢失上下文。
    """

    # 优先匹配目标基因区间。
    for interval in gene_intervals:
        if (
            interval["chrom"] == chrom
            and int(interval["start"]) <= pos <= int(interval["end"])
        ):
            return str(interval["gene_id"])

    # 如果没有落在目标基因内，再匹配候选区域。
    for interval in region_intervals:
        if (
            interval["chrom"] == chrom
            and int(interval["start"]) <= pos <= int(interval["end"])
        ):
            return str(interval.get("name") or "candidate_region")

    return ""


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """写出 TSV 文件。

    Args:
        path:
            输出 TSV 文件路径。

        fieldnames:
            表头列名。

        rows:
            待写出的记录列表。

    该函数会自动创建父目录。
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)