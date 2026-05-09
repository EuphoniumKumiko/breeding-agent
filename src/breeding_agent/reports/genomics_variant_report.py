"""Markdown report generation for candidate variant calling."""

from __future__ import annotations

from pathlib import Path


TARGET_GENES = ("Si9g04210.1", "Si5g31340.1", "Si9g34380.1")


def generate_genomics_variant_report(
    *,
    outdir: Path,
    result: dict[str, object],
) -> Path:
    """Write a candidate variant calling report."""

    report_dir = outdir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "genomics_variant_calling_report.md"
    report_path.write_text(render_genomics_variant_report(result), encoding="utf-8")
    return report_path


def render_genomics_variant_report(result: dict[str, object]) -> str:
    """Render the report body."""

    counts = result.get("counts", {})
    outputs = result.get("outputs", {})
    inputs = result.get("inputs", {})
    covered = set(result.get("covered_target_genes", []))
    commands = result.get("commands", [])

    lines = [
        "# Genomics Candidate Variant Calling MVP 报告",
        "",
        "## 1. 输入文件",
        _mapping_table(inputs),
        "",
        "## 2. 使用的 samtools/bcftools 命令",
        _commands_section(commands),
        "",
        "## 3. 输出文件",
        _mapping_table(outputs),
        "",
        "## 4. SNP/InDel 数量",
        f"- Candidate variants: {_value(counts, 'candidate_variants')}",
        f"- SNP: {_value(counts, 'snps')}",
        f"- InDel: {_value(counts, 'indels')}",
        f"- KASP candidate rows: {_value(counts, 'kasp_candidate_sites')}",
        f"- CAPS screening rows: {_value(counts, 'caps_candidate_sites')}",
        "",
        "## Variant Quality Summary",
        f"- total candidate variants: {_value(counts, 'candidate_variants')}",
        f"- PASS variants: {_value(counts, 'pass_variants')}",
        f"- LowQual variants: {_value(counts, 'lowqual_variants')}",
        f"- PASS SNPs: {_value(counts, 'pass_snps')}",
        f"- LowQual SNPs: {_value(counts, 'lowqual_snps')}",
        f"- PASS InDels: {_value(counts, 'pass_indels')}",
        f"- LowQual InDels: {_value(counts, 'lowqual_indels')}",
        f"- KASP preliminary_pass rows: {_value(counts, 'kasp_preliminary_pass')}",
        (
            "- KASP low_quality_review_required rows: "
            f"{_value(counts, 'kasp_low_quality_review_required')}"
        ),
        (
            "- CAPS pass_variant_requires_enzyme_screening rows: "
            f"{_value(counts, 'caps_pass_variant_requires_enzyme_screening')}"
        ),
        (
            "- CAPS low_quality_variant_requires_review rows: "
            f"{_value(counts, 'caps_low_quality_variant_requires_review')}"
        ),
        "",
        "PASS variants are prioritized for downstream marker review.",
        (
            "LowQual variants are retained for traceability but should not be "
            "prioritized without manual review."
        ),
        (
            "KASP/CAPS tables are preliminary screening outputs and do not replace "
            "primer design, flanking-sequence checking, enzyme screening, or "
            "population validation."
        ),
        "",
        "PASS 位点可优先进入后续标记开发复核。",
        "LowQual 位点仅作为可追溯候选记录保留，不应直接优先用于 KASP/CAPS 开发。",
        "KASP/CAPS 表只是初筛结果，不等同于最终引物或酶切方案。",
        "",
        "## 5. 三个重点基因候选区域覆盖情况",
    ]
    for gene_id in TARGET_GENES:
        status = "covered_by_called_variant" if gene_id in covered else "no_called_variant_in_region"
        lines.append(f"- `{gene_id}`: {status}")

    lines.extend(
        [
            "",
            "## 6. 当前结果解释",
            (
                "当前结果来自候选区域 calling，不等同于 WGS 全基因组变异检测。"
                "只有 bcftools/samtools 实际生成的 VCF 中存在的位点才会进入"
                "`candidate_variants.tsv`，本 workflow 不伪造 SNP/InDel 位点。"
            ),
            (
                "当前 BAM 如果是 RNA-seq BAM，候选变异结果会受到表达区域、"
                "reads 覆盖、剪接比对和等位基因表达偏倚限制，不能替代 WGS "
                "群体变异检测。"
            ),
            (
                "后续仍需在更大群体中结合基因型和黄酮含量数据进行关联验证，"
                "再筛选 KASP/CAPS 可转化位点。"
            ),
            "",
            "## 7. Warning",
        ]
    )
    warnings = result.get("warnings", [])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- 无。")
    return "\n".join(lines).rstrip() + "\n"


def _mapping_table(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return "无。"
    lines = ["| key | value |", "| --- | --- |"]
    for key, item in value.items():
        lines.append(f"| {key} | `{_escape(str(item))}` |")
    return "\n".join(lines)


def _commands_section(commands: object) -> str:
    if not isinstance(commands, list) or not commands:
        return "无。"
    lines = []
    for command in commands:
        if isinstance(command, dict):
            name = command.get("name", "command")
            rendered = command.get("command", "")
            lines.append(f"- {name}: `{_escape(str(rendered))}`")
        else:
            lines.append(f"- `{_escape(str(command))}`")
    return "\n".join(lines)


def _value(mapping: object, key: str) -> object:
    if isinstance(mapping, dict):
        return mapping.get(key, 0)
    return 0


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
