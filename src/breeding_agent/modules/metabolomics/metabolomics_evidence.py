"""Metabolomics evidence analysis from the mini flavonoid package.

本文件负责从 mini flavonoid package 中整理代谢组相关证据。

它属于 modules 层，也就是“具体业务处理层”：
- workflows/metabolomics_evidence.py 负责调度；
- 本文件负责真正读取数据包中的代谢组文件、复制结果表、统计行数、生成预览数据；
- reports/metabolomics_report.py 负责把这里返回的 analysis_result 渲染成 Markdown 报告。

当前模块并不重新计算原始代谢组差异分析结果，
而是基于数据包中已经准备好的 TSV 文件进行 evidence 整理。

主要输出包括：
1. candidate_metabolites.tsv
2. flavonoid_related_significant_metabolites.tsv
3. target_gene_metabolite_network_edges.tsv
4. target_gene_spls_coefficients.tsv

这些表会被复制到 output_dir 下，供 Gradio 页面展示和报告生成使用。
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path


# 当前黄酮标记推荐任务中固定关注的三个重点候选基因。
#
# 这些基因来自项目的谷子黄酮任务设定：
# - Si9g04210.1
# - Si5g31340.1
# - Si9g34380.1
#
# 后续 target_gene_summary 会围绕这三个基因提取代谢组相关摘要。
TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")


# 输入文件清单。
#
# key 是模块内部使用的逻辑名称；
# value 是相对于 dataset_dir 的文件路径。
#
# 例如：
# dataset_dir = data/private/flavonoid_marker_mini_5genes_50kb
#
# 那么 raw_metabolome 对应：
# data/private/flavonoid_marker_mini_5genes_50kb/metabolome/metabolome_raw_3372.tsv
#
# 注意：
# 这里列出的文件并不一定都会被复制为输出表。
# 有些文件主要用于完整性检查或生成摘要，例如：
# - sample_metadata.tsv
# - annotations/target_gene_evidence_summary.tsv
INPUT_FILES = {
    # 原始代谢组矩阵或原始代谢物表。
    # 当前模块只检查它是否存在，并不直接重新分析该文件。
    "raw_metabolome": Path("metabolome") / "metabolome_raw_3372.tsv",

    # 候选代谢物表。
    # 会被复制到 output_dir/candidate_metabolites.tsv。
    "candidate_metabolites": Path("metabolome") / "candidate_metabolites.tsv",

    # 黄酮相关显著差异代谢物表。
    # 会被复制到 output_dir/flavonoid_related_significant_metabolites.tsv。
    "flavonoid_related_significant_metabolites": (
        Path("metabolome") / "flavonoid_related_significant_metabolites.tsv"
    ),

    # 目标基因与代谢物的相关性网络边表。
    # 例如某个基因与某个代谢物之间的 Pearson 相关系数。
    "target_gene_metabolite_network_edges": (
        Path("metabolome") / "target_gene_metabolite_network_edges.tsv"
    ),

    # sPLS 模型中的基因-代谢物系数表。
    # 用于表示候选基因和代谢物之间的多变量关联强度。
    "target_gene_spls_coefficients": (
        Path("metabolome") / "target_gene_spls_coefficients.tsv"
    ),

    # 与目标基因相关的代谢物丰度表。
    # 当前模块只做存在性检查，不直接复制到 OUTPUT_TABLES。
    "target_gene_related_metabolite_abundance": (
        Path("metabolome") / "target_gene_related_metabolite_abundance.tsv"
    ),

    # 样本元数据。
    # 通常可包含样本分组、材料信息、处理条件等。
    # 当前模块只检查是否存在。
    "sample_metadata": Path("sample_metadata.tsv"),

    # 目标基因综合证据摘要表。
    # 该文件用于提取 target_gene_summary，
    # 包括每个目标基因的功能描述、表达方向、网络边数量、top 相关代谢物等。
    "target_gene_evidence_summary": (
        Path("annotations") / "target_gene_evidence_summary.tsv"
    ),
}


# 输出表清单。
#
# key 必须能在 INPUT_FILES 中找到对应输入文件。
# value 是复制到 output_dir 下的输出文件名。
#
# 当前模块的策略是：
# - 如果输入文件存在，就原样复制到 output_dir；
# - 如果输入文件缺失，就写一个只有表头的空 TSV，避免 Gradio 展示时报错。
OUTPUT_TABLES = {
    "candidate_metabolites": "candidate_metabolites.tsv",
    "flavonoid_related_significant_metabolites": (
        "flavonoid_related_significant_metabolites.tsv"
    ),
    "target_gene_metabolite_network_edges": (
        "target_gene_metabolite_network_edges.tsv"
    ),
    "target_gene_spls_coefficients": "target_gene_spls_coefficients.tsv",
}


# 默认表头。
#
# 当某个输入表缺失时，模块不会直接失败，
# 而是创建一个只有表头的空表。
#
# 这样做的好处是：
# 1. Gradio 页面可以正常加载空表；
# 2. 报告生成流程不会因为单个可选表缺失而完全中断；
# 3. manifest / warnings 会记录哪些输入文件缺失，便于追踪。
DEFAULT_HEADERS = {
    "candidate_metabolites": [
        "Index",
        "Compounds",
        "Class I",
        "Class II",
        "Green_mean",
        "Golden_mean",
        "VIP",
        "P_value",
        "FDR",
        "Log2FC",
        "Direction",
        "Candidate_score",
    ],
    "flavonoid_related_significant_metabolites": [
        "Index",
        "Compounds",
        "Class I",
        "Class II",
        "Green_mean",
        "Golden_mean",
        "VIP",
        "P_value",
        "FDR",
        "Log2FC",
        "Direction",
    ],
    "target_gene_metabolite_network_edges": [
        "Gene",
        "Metabolite_index",
        "Metabolite_name",
        "Metabolite_subclass",
        "Pearson_r",
        "Pearson_FDR",
        "edge_sign",
        "edge_weight",
    ],
    "target_gene_spls_coefficients": [
        "Gene",
        "Metabolite_index",
        "Coefficient",
        "Metabolite_name",
        "abs_coefficient",
    ],
}


def build_metabolomics_evidence(*, dataset_dir: Path, output_dir: Path) -> dict[str, object]:
    """复制数据包中的代谢组 evidence 表，并生成结构化摘要。

    这是本模块的核心函数。

    它做的事情可以分成四类：

    1. 输入检查
       - 检查 INPUT_FILES 中列出的文件是否存在；
       - 缺失文件不会立即报错，而是写入 warnings。

    2. 输出表生成
       - 对 OUTPUT_TABLES 中定义的 4 类表进行处理；
       - 如果源文件存在，则复制到 output_dir；
       - 如果源文件不存在，则写出只有表头的空表。

    3. 摘要统计
       - 统计每个输出表的数据行数；
       - 统计每个目标基因的网络边数量；
       - 统计每个目标基因的 sPLS 系数数量；
       - 从 target_gene_evidence_summary.tsv 中提取三个重点基因的摘要。

    4. 预览数据
       - 读取各主要输出表前 8 行，供 Gradio 页面和报告快速展示。

    Args:
        dataset_dir:
            输入数据包目录。

            典型路径：
            data/private/flavonoid_marker_mini_5genes_50kb

        output_dir:
            代谢组 evidence 输出目录。

            典型路径：
            outputs/gradio_metabolomics_run/metabolomics

    Returns:
        一个结构化结果字典，通常会被 workflow 层继续写入 manifest，
        并交给 metabolomics_report.py 生成报告。

        主要字段包括：
        - task_name
        - dataset_dir
        - output_dir
        - inputs
        - outputs
        - row_counts
        - warnings
        - target_genes
        - target_gene_summary
        - network_counts
        - spls_counts
        - candidate_preview
        - significant_preview
        - top_network_edges
        - top_spls_coefficients
    """

    # 确保输出目录存在。
    output_dir.mkdir(parents=True, exist_ok=True)

    # 检查所有预期输入文件是否存在。
    # 缺失文件会记录为 warning，但不会中断流程。
    warnings = _missing_input_warnings(dataset_dir)

    # outputs 记录每个输出表的实际路径。
    outputs: dict[str, str] = {}

    # row_counts 记录每个输出表的数据行数，不包含表头。
    row_counts: dict[str, int] = {}

    # 遍历需要输出展示的 4 类表。
    # 如果源文件存在，则复制；
    # 如果源文件缺失，则写出空表。
    for input_key, filename in OUTPUT_TABLES.items():
        source = dataset_dir / INPUT_FILES[input_key]
        target = output_dir / filename

        row_counts[input_key] = _copy_existing_or_write_empty(
            source=source,
            target=target,
            fallback_header=DEFAULT_HEADERS[input_key],
        )
        outputs[input_key] = str(target)

    # 目标基因综合证据摘要表路径。
    # 后续从这个文件中提取三个目标基因的代谢组相关摘要。
    summary_path = dataset_dir / INPUT_FILES["target_gene_evidence_summary"]

    # 输出后的网络边表路径。
    network_path = output_dir / OUTPUT_TABLES["target_gene_metabolite_network_edges"]

    # 输出后的 sPLS 系数表路径。
    spls_path = output_dir / OUTPUT_TABLES["target_gene_spls_coefficients"]

    # 提取三个重点基因的摘要信息。
    target_gene_summary = _target_gene_summary(summary_path)

    # 按 Gene 列统计每个基因有多少条代谢物网络边。
    network_counts = _count_by_column(network_path, "Gene")

    # 按 Gene 列统计每个基因有多少条 sPLS 系数记录。
    spls_counts = _count_by_column(spls_path, "Gene")

    # 读取候选代谢物表前几行，用于页面或报告预览。
    candidate_preview = _read_preview(output_dir / OUTPUT_TABLES["candidate_metabolites"])

    # 读取黄酮相关显著代谢物表前几行。
    significant_preview = _read_preview(
        output_dir / OUTPUT_TABLES["flavonoid_related_significant_metabolites"]
    )

    # 读取网络边表前几行。
    top_network_edges = _read_preview(network_path)

    # 读取 sPLS 系数表前几行。
    top_spls_coefficients = _read_preview(spls_path)

    # 返回完整结构化结果。
    # workflow 层会把该结果写进 manifest，并交给报告模块生成 Markdown。
    return {
        "task_name": "metabolomics_evidence",
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "inputs": _input_status(dataset_dir),
        "outputs": outputs,
        "row_counts": row_counts,
        "warnings": warnings,
        "target_genes": list(TARGET_GENES),
        "target_gene_summary": target_gene_summary,
        "network_counts": network_counts,
        "spls_counts": spls_counts,
        "candidate_preview": candidate_preview,
        "significant_preview": significant_preview,
        "top_network_edges": top_network_edges,
        "top_spls_coefficients": top_spls_coefficients,
    }


def _missing_input_warnings(dataset_dir: Path) -> list[str]:
    """检查 INPUT_FILES 中列出的输入文件是否缺失。

    Args:
        dataset_dir:
            输入数据包根目录。

    Returns:
        warnings:
            缺失文件提示列表。

    注意：
        该函数只生成 warning，不抛异常。
        这符合当前模块“尽量展示已有证据，缺失部分保留追踪信息”的设计。
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

    这些信息会进入 build_metabolomics_evidence() 的返回结果，
    再由 workflow 层写入 manifest.json。

    Args:
        dataset_dir:
            输入数据包根目录。

    Returns:
        一个嵌套字典，格式类似：

        {
            "raw_metabolome": {
                "path": ".../metabolome/metabolome_raw_3372.tsv",
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


def _copy_existing_or_write_empty(
    *,
    source: Path,
    target: Path,
    fallback_header: list[str],
) -> int:
    """复制已有输入表；如果输入表缺失，则写出空表。

    Args:
        source:
            数据包中的源文件路径。

        target:
            输出目录中的目标文件路径。

        fallback_header:
            当 source 不存在时，用于创建空 TSV 的表头。

    Returns:
        输出表的数据行数，不包含表头。

    逻辑：
        - 如果 source 存在且是文件：复制 source 到 target，并统计数据行数；
        - 如果 source 不存在：创建只有 fallback_header 的空表，返回 0。
    """

    # 确保目标文件父目录存在。
    target.parent.mkdir(parents=True, exist_ok=True)

    # 如果源文件存在，直接复制。
    if source.exists() and source.is_file():
        shutil.copyfile(source, target)
        return _count_data_rows(target)

    # 如果源文件不存在，写一个只有表头的空 TSV。
    # 这样后续 Gradio DataFrame 和报告读取时仍有合法表结构。
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(fallback_header)
    return 0


def _count_data_rows(path: Path) -> int:
    """统计 TSV 文件的数据行数，不包含表头。

    Args:
        path:
            待统计的 TSV 文件路径。

    Returns:
        数据行数。

    示例：
        如果文件共有 11 行，其中第 1 行是表头，
        则返回 10。

    max(..., 0) 是为了避免空文件或异常情况下出现负数。
    """

    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


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


def _target_gene_summary(summary_path: Path) -> list[dict[str, str]]:
    """提取三个目标基因的代谢组相关摘要。

    Args:
        summary_path:
            annotations/target_gene_evidence_summary.tsv 文件路径。

    Returns:
        一个列表，每个元素对应一个目标基因的摘要信息。

    该函数会固定遍历 TARGET_GENES，
    即使某个基因在 summary 文件中不存在，也会返回该基因的空摘要。
    这样可以保证报告结构稳定，三个重点基因始终都会出现。

    提取字段包括：
    - description
    - direction
    - n_network_edges
    - max_abs_pearson
    - top_correlated_metabolite
    - top_pearson_r
    - n_spls_coefficients
    - max_abs_spls_coefficient
    - top_spls_metabolite
    """

    # 读取 summary 表。
    rows = _read_dict_rows(summary_path)

    # 按 Gene 字段建立索引，方便根据 gene_id 快速查找。
    rows_by_gene = {row.get("Gene", ""): row for row in rows}

    summary = []
    for gene_id in TARGET_GENES:
        # 如果该 gene_id 不存在，则使用空字典。
        # 后续 row.get(..., "") 会返回空字符串。
        row = rows_by_gene.get(gene_id, {})

        summary.append(
            {
                "gene_id": gene_id,
                "description": row.get("Description", ""),
                "direction": row.get("Direction", ""),
                "n_network_edges": row.get("n_network_edges", ""),
                "max_abs_pearson": row.get("max_abs_pearson", ""),
                "top_correlated_metabolite": row.get(
                    "top_correlated_metabolite", ""
                ),
                "top_pearson_r": row.get("top_pearson_r", ""),
                "n_spls_coefficients": row.get("n_spls_coefficients", ""),
                "max_abs_spls_coefficient": row.get(
                    "max_abs_spls_coefficient", ""
                ),
                "top_spls_metabolite": row.get("top_spls_metabolite", ""),
            }
        )

    return summary


def _count_by_column(path: Path, column: str) -> dict[str, int]:
    """按指定列统计记录数量。

    Args:
        path:
            TSV 文件路径。

        column:
            用于分组统计的列名。

    Returns:
        一个字典：
        - key 为 column 列中的取值；
        - value 为该取值出现的次数。

    典型用法：
        _count_by_column(network_path, "Gene")

    用于统计：
        每个 Gene 有多少条 network edge；
        每个 Gene 有多少条 sPLS coefficient。
    """

    counts: dict[str, int] = {}

    for row in _read_dict_rows(path):
        key = row.get(column, "")
        if key:
            counts[key] = counts.get(key, 0) + 1

    return counts


def _read_preview(path: Path, limit: int = 8) -> list[dict[str, str]]:
    """读取 TSV 文件前若干行作为预览。

    Args:
        path:
            TSV 文件路径。

        limit:
            最多读取多少行，默认 8 行。

    Returns:
        TSV 前 limit 行记录，格式为 list[dict[str, str]]。

    用途：
        - Gradio 页面展示前几行；
        - Markdown 报告展示 top records；
        - 避免一次性把大表全部塞进报告。
    """

    return _read_dict_rows(path)[:limit]