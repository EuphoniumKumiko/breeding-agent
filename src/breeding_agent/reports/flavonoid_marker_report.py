"""Markdown report generation for flavonoid marker aggregation."""

from __future__ import annotations

import json
from pathlib import Path

from breeding_agent.integration.flavonoid_marker_aggregator import (
    NOT_CALLED_VARIANT_NOTE,
    REQUIRED_GENE_IDS,
)


REPORT_FILENAME = "flavonoid_marker_report.md"
CORE_CONCLUSION = (
    "优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 SNP/InDel/KASP "
    "标记，再用更大群体的基因型和黄酮含量数据验证关联。"
)


def generate_flavonoid_marker_report(
    *,
    outdir: Path,
    evidence_dir: Path,
    candidate_rows: list[dict[str, str]],
    literature_rows: list[dict[str, str]],
    warnings: list[str],
    literature_review_text: str | None = None,
    marker_recommendation_text: str | None = None,
    validation_plan_text: str | None = None,
    reviewer_notes: str | None = None,
    qa_result: dict[str, object] | None = None,
    variant_calling_dir: Path | None = None,
) -> Path:
    """Generate a Chinese-facing flavonoid marker recommendation report."""

    report_dir = outdir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / REPORT_FILENAME
    report_file.write_text(
        render_flavonoid_marker_report(
            evidence_dir=evidence_dir,
            candidate_rows=candidate_rows,
            literature_rows=literature_rows,
            warnings=warnings,
            literature_review_text=literature_review_text,
            marker_recommendation_text=marker_recommendation_text,
            validation_plan_text=validation_plan_text,
            reviewer_notes=reviewer_notes,
            qa_result=qa_result,
            variant_calling_dir=variant_calling_dir,
        ),
        encoding="utf-8",
    )
    return report_file


def generate_flavonoid_marker_report_from_agent_result(
    *,
    outdir: Path,
    agent_result: dict[str, object],
) -> Path:
    """Write a report from the CentralHost structured result."""

    report_dir = outdir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / REPORT_FILENAME
    report_file.write_text(str(agent_result["report_text"]), encoding="utf-8")
    return report_file


def render_flavonoid_marker_report(
    *,
    evidence_dir: Path,
    candidate_rows: list[dict[str, str]],
    literature_rows: list[dict[str, str]],
    warnings: list[str],
    literature_review_text: str | None = None,
    marker_recommendation_text: str | None = None,
    validation_plan_text: str | None = None,
    reviewer_notes: str | None = None,
    qa_result: dict[str, object] | None = None,
    variant_calling_dir: Path | None = None,
) -> str:
    """Render the report body."""

    rows_by_gene = {
        row.get("gene_id", ""): row
        for row in candidate_rows
    }
    ordered_rows = [
        rows_by_gene.get(gene_id, {"gene_id": gene_id})
        for gene_id in REQUIRED_GENE_IDS
    ]
    has_not_called = any(
        row.get("variant_status", "not_called") == "not_called"
        for row in ordered_rows
    )

    lines = [
        "# 谷子黄酮候选标记 aggregation 报告",
        "",
        "## 1. 任务概述",
        (
            "本报告基于本地 mini 数据包生成的 transcriptome、metabolome、"
            "annotation、genome variant 和 literature evidence，采用纯规则、"
            "模板版、可复现 workflow 对谷子黄酮相关候选基因进行标记类型推荐。"
        ),
        CORE_CONCLUSION,
        "",
        "## 2. 输入数据",
        f"- Evidence 目录: `{evidence_dir}`",
        "- 转录组：`bam/` 中所有文件，并由 evidence 转换流程整理为 `transcriptome_evidence.tsv`。",
        "- 代谢组：`metabolome_raw_3372.tsv`，并由 evidence 转换流程整理为 `metabolome_evidence.tsv`。",
        "- 基因组：`genome.fa` 和 `genome.gff`，后续 calling 可结合 `genome.bam_compatible.fa.gz` 与 `genome.original_coords.gff`。",
        "- 功能注释：`local_region_emapper_annotations.tsv`，并由 evidence 转换流程整理为 `annotation_evidence.tsv`。",
        "- 文献查阅：读取 `literature_evidence.tsv` 中已核对 DOI 的 seed evidence；本 workflow 不调用外部 API，也不伪造 DOI。",
        "",
        "## 3. 目标候选基因",
        _target_gene_list(ordered_rows),
        "",
        "## 4. 转录组证据",
        _transcriptome_table(ordered_rows),
        "",
        "## 5. 代谢组证据",
        _metabolome_table(ordered_rows),
        "",
        "## 6. 基因组/变异证据",
        _variant_table(ordered_rows),
    ]

    if has_not_called:
        lines.extend(["", NOT_CALLED_VARIANT_NOTE])
    if variant_calling_dir is not None:
        lines.extend(
            [
                "",
                "## 候选区域变异 calling 证据",
                _variant_calling_evidence_section(
                    rows=ordered_rows,
                    variant_calling_dir=variant_calling_dir,
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 7. 功能注释证据",
            _annotation_table(ordered_rows),
            "",
            "## 8. 文献查阅过程",
            _literature_section(literature_rows, literature_review_text),
            "",
            "## 9. 标记类型推荐：SNP/InDel/KASP/CAPS",
            marker_recommendation_text
            if marker_recommendation_text
            else _marker_recommendation_section(ordered_rows),
            "",
            "## 10. 后续验证方案",
            validation_plan_text if validation_plan_text else _default_validation_plan(),
            "",
            "## 11. 不确定性与限制",
            _limitations_section(
                warnings=warnings,
                has_not_called=has_not_called,
                reviewer_notes=reviewer_notes,
            ),
            "",
            "## 12. QA 检查结果",
            _qa_section(qa_result),
            "",
        ]
    )
    return "\n".join(lines)


def _target_gene_list(rows: list[dict[str, str]]) -> str:
    return "\n".join(
        [
            f"- `{row.get('gene_id', gene_id)}`: variant_status="
            f"`{row.get('variant_status', 'not_called')}`；推荐进入候选标记开发和群体验证。"
            for gene_id, row in zip(REQUIRED_GENE_IDS, rows)
        ]
    )


def _transcriptome_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "| gene_id | baseMean | log2FC | pvalue | padj | Green_mean | Golden_mean | Direction |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {gene_id} | {baseMean} | {log2FC} | {pvalue} | {padj} | "
            "{Green_mean} | {Golden_mean} | {Direction} |".format(
                gene_id=_cell(row, "gene_id"),
                baseMean=_cell(row, "baseMean"),
                log2FC=_cell(row, "log2FC"),
                pvalue=_cell(row, "pvalue"),
                padj=_cell(row, "padj"),
                Green_mean=_cell(row, "Green_mean"),
                Golden_mean=_cell(row, "Golden_mean"),
                Direction=_cell(row, "Direction"),
            )
        )
    return "\n".join(lines)


def _metabolome_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "| gene_id | top_correlated_metabolite | top_pearson_r | top_spls_metabolite |",
        "| --- | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {gene_id} | {top_correlated_metabolite} | {top_pearson_r} | "
            "{top_spls_metabolite} |".format(
                gene_id=_cell(row, "gene_id"),
                top_correlated_metabolite=_cell(row, "top_correlated_metabolite"),
                top_pearson_r=_cell(row, "top_pearson_r"),
                top_spls_metabolite=_cell(row, "top_spls_metabolite"),
            )
        )
    return "\n".join(lines)


def _variant_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "| gene_id | variant_status | marker recommendation |",
        "| --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {gene_id} | {variant_status} | {marker_recommendation} |".format(
                gene_id=_cell(row, "gene_id"),
                variant_status=_cell(row, "variant_status"),
                marker_recommendation=_cell(row, "marker_recommendation"),
            )
        )
    return "\n".join(lines)


def _variant_calling_evidence_section(
    *,
    rows: list[dict[str, str]],
    variant_calling_dir: Path,
) -> str:
    lines = [
        f"- Variant calling 输出目录: `{variant_calling_dir}`",
        "- 当前 variant calling 来自 mini 数据包和现有 BAM；如果 BAM 是 RNA-seq BAM，结果受表达区域、reads 覆盖、剪接比对和等位基因表达偏倚影响。",
        "- 该结果不能替代 WGS/GBS 群体变异检测。",
        "- PASS 位点可优先进入后续标记开发复核。",
        "- LowQual 位点仅作为可追溯候选记录保留，不应直接优先用于 KASP/CAPS 开发。",
        "- KASP/CAPS 表只是 preliminary screening，不是最终引物或酶切方案。",
        "- 后续仍需更大群体基因型和黄酮含量关联验证。",
        "",
        "| gene_id | variant_evidence_status | total | PASS | LowQual | SNP | InDel | PASS SNP | LowQual SNP | KASP preliminary_pass | KASP LowQual review | CAPS PASS screening | CAPS LowQual review | 解释 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {gene_id} | {variant_evidence_status} | {total_variants} | "
            "{pass_variants} | {lowqual_variants} | {snp_count} | {indel_count} | "
            "{pass_snp_count} | {lowqual_snp_count} | "
            "{kasp_preliminary_pass_count} | "
            "{kasp_low_quality_review_required_count} | "
            "{caps_pass_variant_requires_enzyme_screening_count} | "
            "{caps_low_quality_variant_requires_review_count} | {explanation} |".format(
                gene_id=_cell(row, "gene_id"),
                variant_evidence_status=_cell(row, "variant_evidence_status"),
                total_variants=_cell(row, "total_variants"),
                pass_variants=_cell(row, "pass_variants"),
                lowqual_variants=_cell(row, "lowqual_variants"),
                snp_count=_cell(row, "snp_count"),
                indel_count=_cell(row, "indel_count"),
                pass_snp_count=_cell(row, "pass_snp_count"),
                lowqual_snp_count=_cell(row, "lowqual_snp_count"),
                kasp_preliminary_pass_count=_cell(
                    row,
                    "kasp_preliminary_pass_count",
                ),
                kasp_low_quality_review_required_count=_cell(
                    row,
                    "kasp_low_quality_review_required_count",
                ),
                caps_pass_variant_requires_enzyme_screening_count=_cell(
                    row,
                    "caps_pass_variant_requires_enzyme_screening_count",
                ),
                caps_low_quality_variant_requires_review_count=_cell(
                    row,
                    "caps_low_quality_variant_requires_review_count",
                ),
                explanation=_variant_evidence_explanation(row),
            )
        )
    return "\n".join(lines)


def _variant_evidence_explanation(row: dict[str, str]) -> str:
    status = row.get("variant_evidence_status", "")
    if status == "preliminary_pass_variants_detected":
        return "已有真实 VCF PASS variant，可优先复核 PASS SNP 的 KASP 转化潜力。"
    if status == "only_low_quality_variants_detected":
        return "仅检出 LowQual variant，不应优先用于 KASP/CAPS，需要人工复核质量。"
    if status == "no_called_variant_in_current_mini_calling":
        return "当前 mini calling 未检出 called variant，不能写成已有候选位点。"
    if status == "variant_calling_output_missing":
        return "未读取到 variant calling 输出，保持原有 not_called 解释。"
    return "未接入可选 variant calling evidence。"


def _annotation_table(rows: list[dict[str, str]]) -> str:
    lines = [
        "| gene_id | function annotation | KEGG_ko | KEGG / pathway | PFAMs |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {gene_id} | {function_annotation} | {KEGG_ko} | {KEGG_Pathway} | "
            "{PFAMs} |".format(
                gene_id=_cell(row, "gene_id"),
                function_annotation=_cell(row, "function_annotation"),
                KEGG_ko=_cell(row, "KEGG_ko"),
                KEGG_Pathway=_cell(row, "KEGG_Pathway"),
                PFAMs=_cell(row, "PFAMs"),
            )
        )
    return "\n".join(lines)


def _literature_section(
    literature_rows: list[dict[str, str]],
    literature_review_text: str | None,
) -> str:
    if literature_review_text:
        return literature_review_text

    if not literature_rows:
        return (
            "未读取到 `literature_evidence.tsv`。当前报告不能满足 DOI 展示要求；"
            "请补充经过人工核对的文献查阅 evidence。"
        )

    lines = [
        "本节仅展示 evidence 中已有 DOI，不调用外部 API，不补写未核对 DOI。",
        "",
        "| query | title | year | DOI | relevance |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in literature_rows:
        lines.append(
            "| {query} | {title} | {year} | {doi} | {relevance} |".format(
                query=_cell(row, "query"),
                title=_cell(row, "title"),
                year=_cell(row, "year"),
                doi=_cell(row, "doi"),
                relevance=_cell(row, "relevance"),
            )
        )
    return "\n".join(lines)


def _marker_recommendation_section(rows: list[dict[str, str]]) -> str:
    lines = [
        CORE_CONCLUSION,
        "",
        "- SNP: 用于捕获候选基因或邻近调控区的单碱基差异，适合作为 KASP 转化来源。",
        "- InDel: 若候选区域存在插入/缺失多态，可作为普通 PCR、电泳或 KASP 转化候选。",
        "- KASP: 对通过 calling 和群体验证的高置信 SNP/InDel 优先开发，适合后续高通量分型。",
        "- CAPS: 当 SNP/InDel 改变限制性内切酶识别位点时开发，用于低成本验证或小规模群体验证。",
        "",
        "| gene_id | 推荐说明 |",
        "| --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {gene_id} | {marker_recommendation} |".format(
                gene_id=_cell(row, "gene_id"),
                marker_recommendation=_cell(row, "marker_recommendation"),
            )
        )
    return "\n".join(lines)


def _default_validation_plan() -> str:
    return "\n".join(
        [
            "- 基于 BAM、genome.fa/genome.gff 或 genome.bam_compatible.fa.gz 与 genome.original_coords.gff 对候选区域进行 SNP/InDel calling。",
            "- 对 calling 后的候选 SNP/InDel 做测序深度、缺失率、等位基因频率和重复样本一致性过滤。",
            "- 将高置信 SNP/InDel 转化为 KASP 标记；若变异改变限制性内切酶识别位点，可开发 CAPS 标记。",
            "- 在更大群体中同步采集基因型和黄酮含量数据，验证标记与黄酮性状的关联和稳定性。",
            "- 对 Si9g04210.1、Si5g31340.1、Si9g34380.1 做候选区域单倍型和表达/代谢物联合验证。",
        ]
    )


def _limitations_section(
    *,
    warnings: list[str],
    has_not_called: bool,
    reviewer_notes: str | None,
) -> str:
    lines = [
        "- 当前统计值来自 mini evidence，用于候选排序和报告复现，不等同于最终育种验证。",
        "- 当前 workflow 不调用外部 API；文献 DOI 只来自 evidence 文件中已提供或已核对的记录。",
        "- 不伪造 SNP/InDel 具体位点；未 calling 时统一保留 variant_status=not_called。",
    ]
    if has_not_called:
        lines.append(f"- {NOT_CALLED_VARIANT_NOTE}")
    if reviewer_notes:
        lines.append(f"- {reviewer_notes}")
    if warnings:
        lines.append("- Evidence warning: " + "；".join(sorted(set(warnings))))
    return "\n".join(lines)


def _qa_section(qa_result: dict[str, object] | None) -> str:
    if qa_result is None:
        return "QA 检查将在报告生成后由 workflow 执行，并写入 `logs/qa_check.json`。"
    return "\n".join(
        [
            f"- passed: `{qa_result.get('passed')}`",
            "- qa_check.json 内容摘要：",
            "```json",
            json.dumps(qa_result, ensure_ascii=False, indent=2),
            "```",
        ]
    )


def _cell(row: dict[str, str], key: str) -> str:
    value = row.get(key, "")
    if value is None or value == "":
        return "NA"
    return str(value).replace("\n", " ").replace("|", "\\|")
