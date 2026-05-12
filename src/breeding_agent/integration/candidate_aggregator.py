"""Aggregate standardized evidence into candidate gene tables.

本文件负责把 standardized_evidence.tsv 中的标准化证据记录，
按 entity_id 聚合成 candidate_gene_table.tsv。

它属于 integration 层，也就是“证据整合层”。

整体作用可以理解为：

standardized_evidence.tsv
        ↓
按 entity_id 分组
        ↓
汇总每个候选基因/转录本的证据来源、性状、方向、p 值、effect size
        ↓
计算 final_score
        ↓
判断 recommendation_level
        ↓
写出 candidate_gene_table.tsv

当前这个模块主要用于 RNA-seq DEG 小流程后的第一版候选基因聚合。

注意：
这个模块不会重新做差异表达分析；
不会重新计算 p value；
不会判断真实因果关系；
也不会直接给出最终育种决策。
它只是基于已有 standardized evidence 做候选排序和初步推荐等级划分。
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


# 标准化 evidence 文件名。
#
# 该文件通常由 transcriptomics_standardizer.py 生成，路径类似：
# outputs/demo_cli_run/integration/standardized_evidence.tsv
#
# 里面每一行是一条标准化证据，字段通常包括：
# - entity_id
# - entity_type
# - omics_type
# - trait
# - comparison
# - direction
# - effect_size
# - p_value
# - adj_p_value
# - evidence_score
# - source_module
# - source_file
# - evidence_note
EVIDENCE_FILENAME = "standardized_evidence.tsv"


# 聚合后的候选基因表文件名。
#
# 输出路径通常是：
# outdir / "integration" / "candidate_gene_table.tsv"
CANDIDATE_TABLE_FILENAME = "candidate_gene_table.tsv"


# candidate_gene_table.tsv 的输出列。
#
# 这些列用于把一个候选对象的多条 evidence 汇总成一行。
CANDIDATE_TABLE_COLUMNS = [
    # 候选对象 ID。
    # 当前通常是 gene_id 或 transcript_id，例如 Si9g04210.1。
    "candidate_id",

    # 候选对象类型。
    # 例如 gene_or_transcript。
    "entity_type",

    # 与该候选对象相关的性状。
    # 如果同一候选对象在多条 evidence 中有多个 trait，会用逗号拼接。
    "trait",

    # 支持该候选对象的组学类型。
    # 例如 transcriptomics、metabolomics、genomics 等。
    "supporting_omics",

    # 支持该候选对象的组学类型数量。
    # 注意这里统计的是 omics_type 的去重数量，不是 evidence 行数。
    "support_count",

    # 该候选对象所有 evidence 中最小的 adj_p_value。
    # 值越小表示统计显著性越强。
    "best_adj_p_value",

    # 该候选对象所有 evidence 中最大的绝对 effect_size。
    # 对 RNA-seq 来说，effect_size 通常来自 logFC。
    "max_abs_effect_size",

    # 聚合后的最终分数。
    # 当前是简单规则分数，不是机器学习模型输出。
    "final_score",

    # 推荐等级。
    # 当前可能是 preliminary、medium、high。
    "recommendation_level",

    # 人类可读的证据摘要。
    "evidence_summary",
]


def generate_candidate_gene_table(*, outdir: Path) -> Path:
    """从 standardized_evidence.tsv 生成 candidate_gene_table.tsv。

    这是本文件的公开入口函数。

    主流程：

    1. 定位 integration/standardized_evidence.tsv；
    2. 读取标准化 evidence 记录；
    3. 按 entity_id 聚合 evidence；
    4. 计算每个候选对象的 final_score 和 recommendation_level；
    5. 写出 integration/candidate_gene_table.tsv；
    6. 返回输出文件路径。

    Args:
        outdir:
            当前 workflow 的输出根目录。

            例如：
            outputs/demo_cli_run

            本函数会在其下寻找：
            outputs/demo_cli_run/integration/standardized_evidence.tsv

    Returns:
        candidate_file:
            聚合后的候选基因表路径。

    Raises:
        FileNotFoundError:
            如果 standardized_evidence.tsv 不存在，则抛出异常。
    """

    # integration_dir 是标准化证据和候选表所在目录。
    integration_dir = outdir / "integration"

    # 标准化 evidence 输入文件。
    evidence_file = integration_dir / EVIDENCE_FILENAME

    # 如果标准化 evidence 不存在，说明上游 standardizer 尚未运行成功。
    if not evidence_file.exists():
        raise FileNotFoundError(f"Standardized evidence file does not exist: {evidence_file}")

    # 读取 standardized_evidence.tsv。
    records = _read_evidence(evidence_file)

    # 按 entity_id 聚合为候选对象记录。
    candidate_records = _aggregate_candidates(records)

    # 候选基因表输出路径。
    candidate_file = integration_dir / CANDIDATE_TABLE_FILENAME

    # 写出 TSV 表。
    with candidate_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CANDIDATE_TABLE_COLUMNS,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(candidate_records)

    return candidate_file


def _read_evidence(evidence_file: Path) -> list[dict[str, str]]:
    """读取 standardized_evidence.tsv。

    Args:
        evidence_file:
            标准化 evidence 文件路径。

    Returns:
        records:
            每一行 evidence 记录对应一个 dict。
            key 是表头字段名，value 是该行字段值。
    """

    with evidence_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [dict(row) for row in reader]


def _aggregate_candidates(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """按 entity_id 聚合 evidence 记录。

    Args:
        records:
            standardized_evidence.tsv 中读取到的 evidence 行。

    Returns:
        candidates:
            聚合后的候选对象记录列表。

    处理逻辑：

    1. 遍历所有 evidence 行；
    2. 读取 row["entity_id"]；
    3. entity_id 非空时，将该行加入对应分组；
    4. 每个 entity_id 分组生成一条 candidate 记录；
    5. 最后按 final_score、support_count、max_abs_effect_size 降序排序。

    注意：
        空 entity_id 的记录会被忽略，
        因为无法归入具体候选基因/转录本。
    """

    # defaultdict(list) 可以避免手动判断 key 是否存在。
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in records:
        entity_id = row.get("entity_id", "").strip()
        if entity_id:
            grouped[entity_id].append(row)

    # 每个 entity_id 对应一条聚合后的 candidate 记录。
    candidates = [
        _candidate_from_rows(candidate_id=entity_id, rows=rows)
        for entity_id, rows in grouped.items()
    ]

    # 按排序键降序排列：
    # final_score 越高越靠前；
    # support_count 越高越靠前；
    # max_abs_effect_size 越高越靠前。
    return sorted(candidates, key=_candidate_sort_key, reverse=True)


def _candidate_from_rows(
    *,
    candidate_id: str,
    rows: list[dict[str, str]],
) -> dict[str, str]:
    """将同一个 candidate_id 的多条 evidence 聚合成一行候选记录。

    Args:
        candidate_id:
            候选对象 ID，来自 entity_id。

        rows:
            属于该 candidate_id 的所有 evidence 行。

    Returns:
        一条 candidate_gene_table.tsv 记录。

    聚合字段说明：

    - entity_type:
      取第一条非空 entity_type。

    - trait:
      取所有非空 trait 的去重集合，并用逗号连接。

    - supporting_omics:
      取所有非空 omics_type 的去重集合，并用逗号连接。

    - directions:
      取所有非空 direction 的去重集合。

    - best_adj_p_value:
      取所有 adj_p_value 中的最小值。

    - max_abs_effect_size:
      取所有 effect_size 的最大绝对值。

    - max_evidence_score:
      取所有 evidence_score 中的最大值。

    - support_count:
      当前支持该候选对象的组学类型数量。

    - final_score:
      当前简单规则：
      final_score = min(max_evidence_score + 0.1 * support_count, 1.0)

      也就是说：
      evidence_score 越高，final_score 越高；
      支持该候选对象的组学类型越多，final_score 也会适当提高；
      最高不超过 1.0。

    注意：
        这是第一版规则型聚合分数，
        不是训练出来的模型分数，也不能直接等同于最终育种价值。
    """

    entity_type = _first_non_empty(rows, "entity_type", default="unknown")
    traits = _unique_values(rows, "trait")
    omics_types = _unique_values(rows, "omics_type")
    directions = _unique_values(rows, "direction")

    best_adj_p_value = _min_float(rows, "adj_p_value")
    max_abs_effect_size = _max_abs_float(rows, "effect_size")
    max_evidence_score = _max_float(rows, "evidence_score") or 0.0

    # support_count 统计的是支持该候选对象的组学类型数量。
    # 当前不是 evidence 行数。
    support_count = len(omics_types)

    # final_score 是简单规则分数。
    # 多一个组学来源加 0.1，但总分不超过 1.0。
    final_score = min(max_evidence_score + (0.1 * support_count), 1.0)

    return {
        "candidate_id": candidate_id,
        "entity_type": entity_type,
        "trait": ",".join(traits),
        "supporting_omics": ",".join(omics_types),
        "support_count": str(support_count),
        "best_adj_p_value": _format_float(best_adj_p_value),
        "max_abs_effect_size": _format_float(max_abs_effect_size),
        "final_score": f"{final_score:.3f}",
        "recommendation_level": _recommendation_level(
            final_score=final_score,
            support_count=support_count,
        ),
        "evidence_summary": _evidence_summary(
            omics_types=omics_types,
            support_count=support_count,
            max_score=max_evidence_score,
            directions=directions,
        ),
    }


def _unique_values(rows: list[dict[str, str]], key: str) -> list[str]:
    """提取某个字段的非空去重值，并排序。

    Args:
        rows:
            evidence 行列表。

        key:
            要提取的字段名。

    Returns:
        排序后的唯一值列表。

    示例：
        如果 rows 中 omics_type 分别是：
        transcriptomics, transcriptomics, metabolomics

        则返回：
        ["metabolomics", "transcriptomics"]
    """

    values = {row.get(key, "").strip() for row in rows if row.get(key, "").strip()}
    return sorted(values)


def _first_non_empty(
    rows: list[dict[str, str]],
    key: str,
    *,
    default: str,
) -> str:
    """返回某个字段的第一条非空值。

    Args:
        rows:
            evidence 行列表。

        key:
            要查找的字段名。

        default:
            如果所有行都没有非空值，则返回该默认值。

    Returns:
        第一条非空字段值，或 default。
    """

    for row in rows:
        value = row.get(key, "").strip()
        if value:
            return value
    return default


def _min_float(rows: list[dict[str, str]], key: str) -> float | None:
    """提取某字段的最小浮点数值。

    Args:
        rows:
            evidence 行列表。

        key:
            字段名，例如 adj_p_value。

    Returns:
        最小浮点数；
        如果没有可解析数值，则返回 None。
    """

    values = [_parse_float(row.get(key)) for row in rows]

    # 过滤掉 None，避免 min() 报错。
    values = [value for value in values if value is not None]

    return min(values) if values else None


def _max_float(rows: list[dict[str, str]], key: str) -> float | None:
    """提取某字段的最大浮点数值。

    Args:
        rows:
            evidence 行列表。

        key:
            字段名，例如 evidence_score。

    Returns:
        最大浮点数；
        如果没有可解析数值，则返回 None。
    """

    values = [_parse_float(row.get(key)) for row in rows]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _max_abs_float(rows: list[dict[str, str]], key: str) -> float | None:
    """提取某字段的最大绝对值。

    Args:
        rows:
            evidence 行列表。

        key:
            字段名，例如 effect_size。

    Returns:
        最大绝对值；
        如果没有可解析数值，则返回 None。

    用途：
        对 DEG 结果来说，effect_size 可能是 logFC。
        无论上调还是下调，绝对值越大表示变化幅度越大。
    """

    values = [_parse_float(row.get(key)) for row in rows]
    values = [abs(value) for value in values if value is not None]
    return max(values) if values else None


def _parse_float(value: str | None) -> float | None:
    """安全解析浮点数。

    Args:
        value:
            原始字符串。

    Returns:
        float 或 None。

    处理规则：
        - None 或空字符串返回 None；
        - 可解析为 float 的字符串返回 float；
        - 无法解析的字符串返回 None。

    这样可以避免因为 NA、空值、非数值字段导致整个流程失败。
    """

    if value in (None, ""):
        return None

    try:
        return float(value)
    except ValueError:
        return None


def _format_float(value: float | None) -> str:
    """格式化浮点数为字符串。

    Args:
        value:
            浮点数或 None。

    Returns:
        - 如果 value 是 None，返回空字符串；
        - 否则返回最多 6 位有效数字的字符串。

    示例：
        0.000123456 -> "0.000123456" 可能按 6 位有效数字压缩；
        12.3456789 -> "12.3457"
    """

    if value is None:
        return ""
    return f"{value:.6g}"


def _recommendation_level(*, final_score: float, support_count: int) -> str:
    """根据 final_score 和 support_count 判断推荐等级。

    Args:
        final_score:
            聚合后的候选分数。

        support_count:
            支持该候选对象的组学类型数量。

    Returns:
        推荐等级：
        - preliminary
        - medium
        - high

    当前规则：

    1. 如果 support_count < 2：
       无论 final_score 多高，都只能是 preliminary。

       原因：
       单组学证据不足以给出较高推荐等级，
       仍需要代谢组、基因组、表型、文献等补充证据。

    2. 如果 support_count >= 2 且 final_score >= 0.85：
       high。

    3. 如果 support_count >= 2 且 final_score >= 0.6：
       medium。

    4. 其他情况：
       preliminary。
    """

    if support_count < 2:
        return "preliminary"

    if final_score >= 0.85:
        return "high"

    if final_score >= 0.6:
        return "medium"

    return "preliminary"


def _evidence_summary(
    *,
    omics_types: list[str],
    support_count: int,
    max_score: float,
    directions: list[str],
) -> str:
    """生成候选对象的人类可读证据摘要。

    Args:
        omics_types:
            支持该候选对象的组学类型列表。

        support_count:
            支持该候选对象的组学类型数量。

        max_score:
            该候选对象的最高 evidence_score。

        directions:
            表达方向或证据方向列表。

    Returns:
        一段英文摘要文本。

    说明：
        当前报告中保留英文摘要是因为早期模块输出使用英文；
        如果后续统一中文报告，可以在这里改成中文模板。
    """

    omics_text = ", ".join(omics_types) if omics_types else "unknown omics"
    direction_text = ", ".join(directions) if directions else "unknown"

    summary = (
        f"Supported by {omics_text} evidence; max evidence_score={max_score:.3f}; "
        f"main direction(s): {direction_text}."
    )

    # 如果只有单组学证据，额外提示还需要补充证据。
    if support_count < 2:
        summary = (
            f"{summary} single-omics evidence only; requires additional omics, "
            "phenotype, and literature support."
        )

    return summary


def _candidate_sort_key(row: dict[str, str]) -> tuple[float, int, float]:
    """候选对象排序键。

    Args:
        row:
            candidate_gene_table 中的一行候选记录。

    Returns:
        排序元组：
        (final_score, support_count, max_abs_effect_size)

    排序逻辑：
        generate_candidate_gene_table() 中会使用 reverse=True，
        所以排序优先级为：

        1. final_score 越高越靠前；
        2. support_count 越高越靠前；
        3. max_abs_effect_size 越高越靠前。

    这样可以让证据分数高、多组学支持多、变化幅度大的候选对象排在前面。
    """

    final_score = _parse_float(row.get("final_score")) or 0.0
    support_count = int(row.get("support_count") or 0)
    max_abs_effect_size = _parse_float(row.get("max_abs_effect_size")) or 0.0

    return final_score, support_count, max_abs_effect_size