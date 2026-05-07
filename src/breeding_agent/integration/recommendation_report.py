"""Generate rule-based recommendation reports from standardized evidence."""

from __future__ import annotations

import csv
from pathlib import Path


REPORT_TITLE = "Multi-omics Recommendation Report v0.1"
EVIDENCE_FILENAME = "standardized_evidence.tsv"
CANDIDATE_TABLE_FILENAME = "candidate_gene_table.tsv"
REPORT_FILENAME = "recommendation_report.md"


def generate_recommendation_report(*, outdir: Path) -> Path:
    """Create a first-version rule-based recommendation report."""

    integration_dir = outdir / "integration"
    evidence_file = integration_dir / EVIDENCE_FILENAME
    if not evidence_file.exists():
        raise FileNotFoundError(f"Standardized evidence file does not exist: {evidence_file}")

    records = _read_evidence(evidence_file)
    candidate_file = integration_dir / CANDIDATE_TABLE_FILENAME
    candidate_records = _read_candidate_table(candidate_file) if candidate_file.exists() else []
    report_file = integration_dir / REPORT_FILENAME
    report_file.write_text(
        _render_report(
            records=records,
            candidate_records=candidate_records,
            evidence_file=evidence_file,
        ),
        encoding="utf-8",
    )
    return report_file


def _read_evidence(evidence_file: Path) -> list[dict[str, str]]:
    with evidence_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        records = [dict(row) for row in reader]
    return sorted(records, key=_score_sort_key, reverse=True)


def _read_candidate_table(candidate_file: Path) -> list[dict[str, str]]:
    with candidate_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        records = [dict(row) for row in reader]
    return sorted(records, key=_candidate_sort_key, reverse=True)


def _render_report(
    *,
    records: list[dict[str, str]],
    candidate_records: list[dict[str, str]],
    evidence_file: Path,
) -> str:
    trait = _first_non_empty(records, "trait", default="unknown")
    omics_types = sorted({row.get("omics_type", "unknown") or "unknown" for row in records})
    top_record = records[0] if records else {}

    lines: list[str] = [
        f"# {REPORT_TITLE}",
        "",
        "## 1. 任务目标",
        (
            f"本报告基于标准证据表 `{evidence_file}`，对目标性状 `{trait}` 的候选"
            "基因 / 转录本进行第一版规则型解释。当前建议不是最终育种方案，只是候选"
            "证据解释，用于指导后续验证。"
        ),
        "",
        "## 2. 当前接入的组学证据",
        "- 当前版本仅基于 transcriptomics evidence。",
        "- Metabolomics 和 Genomics/GWAS 模块仍为占位，尚未参与推荐评分。",
        f"- 当前证据类型: {', '.join(omics_types) if omics_types else 'none'}。",
        "",
        "## 3. 候选基因 / 转录本列表",
        _candidate_table(candidate_records=candidate_records, records=records),
        "",
        "## 4. candidate_score / evidence_score",
        _score_summary(candidate_records=candidate_records, records=records),
        "",
        "## 5. 数据证据摘要",
        _data_summary(records),
        "",
        "## 6. 与目标性状的潜在关系",
        _trait_relationship_summary(trait=trait, top_record=top_record),
        "",
        "## 7. 当前限制",
        "- 当前报告只整合 transcriptomics evidence，不能直接推导最终育种决策。",
        "- Metabolomics 和 Genomics/GWAS 模块仍为占位，缺少跨组学一致性验证。",
        "- 当前 DEG 证据来自特定 JM-LM 对比，结论依赖样本、注释和统计阈值。",
        "- 缺少表型关联、功能注释、文献证据和独立实验验证。",
        "",
        "## 8. 后续需要补充的证据",
        "- 代谢组证据：关键代谢物变化、通路富集和候选基因相关性。",
        "- 基因组 / GWAS 证据：候选区域、显著标记、连锁或单倍型支持。",
        "- 表型证据：目标性状在 JM、LM 或更多材料中的稳定差异。",
        "- 文献证据：候选基因功能、同源基因和已报道通路支持。",
        "",
        "## 9. 下一步建议",
        _next_steps(records),
        "",
    ]

    return "\n".join(lines)


def _candidate_table(
    *,
    candidate_records: list[dict[str, str]],
    records: list[dict[str, str]],
) -> str:
    if candidate_records:
        return _aggregated_candidate_table(candidate_records)

    if not records:
        return "未发现可用于推荐的候选基因 / 转录本。"

    lines = [
        "| entity_id | entity_type | comparison | direction | effect_size | adj_p_value | evidence_score |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in records:
        lines.append(
            "| {entity_id} | {entity_type} | {comparison} | {direction} | "
            "{effect_size} | {adj_p_value} | {evidence_score} |".format(
                entity_id=_cell(row, "entity_id"),
                entity_type=_cell(row, "entity_type"),
                comparison=_cell(row, "comparison"),
                direction=_cell(row, "direction"),
                effect_size=_cell(row, "effect_size"),
                adj_p_value=_cell(row, "adj_p_value"),
                evidence_score=_cell(row, "evidence_score"),
            )
        )
    return "\n".join(lines)


def _aggregated_candidate_table(candidate_records: list[dict[str, str]]) -> str:
    lines = [
        "| candidate_id | entity_type | trait | supporting_omics | support_count | best_adj_p_value | max_abs_effect_size | final_score | recommendation_level |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in candidate_records:
        lines.append(
            "| {candidate_id} | {entity_type} | {trait} | {supporting_omics} | "
            "{support_count} | {best_adj_p_value} | {max_abs_effect_size} | "
            "{final_score} | {recommendation_level} |".format(
                candidate_id=_cell(row, "candidate_id"),
                entity_type=_cell(row, "entity_type"),
                trait=_cell(row, "trait"),
                supporting_omics=_cell(row, "supporting_omics"),
                support_count=_cell(row, "support_count"),
                best_adj_p_value=_cell(row, "best_adj_p_value"),
                max_abs_effect_size=_cell(row, "max_abs_effect_size"),
                final_score=_cell(row, "final_score"),
                recommendation_level=_cell(row, "recommendation_level"),
            )
        )
    return "\n".join(lines)


def _score_summary(
    *,
    candidate_records: list[dict[str, str]],
    records: list[dict[str, str]],
) -> str:
    if candidate_records:
        top = candidate_records[0]
        if top.get("recommendation_level") == "preliminary":
            supporting_omics = top.get("supporting_omics") or "transcriptomics"
            return (
                f"最高 final_score 为 `{top.get('final_score', 'NA')}`，对应候选实体 "
                f"`{top.get('candidate_id', 'unknown')}`。当前为 preliminary candidate，"
                f"仅基于 {supporting_omics} evidence。该分数来自候选聚合表中的"
                "第一版规则，仅用于候选排序和证据解释。"
            )
        return (
            f"最高 final_score 为 `{top.get('final_score', 'NA')}`，对应候选实体 "
            f"`{top.get('candidate_id', 'unknown')}`，推荐等级为 "
            f"`{top.get('recommendation_level', 'NA')}`。该分数来自候选聚合表中的"
            "第一版规则，仅用于候选排序和证据解释。"
        )

    if not records:
        return "无 evidence_score 可汇总。"

    top = records[0]
    return (
        f"最高 evidence_score 为 `{top.get('evidence_score', 'NA')}`，对应候选实体 "
        f"`{top.get('entity_id', 'unknown')}`。该分数来自标准证据表中的第一版规则，"
        "仅用于候选排序和证据解释。"
    )


def _data_summary(records: list[dict[str, str]]) -> str:
    if not records:
        return "标准证据表为空，暂无数据证据摘要。"

    lines = []
    for row in records:
        entity_id = row.get("entity_id", "unknown")
        comparison = row.get("comparison", "unknown")
        direction = row.get("direction", "unknown")
        effect_size = row.get("effect_size", "NA")
        adj_p_value = row.get("adj_p_value", "NA")
        note = row.get("evidence_note", "")
        lines.append(
            f"- `{entity_id}`: comparison={comparison}, direction={direction}, "
            f"logFC={effect_size}, adj_p_value={adj_p_value}. {note}"
        )

    target_record = _find_record(records, "Si9g04210.1")
    if target_record:
        lines.extend(["", _benchmark_target_summary(target_record)])
    return "\n".join(lines)


def _trait_relationship_summary(*, trait: str, top_record: dict[str, str]) -> str:
    if not top_record:
        return (
            f"当前没有足够证据解释候选基因 / 转录本与目标性状 `{trait}` 的潜在关系。"
        )

    entity_id = top_record.get("entity_id", "unknown")
    direction = top_record.get("direction", "unknown")
    return (
        f"`{entity_id}` 是当前 transcriptomics evidence 支持的候选实体。"
        f"其表达方向为 `{direction}`，提示该候选可能与 `{trait}` 的组间差异相关。"
        "这一关系仍需代谢组、基因组、表型和文献证据共同支持。"
    )


def _next_steps(records: list[dict[str, str]]) -> str:
    candidate = records[0].get("entity_id", "候选基因") if records else "候选基因"
    return "\n".join(
        [
            f"- 优先对 `{candidate}` 进行功能注释、同源基因检索和通路定位。",
            "- 补充代谢组、基因组 / GWAS、表型和文献证据后再升级推荐等级。",
            "- 在更多材料或独立批次中验证表达方向和目标性状的一致性。",
            "- 将本报告作为候选证据解释，不作为最终育种方案。"
        ]
    )


def _benchmark_target_summary(row: dict[str, str]) -> str:
    entity_id = row.get("entity_id", "Si9g04210.1")
    omics_type = row.get("omics_type", "transcriptomics")
    comparison = row.get("comparison", "unknown")
    logfc = _score_value(row.get("effect_size"))
    adj_p_value = _score_value(row.get("adj_p_value"))
    mean_count_jm, mean_count_lm = _mean_counts_from_note(row.get("evidence_note", ""))

    statements = [f"- Benchmark 候选对象 `{entity_id}` 来自 {omics_type} evidence。"]
    if comparison == "JM-LM" and logfc is not None and logfc < 0:
        statements.append(
            "在 JM-LM 对比中 logFC < 0，说明 LM 组表达更高。"
        )
    if adj_p_value is not None and adj_p_value < 0.05:
        statements.append(f"adj.P.Val={row.get('adj_p_value')} 显著。")
    if (
        mean_count_jm is not None
        and mean_count_lm is not None
        and mean_count_lm > mean_count_jm
    ):
        statements.append(
            "mean_count_LM 明显高于 mean_count_JM "
            f"({mean_count_lm:g} vs {mean_count_jm:g})。"
        )
    statements.append(
        "当前只能说明其是候选差异表达对象，不能直接等同最终育种建议。"
    )
    statements.append(
        "后续需要代谢组、基因组、表型和文献证据支持。"
    )
    return " ".join(statements)


def _score_sort_key(row: dict[str, str]) -> float:
    return _score_value(row.get("evidence_score")) or 0.0


def _candidate_sort_key(row: dict[str, str]) -> float:
    return _score_value(row.get("final_score")) or 0.0


def _score_value(value: str | None) -> float | None:
    try:
        return float(value or 0)
    except ValueError:
        return None


def _find_record(records: list[dict[str, str]], entity_id: str) -> dict[str, str] | None:
    for row in records:
        if row.get("entity_id") == entity_id:
            return row
    return None


def _mean_counts_from_note(note: str) -> tuple[float | None, float | None]:
    values: dict[str, float] = {}
    for item in note.split(";"):
        if "=" not in item:
            continue
        key, value = item.strip().split("=", 1)
        if key in {"mean_count_JM", "mean_count_LM"}:
            values[key] = _score_value(value) or 0.0
    return values.get("mean_count_JM"), values.get("mean_count_LM")


def _first_non_empty(
    records: list[dict[str, str]],
    key: str,
    *,
    default: str,
) -> str:
    for row in records:
        value = row.get(key)
        if value:
            return value
    return default


def _cell(row: dict[str, str], key: str) -> str:
    return row.get(key, "") or "NA"
