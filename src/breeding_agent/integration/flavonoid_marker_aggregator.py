"""Rule-based aggregation for foxtail millet flavonoid marker evidence.

本文件负责“谷子黄酮候选标记推荐”的规则化 evidence 聚合。

它属于 integration 层，也就是多组学 evidence 汇总层。

整体作用可以理解为：

evidence_dir/
    transcriptome_evidence.tsv
    metabolome_evidence.tsv
    annotation_evidence.tsv
    genome_variant_evidence.tsv
    literature_evidence.tsv
        ↓
可选接入 genomics_variant_calling 输出
        ↓
按固定目标基因 Si9g04210.1 / Si5g31340.1 / Si9g34380.1 聚合证据
        ↓
生成 flavonoid_marker_candidates.tsv
        ↓
返回 FlavonoidMarkerAggregationResult 给 agent / workflow / report 使用

注意：
这个模块是规则聚合器，不是机器学习模型。
它不会重新做 RNA-seq、代谢组、variant calling 或文献检索；
只读取已经准备好的 TSV evidence，并将它们整合成候选标记推荐表。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from breeding_agent.integration.flavonoid_variant_evidence import (
    FlavonoidVariantEvidenceResult,
    load_flavonoid_variant_evidence,
)


# 当前黄酮标记推荐任务固定要求出现的三个重点基因。
#
# 聚合器会围绕这三个基因生成候选行。
# 即使某些 evidence 缺失，也会保留对应 gene_id 的输出行，
# 并在 evidence_warnings 中说明缺失情况。
REQUIRED_GENE_IDS = ["Si9g04210.1", "Si5g31340.1", "Si9g34380.1"]


# evidence_dir 中预期存在的标准 evidence 文件名。
#
# 这些文件通常由 create_evidence_from_package() 或相关导入流程生成。
TRANSCRIPTOME_EVIDENCE = "transcriptome_evidence.tsv"
METABOLOME_EVIDENCE = "metabolome_evidence.tsv"
ANNOTATION_EVIDENCE = "annotation_evidence.tsv"
GENOME_VARIANT_EVIDENCE = "genome_variant_evidence.tsv"
LITERATURE_EVIDENCE = "literature_evidence.tsv"


# 聚合后的候选标记表文件名。
#
# 输出路径通常是：
# outdir / "integration" / "flavonoid_marker_candidates.tsv"
CANDIDATE_FILENAME = "flavonoid_marker_candidates.tsv"


# flavonoid_marker_candidates.tsv 的输出列。
#
# 这个表把每个目标基因的转录组、代谢组、注释、变异和标记推荐信息整合到一行。
CANDIDATE_COLUMNS = [
    # 目标基因 ID。
    "gene_id",

    # 转录组 DEG 证据。
    "baseMean",
    "log2FC",
    "pvalue",
    "padj",
    "Green_mean",
    "Golden_mean",
    "Direction",

    # 代谢组关联证据。
    "top_correlated_metabolite",
    "top_pearson_r",
    "top_spls_metabolite",

    # 功能注释证据。
    "function_annotation",
    "KEGG_ko",
    "KEGG_Pathway",
    "PFAMs",

    # 基因组变异状态。
    # genome_variant_evidence.tsv 中通常是 not_called，
    # 表示当前 mini 数据包未提供最终 SNP/InDel 位点。
    "variant_status",

    # 可选 candidate-region variant calling 结果状态。
    #
    # 如果接入 genomics_variant_calling 输出，可能出现：
    # - preliminary_pass_variants_detected
    # - only_low_quality_variants_detected
    # - no_called_variant_in_current_mini_calling
    "variant_evidence_status",

    # candidate-region variant calling 的数量统计。
    "total_variants",
    "pass_variants",
    "lowqual_variants",
    "snp_count",
    "indel_count",
    "pass_snp_count",
    "lowqual_snp_count",
    "kasp_preliminary_pass_count",
    "kasp_low_quality_review_required_count",
    "caps_pass_variant_requires_enzyme_screening_count",
    "caps_low_quality_variant_requires_review_count",

    # 当前模块根据 variant_status / variant_evidence_status 给出的推荐说明。
    "marker_recommendation",

    # 证据缺失或流程警告。
    "evidence_warnings",
]


# 当没有进行真实 variant calling 时的边界说明。
#
# 这段文字用于提醒：
# 当前 mini 数据包没有最终 SNP/InDel 位点，
# 后续需要基于 BAM + reference + GFF 做候选区域 SNP/InDel calling，
# 再判断是否能转化为 KASP/CAPS。
NOT_CALLED_VARIANT_NOTE = (
    "当前 mini 数据包未提供最终 SNP/InDel 位点；建议后续基于 BAM、genome.fa/"
    "genome.gff 或 genome.bam_compatible.fa.gz 与 genome.original_coords.gff "
    "进行候选区域 SNP/InDel calling，再筛选 KASP/CAPS 可转化位点。"
)


@dataclass(frozen=True)
class FlavonoidMarkerAggregationResult:
    """黄酮候选标记聚合结果对象。

    该对象是 aggregate_flavonoid_marker_candidates() 的返回值，
    会被 workflow、LangGraph 节点、报告生成器和 agent context builder 使用。

    Attributes:
        candidate_file:
            聚合后的候选标记表路径。

        candidate_rows:
            候选标记表中的记录列表。
            每个目标基因对应一条记录。

        literature_rows:
            literature_evidence.tsv 中读取到的文献证据行。
            后续 LiteratureAgent / report 会继续使用。

        warnings:
            运行过程中产生的 warning。
            例如 evidence 文件缺失、某个基因缺少某类证据等。

        variant_evidence_rows:
            从可选 variant_calling_dir 中读取并汇总出的变异 evidence 行。

        variant_calling_dir:
            当前接入的 candidate-region variant calling 输出目录。
            如果没有接入，则为 None。
    """

    candidate_file: Path
    candidate_rows: list[dict[str, str]]
    literature_rows: list[dict[str, str]]
    warnings: list[str]
    variant_evidence_rows: list[dict[str, str]]
    variant_calling_dir: Path | None


def aggregate_flavonoid_marker_candidates(
    *,
    evidence_dir: Path,
    outdir: Path,
    variant_calling_dir: Path | None = None,
) -> FlavonoidMarkerAggregationResult:
    """将标准 evidence 文件聚合为固定目标基因候选标记表。

    这是本文件的核心公开函数。

    主流程：

    1. 创建 outdir/integration 输出目录；
    2. 读取 transcriptome_evidence.tsv；
    3. 读取 metabolome_evidence.tsv；
    4. 读取 annotation_evidence.tsv；
    5. 读取 genome_variant_evidence.tsv；
    6. 读取 literature_evidence.tsv；
    7. 可选读取 genomics_variant_calling 输出；
    8. 围绕 REQUIRED_GENE_IDS 逐个构建 candidate row；
    9. 写出 flavonoid_marker_candidates.tsv；
    10. 返回 FlavonoidMarkerAggregationResult。

    Args:
        evidence_dir:
            evidence 文件目录。

        outdir:
            聚合结果输出根目录。

        variant_calling_dir:
            可选 candidate-region variant calling 输出目录。
            如果提供，会读取其中的候选变异统计结果并接入推荐说明。

    Returns:
        FlavonoidMarkerAggregationResult:
            聚合后的候选文件、候选行、文献行、warnings 和变异 evidence。
    """

    # integration_dir 是候选标记表输出目录。
    integration_dir = outdir / "integration"
    integration_dir.mkdir(parents=True, exist_ok=True)

    # warnings 用于累计全流程警告。
    # 注意：这个 warnings 会被写入每个候选行的 evidence_warnings，
    # 也会返回给 workflow / report 层。
    warnings: list[str] = []

    # 读取转录组 evidence，并按 gene_id 建索引。
    transcriptome_rows = _read_gene_evidence(
        evidence_dir / TRANSCRIPTOME_EVIDENCE,
        warnings=warnings,
    )

    # 读取代谢组 evidence，并按 gene_id 建索引。
    metabolome_rows = _read_gene_evidence(
        evidence_dir / METABOLOME_EVIDENCE,
        warnings=warnings,
    )

    # 读取功能注释 evidence，并按 gene_id 建索引。
    annotation_rows = _read_gene_evidence(
        evidence_dir / ANNOTATION_EVIDENCE,
        warnings=warnings,
    )

    # 读取 genome_variant_evidence.tsv。
    #
    # 这个文件通常来自 package importer，
    # 当前常见状态是 variant_status=not_called。
    variant_rows = _read_gene_evidence(
        evidence_dir / GENOME_VARIANT_EVIDENCE,
        warnings=warnings,
    )

    # 读取文献 evidence。
    #
    # 文献 evidence 不按 gene_id 建索引，
    # 因为它可能是背景文献、方法文献或通路文献。
    literature_rows = _read_evidence_rows(
        evidence_dir / LITERATURE_EVIDENCE,
        warnings=warnings,
    )

    # 可选读取 candidate-region variant calling 输出。
    #
    # 如果 variant_calling_dir 为 None，则返回空结果；
    # 如果提供路径，则交给 load_flavonoid_variant_evidence() 读取和汇总。
    variant_evidence_result = _load_optional_variant_evidence(
        variant_calling_dir=variant_calling_dir,
        warnings=warnings,
    )

    # 将 variant evidence 按 gene_id 建索引。
    variant_evidence_rows = {
        row["gene_id"]: row
        for row in variant_evidence_result.rows
        if row.get("gene_id")
    }

    # 固定围绕 REQUIRED_GENE_IDS 构建候选行。
    #
    # 每个 gene_id 都会输出一行；
    # 缺失 evidence 的部分用空字符串补齐，并在 evidence_warnings 中提示。
    candidate_rows = [
        _candidate_row(
            gene_id=gene_id,
            transcriptome=transcriptome_rows.get(gene_id, {}),
            metabolome=metabolome_rows.get(gene_id, {}),
            annotation=annotation_rows.get(gene_id, {}),
            variant=variant_rows.get(gene_id, {}),
            variant_evidence=variant_evidence_rows.get(gene_id, {}),
            warnings=warnings,
        )
        for gene_id in REQUIRED_GENE_IDS
    ]

    # 写出候选标记表。
    candidate_file = integration_dir / CANDIDATE_FILENAME
    _write_tsv(candidate_file, CANDIDATE_COLUMNS, candidate_rows)

    return FlavonoidMarkerAggregationResult(
        candidate_file=candidate_file,
        candidate_rows=candidate_rows,
        literature_rows=literature_rows,
        warnings=warnings,
        variant_evidence_rows=variant_evidence_result.rows,
        variant_calling_dir=variant_calling_dir,
    )


def read_flavonoid_marker_candidates(candidate_file: Path) -> list[dict[str, str]]:
    """读取已经聚合好的黄酮候选标记表。

    Args:
        candidate_file:
            flavonoid_marker_candidates.tsv 路径。

    Returns:
        候选标记记录列表。

    用途：
        报告生成器、测试或其他模块可以通过该函数读取候选表。
    """

    return _read_evidence_rows(candidate_file, warnings=[])


def read_literature_evidence(evidence_dir: Path) -> list[dict[str, str]]:
    """读取 literature_evidence.tsv。

    Args:
        evidence_dir:
            evidence 文件目录。

    Returns:
        文献 evidence 行列表。

    如果文件不存在，当前函数不会向外暴露 warning，
    因为这里传入的是独立的空 warnings 列表。
    """

    return _read_evidence_rows(evidence_dir / LITERATURE_EVIDENCE, warnings=[])


def _read_gene_evidence(
    path: Path,
    *,
    warnings: list[str],
) -> dict[str, dict[str, str]]:
    """读取按 gene_id 组织的 evidence 文件，并建立 gene_id -> row 映射。

    Args:
        path:
            evidence TSV 文件路径。

        warnings:
            用于累计读取过程中的 warning。

    Returns:
        以 gene_id 为 key 的字典。

    注意：
        输入文件必须有 gene_id 列。
        如果某行 gene_id 为空，则会被忽略。
    """

    rows = _read_evidence_rows(path, warnings=warnings)

    return {
        row["gene_id"].strip(): row
        for row in rows
        if row.get("gene_id", "").strip()
    }


def _read_evidence_rows(path: Path, *, warnings: list[str]) -> list[dict[str, str]]:
    """读取 TSV evidence 文件。

    Args:
        path:
            evidence 文件路径。

        warnings:
            用于累计缺失文件或路径异常的 warning。

    Returns:
        TSV 记录列表，每行是一个 dict。

    读取策略：
        - 如果文件不存在，添加 warning 并返回空列表；
        - 如果路径不是文件，添加 warning 并返回空列表；
        - 如果文件存在，则按 tab 分隔读取为 DictReader。
    """

    if not path.exists():
        warnings.append(f"Evidence file missing: {path}")
        return []

    if not path.is_file():
        warnings.append(f"Evidence path is not a file: {path}")
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _candidate_row(
    *,
    gene_id: str,
    transcriptome: dict[str, str],
    metabolome: dict[str, str],
    annotation: dict[str, str],
    variant: dict[str, str],
    variant_evidence: dict[str, str],
    warnings: list[str],
) -> dict[str, str]:
    """构建单个目标基因的候选标记推荐行。

    Args:
        gene_id:
            当前目标基因 ID。

        transcriptome:
            当前基因的转录组 evidence 行。

        metabolome:
            当前基因的代谢组 evidence 行。

        annotation:
            当前基因的功能注释 evidence 行。

        variant:
            当前基因的 genome_variant_evidence 行。
            通常包含 variant_status。

        variant_evidence:
            从 candidate-region variant calling 输出中汇总出的变异 evidence 行。

        warnings:
            全局 warning 列表。

    Returns:
        flavonoid_marker_candidates.tsv 中的一行。

    聚合逻辑：
        - 转录组字段从 transcriptome 中取；
        - 代谢组字段从 metabolome 中取；
        - 注释字段从 annotation 中取；
        - 基因组 variant_status 从 variant 中取；
        - 真实 variant calling 统计从 variant_evidence 中取；
        - marker_recommendation 根据 variant_status 和 variant_evidence_status 生成；
        - evidence_warnings 合并全局 warnings 和当前 gene 的缺失 evidence warnings。
    """

    # 如果 genome_variant_evidence 缺失，默认 variant_status=not_called。
    variant_status = _value(variant, "variant_status", default="not_called")

    # 可选 variant calling evidence 状态。
    # 如果没有接入 variant_calling_dir，通常为空。
    variant_evidence_status = _value(variant_evidence, "variant_evidence_status")

    # 根据变异状态生成推荐说明。
    marker_recommendation = _marker_recommendation(
        variant_status=variant_status,
        variant_evidence_status=variant_evidence_status,
    )

    # 当前 gene 级别的 evidence 缺失 warning。
    row_warnings = _row_warnings(
        gene_id=gene_id,
        transcriptome=transcriptome,
        metabolome=metabolome,
        annotation=annotation,
        variant=variant,
    )

    return {
        "gene_id": gene_id,

        # 转录组 DEG 证据。
        "baseMean": _value(transcriptome, "baseMean"),
        "log2FC": _value(transcriptome, "log2FC"),
        "pvalue": _value(transcriptome, "pvalue"),
        "padj": _value(transcriptome, "padj"),
        "Green_mean": _value(transcriptome, "Green_mean"),
        "Golden_mean": _value(transcriptome, "Golden_mean"),
        "Direction": _value(transcriptome, "Direction"),

        # 代谢组关联证据。
        "top_correlated_metabolite": _value(
            metabolome,
            "top_correlated_metabolite",
        ),
        "top_pearson_r": _value(metabolome, "top_pearson_r"),
        "top_spls_metabolite": _value(metabolome, "top_spls_metabolite"),

        # 功能注释证据。
        "function_annotation": _value(annotation, "Description"),
        "KEGG_ko": _value(annotation, "KEGG_ko"),
        "KEGG_Pathway": _value(annotation, "KEGG_Pathway"),
        "PFAMs": _value(annotation, "PFAMs"),

        # 基因组变异状态。
        "variant_status": variant_status,
        "variant_evidence_status": variant_evidence_status,

        # candidate-region variant calling 数量统计。
        "total_variants": _value(variant_evidence, "total_variants"),
        "pass_variants": _value(variant_evidence, "pass_variants"),
        "lowqual_variants": _value(variant_evidence, "lowqual_variants"),
        "snp_count": _value(variant_evidence, "snp_count"),
        "indel_count": _value(variant_evidence, "indel_count"),
        "pass_snp_count": _value(variant_evidence, "pass_snp_count"),
        "lowqual_snp_count": _value(variant_evidence, "lowqual_snp_count"),
        "kasp_preliminary_pass_count": _value(
            variant_evidence,
            "kasp_preliminary_pass_count",
        ),
        "kasp_low_quality_review_required_count": _value(
            variant_evidence,
            "kasp_low_quality_review_required_count",
        ),
        "caps_pass_variant_requires_enzyme_screening_count": _value(
            variant_evidence,
            "caps_pass_variant_requires_enzyme_screening_count",
        ),
        "caps_low_quality_variant_requires_review_count": _value(
            variant_evidence,
            "caps_low_quality_variant_requires_review_count",
        ),

        # 根据 variant 状态生成的人类可读推荐。
        "marker_recommendation": marker_recommendation,

        # 全局 warnings + 当前 gene evidence 缺失 warnings。
        "evidence_warnings": "; ".join([*warnings, *row_warnings]),
    }


def _marker_recommendation(
    *,
    variant_status: str,
    variant_evidence_status: str,
) -> str:
    """根据变异检测状态生成候选标记推荐说明。

    Args:
        variant_status:
            来自 genome_variant_evidence.tsv 的状态。
            常见值是 not_called。

        variant_evidence_status:
            来自 candidate-region variant calling 汇总结果的状态。
            常见值包括：
            - preliminary_pass_variants_detected
            - only_low_quality_variants_detected
            - no_called_variant_in_current_mini_calling
            - 空字符串

    Returns:
        针对当前基因的 marker recommendation 文本。

    重要边界：
        这里输出的是“候选推荐说明”，不是最终标记开发结论。
        即使存在 PASS variant，也仍需 flanking sequence、覆盖度、群体验证等后续复核。
    """

    # 已检测到真实 VCF PASS variant。
    # 可以优先复核 PASS SNP 的 KASP 转化潜力，
    # 但仍不能声称已经完成 KASP 标记开发。
    if variant_evidence_status == "preliminary_pass_variants_detected":
        return (
            "候选区域已有真实 VCF PASS variant；可优先复核 PASS SNP 的 KASP "
            "转化潜力，并继续检查 flanking sequence、覆盖度和群体验证。"
        )

    # 只检测到 LowQual variant。
    # 不应优先用于 KASP/CAPS 开发，需要先复核质量。
    if variant_evidence_status == "only_low_quality_variants_detected":
        return (
            "候选区域仅检出 LowQual variant；不应优先用于 KASP/CAPS 开发，"
            "需先人工复核覆盖度、质量和 flanking sequence。"
        )

    # 当前 mini calling 未检出 called variant。
    # 这不等于没有变异，只能说明当前 mini 数据/区域/阈值下未检出。
    if variant_evidence_status == "no_called_variant_in_current_mini_calling":
        return (
            "当前 mini calling 未检出 called variant；建议扩大候选区域、增加样本，"
            "或使用 WGS/GBS 数据继续检测。"
        )

    # 还没有做 variant calling。
    # 这是 genome_region 阶段最常见的状态。
    if variant_status == "not_called":
        return (
            "variant_status=not_called; 先进行候选区域 SNP/InDel calling。获得可靠"
            "多态位点后，优先将高质量 SNP/InDel 转化为 KASP 标记；若变异影响"
            "限制性内切酶识别位点，可补充开发 CAPS 标记。"
        )

    # 兜底说明。
    return (
        "优先评估已 calling 的 SNP/InDel 位点；选择高置信、与黄酮表型相关的"
        "位点开发 KASP 标记，并筛选可设计限制性酶切实验的 CAPS 标记。"
    )


def _load_optional_variant_evidence(
    *,
    variant_calling_dir: Path | None,
    warnings: list[str],
) -> FlavonoidVariantEvidenceResult:
    """可选读取 candidate-region variant calling evidence。

    Args:
        variant_calling_dir:
            genomics_variant_calling 输出目录。
            如果为 None，表示当前流程不接入真实 variant calling 结果。

        warnings:
            用于累计读取过程中的 warning。

    Returns:
        FlavonoidVariantEvidenceResult。

    行为：
        - variant_calling_dir is None：
          返回 loaded=False、rows=[] 的空结果；
        - variant_calling_dir 有值：
          调用 load_flavonoid_variant_evidence() 读取变异 evidence，
          并把其 warnings 合并到当前 warnings。
    """

    if variant_calling_dir is None:
        return FlavonoidVariantEvidenceResult(
            variant_calling_dir=Path(""),
            rows=[],
            warnings=[],
            loaded=False,
        )

    result = load_flavonoid_variant_evidence(variant_calling_dir)
    warnings.extend(result.warnings)
    return result


def _row_warnings(
    *,
    gene_id: str,
    transcriptome: dict[str, str],
    metabolome: dict[str, str],
    annotation: dict[str, str],
    variant: dict[str, str],
) -> list[str]:
    """生成单个基因层面的 evidence 缺失 warning。

    Args:
        gene_id:
            当前目标基因。

        transcriptome:
            转录组 evidence 行。

        metabolome:
            代谢组 evidence 行。

        annotation:
            注释 evidence 行。

        variant:
            genome variant evidence 行。

    Returns:
        当前基因缺失 evidence 的 warning 列表。

    例如：
        transcriptome evidence missing for Si9g04210.1
    """

    warnings = []

    evidence_by_name = {
        "transcriptome": transcriptome,
        "metabolome": metabolome,
        "annotation": annotation,
        "genome_variant": variant,
    }

    for evidence_name, row in evidence_by_name.items():
        if not row:
            warnings.append(f"{evidence_name} evidence missing for {gene_id}")

    return warnings


def _value(row: dict[str, str], key: str, *, default: str = "") -> str:
    """安全读取字段值并去除首尾空白。

    Args:
        row:
            evidence 行。

        key:
            字段名。

        default:
            字段不存在或值为 None 时使用的默认值。

    Returns:
        清理后的字符串值。

    设计目的：
        不让缺失字段导致 KeyError；
        保证写入 TSV 的值都是字符串。
    """

    value = row.get(key, default)
    if value is None:
        return default
    return value.strip()


def _write_tsv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    """写出 TSV 文件。

    Args:
        path:
            输出 TSV 文件路径。

        fieldnames:
            表头字段列表。

        rows:
            待写出的记录列表。

    当前主要用于写出：
        flavonoid_marker_candidates.tsv
    """

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)