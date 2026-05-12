"""Genomics region and annotation analysis from the mini package.

本文件负责从 mini flavonoid package 中整理“基因组候选区域与注释证据”。

它属于 modules 层，也就是“具体业务处理层”：
- workflows/genomics_region.py 负责调度；
- 本文件负责真正读取数据包中的 regions、GFF 派生表、注释表，并生成结构化结果 target_gene_regions.tsv、annotation_summary.tsv、marker_readiness.tsv；
- 明确当前 variant_status = not_called，提示后续需要 candidate-region SNP/InDel calling
- 当前这个模块只完成 候选区域和注释证据整理，还没有真正从 BAM 里检测 SNP/InDel 变异位点，所以每个目标基因的 variant_status 必须标记为 not_called
- reports/genomics_report.py 负责把这里返回的 analysis_result 渲染成 Markdown 报告；
- Gradio 页面只负责调用 workflow 并展示这里产出的表格和报告。

当前模块的定位是：

1. 整理目标基因对应的候选区域；
2. 整理目标基因功能注释；
3. 给出 marker readiness 初步判断；
4. 明确提示当前还没有最终 SNP/InDel 位点；
5. 为后续候选区域 variant calling 提供输入和说明。

注意：
当前 genomics_region.py 不等同于真正 GWAS；
也不执行 WGS/GBS 群体变异检测；
也不直接设计最终 KASP/CAPS 标记。
它只是把 mini 数据包中已有的候选区域和注释证据整理为可展示、可追踪的 evidence 表。
"""

from __future__ import annotations

import csv
from pathlib import Path


# 当前谷子黄酮候选标记任务中固定关注的三个重点基因。
#
# 这三个基因会在：
# - annotation_summary.tsv
# - marker_readiness.tsv
# - target_gene_regions.tsv
# 中被优先展示或补齐。
TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")


# 输入文件清单。
#
# key 是模块内部使用的逻辑名称；
# value 是相对于 dataset_dir 的路径。
#
# 例如：
# dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
#
# 那么：
# INPUT_FILES["regions_bed"] 对应：
# data/private/flavonoid_marker_mini_5genes_50kb/regions/regions.bed
#
# 注意：
# 这里列出的文件并非都会被完整解析。
# 有些文件用于完整性检查和 source_file 记录，
# 有些文件则用于实际构建输出表。
INPUT_FILES = {
    # 原始参考基因组 FASTA。
    # 当前 genomics_region 模块只检查它是否存在，不从 FASTA 中重新提取序列。
    "genome_fasta": Path("genome.fa"),

    # 普通 GFF 注释文件。
    # 当前模块不直接解析它，而是优先使用已经准备好的 deg_features.tsv 和注释 TSV。
    "genome_gff": Path("genome.gff"),

    # 原始坐标体系下的 GFF。
    # 后续 variant calling 或坐标解释时更重要。
    "genome_original_coords_gff": Path("genome.original_coords.gff"),

    # 与 BAM 文件兼容的参考基因组 FASTA。
    # 通常用于后续候选区域变异检测。
    "genome_bam_compatible_fasta": Path("genome.bam_compatible.fa.gz"),

    # 候选区域 BED 文件。
    # 用于表示需要关注的基因组区间。
    "regions_bed": Path("regions") / "regions.bed",

    # samtools 风格的区域字符串文件。
    # 例如 chr:start-end，用于后续按区域提取 BAM/VCF。
    "regions_samtools": Path("regions") / "regions.samtools.txt",

    # DEG 特征与候选区域映射表。
    # 该文件通常是从 GFF/候选基因附近区域预处理得到的。
    # _target_gene_regions() 主要读取这个文件来构建 target_gene_regions.tsv。
    "deg_features": Path("regions") / "deg_features.tsv",

    # 目标基因列表。
    # 当前模块固定使用 TARGET_GENES，但该文件仍被纳入输入完整性检查。
    "target_genes": Path("target_genes.tsv"),

    # 局部区域 emapper 注释。
    # 当前模块只检查是否存在，不直接用于 annotation_summary 的主逻辑。
    "local_region_emapper_annotations": (
        Path("annotations") / "local_region_emapper_annotations.tsv"
    ),

    # 目标基因 emapper 注释。
    # annotation_summary 优先读取该文件。
    "target_gene_emapper_annotations": (
        Path("annotations") / "target_gene_emapper_annotations.tsv"
    ),

    # 目标基因综合证据摘要。
    # 如果 target_gene_emapper_annotations.tsv 不存在或为空，
    # annotation_summary 会回退读取该文件。
    "target_gene_evidence_summary": (
        Path("annotations") / "target_gene_evidence_summary.tsv"
    ),
}


# target_gene_regions.tsv 的输出列。
#
# 这个表用于展示每个目标基因/解析后的 feature 与候选 region 的对应关系。
TARGET_GENE_REGION_COLUMNS = [
    "gene_id",
    "resolved_id",
    "resolved_type",
    "chrom",
    "start",
    "end",
    "strand",
    "region_chrom",
    "region_start",
    "region_end",
    "region_name",
    "region_samtools",
    "source_file",
]

# annotation_summary.tsv 的输出列。
#
# 这个表用于展示目标基因的功能注释信息。
ANNOTATION_SUMMARY_COLUMNS = [
    "gene_id",
    "Description",
    "Preferred_name",
    "KEGG_ko",
    "KEGG_Pathway",
    "PFAMs",
    "source_file",
]

# marker_readiness.tsv 的输出列。
#
# 这个表用于说明当前是否已经具备进入标记开发/变异检测的条件。
# 注意它不是最终标记结果，只是 readiness 判断。
MARKER_READINESS_COLUMNS = [
    "gene_id",
    "variant_status",
    "candidate_marker_types",
    "readiness_summary",
    "required_next_step",
    "source_file",
]


# 对当前 genomics region 模块的边界说明。
#
# 当前 mini 数据包只提供候选区域和注释证据，
# 还没有真正的 SNP/InDel calling 结果。
# 因此需要在报告和 readiness 表里明确说明：
# 后续要基于 BAM、参考基因组、GFF 和候选区域执行 variant calling，
# 再筛选 KASP/CAPS 可转化位点。
VARIANT_NEXT_STEP = (
    "当前 mini 数据包未提供最终 SNP/InDel 位点；后续需要基于 BAM、"
    "genome.fa/genome.gff 或 genome.bam_compatible.fa.gz 与 "
    "genome.original_coords.gff 进行候选区域 SNP/InDel calling，再筛选 "
    "KASP/CAPS 可转化位点。"
)


def build_genomics_region_analysis(
    *,
    dataset_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    """构建基因组候选区域、功能注释和 marker readiness 表。

    这是本模块的核心函数。

    它主要完成三类输出：

    1. target_gene_regions.tsv
       - 根据 regions/deg_features.tsv、regions.bed、regions.samtools.txt
         整理目标基因所在候选区域；
       - 用于展示候选基因和候选区域之间的对应关系。

    2. annotation_summary.tsv
       - 优先读取 annotations/target_gene_emapper_annotations.tsv；
       - 如果该文件为空，则回退读取 annotations/target_gene_evidence_summary.tsv；
       - 提取 Description、Preferred_name、KEGG、PFAM 等功能注释。

    3. marker_readiness.tsv
       - 对每个 TARGET_GENES 生成一行 readiness 说明；
       - 明确当前 variant_status = not_called；
       - 说明候选 marker 类型可以考虑 SNP/InDel/KASP/CAPS；
       - 但后续必须做候选区域 SNP/InDel calling。

    Args:
        dataset_dir:
            输入数据包目录。

            典型路径：
            data/private/flavonoid_marker_mini_5genes_50kb

        output_dir:
            输出目录。

            典型路径：
            outputs/gradio_genomics_run/genomics

    Returns:
        一个结构化结果字典，供 workflow 层写入 manifest，
        并供 report 层生成 genomics_report.md。

        主要字段包括：
        - task_name
        - dataset_dir
        - output_dir
        - inputs
        - outputs
        - row_counts
        - warnings
        - target_genes
        - target_regions
        - annotation_summary
        - marker_readiness
    """

    # 确保输出目录存在。
    output_dir.mkdir(parents=True, exist_ok=True)

    # 检查 INPUT_FILES 中列出的文件是否存在。
    # 缺失项不会直接中断流程，而是进入 warnings。
    warnings = _missing_input_warnings(dataset_dir)

    # 生成每个输入文件的状态记录：
    # - path
    # - exists
    input_status = _input_status(dataset_dir)

    # 构建目标基因候选区域表。
    target_regions = _target_gene_regions(dataset_dir)

    # 构建目标基因注释摘要表。
    annotation_summary = _annotation_summary(dataset_dir)

    # 构建 marker readiness 表。
    marker_readiness = _marker_readiness(dataset_dir)

    # 定义三个输出文件路径。
    target_regions_file = output_dir / "target_gene_regions.tsv"
    annotation_summary_file = output_dir / "annotation_summary.tsv"
    marker_readiness_file = output_dir / "marker_readiness.tsv"

    # 写出 TSV 文件。
    _write_tsv(target_regions_file, TARGET_GENE_REGION_COLUMNS, target_regions)
    _write_tsv(annotation_summary_file, ANNOTATION_SUMMARY_COLUMNS, annotation_summary)
    _write_tsv(marker_readiness_file, MARKER_READINESS_COLUMNS, marker_readiness)

    # 返回结构化分析结果。
    # workflow 层会把其中的 outputs、row_counts、warnings 写入 manifest.json；
    # report 层会读取 target_regions、annotation_summary、marker_readiness 生成报告。
    return {
        "task_name": "genomics_region",
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "inputs": input_status,
        "outputs": {
            "target_gene_regions": str(target_regions_file),
            "annotation_summary": str(annotation_summary_file),
            "marker_readiness": str(marker_readiness_file),
        },
        "row_counts": {
            "target_gene_regions": len(target_regions),
            "annotation_summary": len(annotation_summary),
            "marker_readiness": len(marker_readiness),
        },
        "warnings": warnings,
        "target_genes": list(TARGET_GENES),
        "target_regions": target_regions,
        "annotation_summary": annotation_summary,
        "marker_readiness": marker_readiness,
    }


def _missing_input_warnings(dataset_dir: Path) -> list[str]:
    """检查输入数据包中哪些预期文件缺失。

    Args:
        dataset_dir:
            输入数据包根目录。

    Returns:
        warnings:
            缺失文件提示列表。

    注意：
        该函数只生成 warning，不抛出异常。
        因为当前模块希望尽可能展示已有证据，
        即使某些辅助文件缺失，也不一定需要整个流程失败。
    """

    warnings = []
    for relative_path in INPUT_FILES.values():
        path = dataset_dir / relative_path
        if not path.exists():
            warnings.append(f"Input file missing: {path}")
    return warnings


def _input_status(dataset_dir: Path) -> dict[str, dict[str, object]]:
    """生成输入文件状态表。

    该函数会记录每个输入文件：

    - 实际路径；
    - 是否存在。

    这些信息最终会进入 result["inputs"]，
    再由 workflow 层写入 manifest.json，
    方便后续排查数据包是否完整。

    Args:
        dataset_dir:
            输入数据包根目录。

    Returns:
        嵌套字典，例如：

        {
            "genome_fasta": {
                "path": ".../genome.fa",
                "exists": True
            },
            ...
        }
    """

    status = {}
    for key, relative_path in INPUT_FILES.items():
        path = dataset_dir / relative_path
        status[key] = {
            "path": str(path),
            "exists": path.exists(),
        }
    return status


def _target_gene_regions(dataset_dir: Path) -> list[dict[str, str]]:
    """构建目标基因与候选区域的对应表。

    数据来源：

    1. regions/deg_features.tsv
       - 提供 DEG 或目标基因在基因组上的 feature 信息；
       - 包括 deg_id、resolved_id、resolved_type、chrom、start、end、strand 等。

    2. regions/regions.bed
       - 提供候选区域 BED 区间；
       - 用于判断某个 feature 落在哪个候选区域中。

    3. regions/regions.samtools.txt
       - 提供 samtools 风格区域字符串；
       - 例如 chr:start-end；
       - 用于后续候选区域变异检测时按区域调用。

    如果 deg_features.tsv 缺失或没有有效行，
    函数会退回使用 TARGET_GENES 生成空坐标记录，
    以保证输出表结构稳定，三个目标基因仍然可见。

    Returns:
        target_gene_regions 记录列表。
    """

    # deg_features.tsv 是主输入，用于获取每个基因/feature 的坐标信息。
    deg_features_path = dataset_dir / INPUT_FILES["deg_features"]

    # 读取 deg_features.tsv。
    features = _read_dict_rows(deg_features_path)

    # 只保留存在 deg_id 或 resolved_id 的行。
    feature_rows = [
        row for row in features if row.get("deg_id") or row.get("resolved_id")
    ]

    # 读取 BED 候选区域。
    regions = _read_bed_rows(dataset_dir / INPUT_FILES["regions_bed"])

    # 读取 samtools 风格区域字符串。
    samtools_regions = _read_lines(dataset_dir / INPUT_FILES["regions_samtools"])

    # 如果 deg_features.tsv 不存在、为空或没有有效行，
    # 则使用 TARGET_GENES 构造占位记录。
    #
    # 这样 Gradio 和报告中仍然可以看到固定三个重点基因，
    # 但坐标和区域字段为空。
    if not feature_rows:
        feature_rows = [
            {
                "deg_id": gene_id,
                "resolved_id": gene_id,
                "resolved_type": "",
                "chrom": "",
                "start": "",
                "end": "",
                "strand": "",
            }
            for gene_id in TARGET_GENES
        ]

    output = []
    for row in feature_rows:
        # gene_id 优先使用 deg_id；
        # 如果 deg_id 为空，则回退到 resolved_id。
        gene_id = row.get("deg_id") or row.get("resolved_id") or ""

        # 将 feature 坐标匹配到对应 BED region。
        matched_region, region_index = _match_region(row, regions)

        output.append(
            {
                "gene_id": gene_id,
                "resolved_id": row.get("resolved_id", ""),
                "resolved_type": row.get("resolved_type", ""),
                "chrom": row.get("chrom", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "strand": row.get("strand", ""),

                # 匹配到的 BED 区域信息。
                "region_chrom": matched_region.get("chrom", ""),
                "region_start": matched_region.get("start", ""),
                "region_end": matched_region.get("end", ""),
                "region_name": matched_region.get("name", ""),

                # 与 BED region 同索引的 samtools 区域字符串。
                # 如果没有匹配到区域，或索引越界，则为空。
                "region_samtools": (
                    samtools_regions[region_index]
                    if 0 <= region_index < len(samtools_regions)
                    else ""
                ),

                # 记录该信息来源于哪个文件，便于追溯。
                "source_file": str(deg_features_path),
            }
        )
    return output


def _annotation_summary(dataset_dir: Path) -> list[dict[str, str]]:
    """构建目标基因功能注释摘要表。

    优先读取：

    annotations/target_gene_emapper_annotations.tsv

    如果该文件不存在或读取结果为空，则回退读取：

    annotations/target_gene_evidence_summary.tsv

    输出字段包括：
    - gene_id
    - Description
    - Preferred_name
    - KEGG_ko
    - KEGG_Pathway
    - PFAMs
    - source_file

    函数最后会检查 TARGET_GENES 是否都已经出现；
    如果某个目标基因没有注释行，会补一行空注释，
    保证三个重点基因在输出表中都能显示。
    """

    # 优先读取 target_gene_emapper_annotations.tsv。
    annotation_path = dataset_dir / INPUT_FILES["target_gene_emapper_annotations"]
    rows = _read_dict_rows(annotation_path)

    # 如果优先注释文件为空，则回退到 target_gene_evidence_summary.tsv。
    if not rows:
        annotation_path = dataset_dir / INPUT_FILES["target_gene_evidence_summary"]
        rows = _read_dict_rows(annotation_path)

    output = []

    # seen 用于记录已经出现在注释结果中的 gene_id。
    seen: set[str] = set()

    for row in rows:
        # 不同来源文件中基因 ID 字段名可能不同：
        # - emapper 注释中可能叫 query；
        # - evidence summary 中可能叫 Gene。
        gene_id = row.get("query") or row.get("Gene") or ""
        if not gene_id:
            continue

        seen.add(gene_id)

        output.append(
            {
                "gene_id": gene_id,
                "Description": row.get("Description", ""),
                "Preferred_name": row.get("Preferred_name", ""),
                "KEGG_ko": row.get("KEGG_ko", ""),
                "KEGG_Pathway": row.get("KEGG_Pathway", ""),
                "PFAMs": row.get("PFAMs", ""),
                "source_file": str(annotation_path),
            }
        )

    # 确保固定三个重点基因都出现在 annotation_summary.tsv 中。
    # 如果某个基因没有注释，就补空行。
    for gene_id in TARGET_GENES:
        if gene_id not in seen:
            output.append(
                {
                    "gene_id": gene_id,
                    "Description": "",
                    "Preferred_name": "",
                    "KEGG_ko": "",
                    "KEGG_Pathway": "",
                    "PFAMs": "",
                    "source_file": str(annotation_path),
                }
            )
    return output


def _marker_readiness(dataset_dir: Path) -> list[dict[str, str]]:
    """构建 marker readiness 表。

    当前函数不会做真实 variant calling，
    而是基于数据包中已有的候选区域、注释和参考文件情况，
    为每个目标基因生成一条“是否具备进入下一步标记开发”的说明。

    当前所有目标基因的 variant_status 都是：

    not_called

    这表示：
    - 当前 genomics_region 模块还没有得到最终 SNP/InDel 位点；
    - 只能说明已有候选区域和注释证据；
    - 后续仍需运行 candidate-region variant calling；
    - 再根据 PASS SNP/InDel 初筛 KASP/CAPS 可转化位点。

    Returns:
        marker_readiness 记录列表。
    """

    # source_file 不是单个文件，而是把支撑 readiness 判断的几个关键输入拼接起来。
    # 这样报告中可以看到 readiness 判断依赖哪些数据来源。
    source_file = " + ".join(
        [
            str(dataset_dir / INPUT_FILES["regions_bed"]),
            str(dataset_dir / INPUT_FILES["target_gene_emapper_annotations"]),
            str(dataset_dir / INPUT_FILES["genome_bam_compatible_fasta"]),
            str(dataset_dir / INPUT_FILES["genome_original_coords_gff"]),
        ]
    )

    return [
        {
            "gene_id": gene_id,

            # 明确说明当前还没有完成 variant calling。
            "variant_status": "not_called",

            # 从业务角度，后续潜在可开发的标记类型包括这些。
            # 但这里只是候选方向，不是最终位点。
            "candidate_marker_types": "SNP/InDel/KASP/CAPS",

            # 当前 readiness 的人类可读摘要。
            "readiness_summary": (
                "已有候选区域和功能注释证据，可进入候选区域变异检测设计；"
                "尚不能输出正式标记位点。"
            ),

            # 必须补充的下一步。
            "required_next_step": VARIANT_NEXT_STEP,

            # 支撑该 readiness 判断的数据来源。
            "source_file": source_file,
        }
        for gene_id in TARGET_GENES
    ]


def _read_dict_rows(path: Path) -> list[dict[str, str]]:
    """以字典形式读取 TSV 文件。

    Args:
        path:
            TSV 文件路径。

    Returns:
        每一行对应一个 dict：
        - key 为表头列名；
        - value 为该行对应列的字符串值。

    如果文件不存在，则返回空列表。
    """

    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _read_bed_rows(path: Path) -> list[dict[str, str]]:
    """读取 BED 文件并转换为字典列表。

    BED 文件至少应包含三列：

    1. chrom
    2. start
    3. end

    如果存在第 4 列，则作为 name；
    如果没有第 4 列，则 name 为空字符串。

    注意：
        BED 的 start 通常是 0-based；
        后续 _match_region() 中会把 region start 转为 1-based 再与 feature start 比较。

    Args:
        path:
            BED 文件路径。

    Returns:
        BED 区域记录列表。
    """

    if not path.exists():
        return []

    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            # 少于三列不是合法 BED 区间，直接跳过。
            if len(row) < 3:
                continue

            rows.append(
                {
                    "chrom": row[0],
                    "start": row[1],
                    "end": row[2],
                    "name": row[3] if len(row) > 3 else "",
                }
            )
    return rows


def _read_lines(path: Path) -> list[str]:
    """读取普通文本文件中的非空行。

    当前主要用于读取 regions.samtools.txt。

    Args:
        path:
            文本文件路径。

    Returns:
        去掉首尾空白后的非空行列表。

    如果文件不存在，则返回空列表。
    """

    if not path.exists():
        return []

    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def _match_region(
    feature: dict[str, str],
    regions: list[dict[str, str]],
) -> tuple[dict[str, str], int]:
    """将一个 feature 坐标匹配到包含它的 BED region。

    Args:
        feature:
            来自 deg_features.tsv 的 feature 行。

            需要包含：
            - chrom
            - start
            - end

        regions:
            从 regions.bed 读取出的 BED 区域列表。

    Returns:
        一个二元组：

        (matched_region, region_index)

        - matched_region:
          匹配到的 BED 区域字典；
          如果没有匹配到，则为空字典。

        - region_index:
          匹配到的 BED 区域在 regions 列表中的索引；
          如果没有匹配到，则为 -1。

    匹配逻辑：
        - feature 和 region 必须在同一 chrom；
        - BED start 通常是 0-based，所以先加 1 转为 1-based；
        - 如果 region_start_1based <= feature_start 且 feature_end <= region_end，
          则认为该 region 包含该 feature。
    """

    chrom = feature.get("chrom", "")

    # feature start/end 必须能转换为整数；
    # 如果坐标为空或格式错误，无法匹配 region。
    try:
        feature_start = int(feature.get("start", ""))
        feature_end = int(feature.get("end", ""))
    except ValueError:
        return {}, -1

    for index, region in enumerate(regions):
        # 染色体不一致则跳过。
        if region.get("chrom") != chrom:
            continue

        try:
            # BED start 是 0-based，转成 1-based 后再和 feature 坐标比较。
            region_start_1based = int(region.get("start", "")) + 1
            region_end = int(region.get("end", ""))
        except ValueError:
            continue

        # 判断 region 是否完整覆盖 feature。
        if region_start_1based <= feature_start and feature_end <= region_end:
            return region, index

    # 没有任何 region 覆盖该 feature。
    return {}, -1


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