"""Build structured context for flavonoid marker agents.

本文件负责为“谷子黄酮候选标记推荐”的多个 agent 构建统一上下文。

它位于 agents 层，但它本身不是一个具体 agent，
而是 agent 运行前的“上下文组装器”。

整体作用可以理解为：

evidence_dir/
    transcriptome_evidence.tsv
    metabolome_evidence.tsv
    annotation_evidence.tsv
    genome_variant_evidence.tsv
    literature_evidence.tsv
        +
可选 candidate_rows
        +
可选 variant_calling_dir / variant_evidence_rows
        +
可选 literature_results_path / literature_results
        ↓
build_flavonoid_agent_context()
        ↓
生成 agent_context
        ↓
供 LiteratureAgent / MarkerRecommendationAgent / ValidationAgent /
ReviewerAgent / FinalQAAgent 共同使用

注意：
本文件只负责读取、整理、合并上下文；
不会调用 LLM；
不会生成最终推荐；
不会做 SNP/InDel calling；
不会做文献在线检索。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from breeding_agent.integration.flavonoid_marker_aggregator import (
    ANNOTATION_EVIDENCE,
    GENOME_VARIANT_EVIDENCE,
    LITERATURE_EVIDENCE,
    METABOLOME_EVIDENCE,
    REQUIRED_GENE_IDS,
    TRANSCRIPTOME_EVIDENCE,
)
from breeding_agent.integration.flavonoid_variant_evidence import (
    load_flavonoid_variant_evidence,
)
from breeding_agent.literature.loader import load_literature_results, records_to_dicts


def build_flavonoid_agent_context(
    *,
    evidence_dir: Path,
    candidate_rows: list[dict[str, str]] | None = None,
    variant_calling_dir: Path | None = None,
    variant_evidence_rows: list[dict[str, str]] | None = None,
    literature_results_path: Path | None = None,
    literature_results: list[dict[str, object]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """构建供黄酮候选标记 agents 使用的结构化上下文。

    这是本文件的核心函数。

    它会把分散在多个来源中的信息统一整理成一个 context 字典，
    后续多个 agent 都从这个 context 中读取数据。

    输入来源包括：

    1. evidence_dir 下的标准 evidence 文件：
       - transcriptome_evidence.tsv
       - metabolome_evidence.tsv
       - annotation_evidence.tsv
       - genome_variant_evidence.tsv
       - literature_evidence.tsv

    2. 上游聚合器传入的 candidate_rows：
       - 通常来自 flavonoid_marker_candidates.tsv；
       - 包含每个目标基因的多组学聚合结果。

    3. 可选 variant calling evidence：
       - 如果已经由 aggregate_candidates_node 传入 variant_evidence_rows，
         则直接使用；
       - 否则如果传入 variant_calling_dir，
         则调用 load_flavonoid_variant_evidence() 读取。

    4. 可选 literature results：
       - 如果已经传入 literature_results，则直接使用；
       - 否则如果传入 literature_results_path，
         则读取 JSONL 文献结果。

    5. warnings：
       - 接收上游已有 warning；
       - 继续追加 context 构建阶段发现的缺失文件或读取警告。

    Args:
        evidence_dir:
            evidence 文件目录。

        candidate_rows:
            可选候选标记聚合结果。
            一般来自 flavonoid_marker_aggregator.py。

        variant_calling_dir:
            可选 candidate-region variant calling 输出目录。

        variant_evidence_rows:
            可选已加载的 variant evidence 行。
            如果该参数已有内容，则无需重复从 variant_calling_dir 读取。

        literature_results_path:
            可选外部文献检索结果 JSONL 文件路径。

        literature_results:
            可选已加载的文献检索结果。
            如果该参数已有内容，则无需重复从 literature_results_path 读取。

        warnings:
            上游传入的 warning 列表。

    Returns:
        context:
            结构化上下文字典。

            后续 agent 会从这里读取：
            - hard_requirements；
            - evidence_by_gene；
            - transcriptomics_evidence；
            - metabolomics_evidence；
            - annotation_evidence；
            - genome_variant_evidence；
            - literature_evidence；
            - literature_results；
            - variant_calling_evidence；
            - candidate_rows；
            - warnings。
    """

    # 复制上游 warnings。
    # 使用 list(warnings or []) 是为了避免直接修改调用方传入的原列表对象。
    context_warnings = list(warnings or [])

    # 构建 evidence 文件路径映射。
    #
    # key 是上下文中使用的组学名称；
    # value 是实际 TSV 文件路径。
    evidence_files = {
        "transcriptomics": evidence_dir / TRANSCRIPTOME_EVIDENCE,
        "metabolomics": evidence_dir / METABOLOME_EVIDENCE,
        "annotation": evidence_dir / ANNOTATION_EVIDENCE,
        "genome_variant": evidence_dir / GENOME_VARIANT_EVIDENCE,
        "literature": evidence_dir / LITERATURE_EVIDENCE,
    }

    # 读取各类 evidence TSV。
    #
    # 如果文件缺失，_read_tsv() 不会抛异常，
    # 而是追加 warning 并返回空列表。
    transcriptomics_rows = _read_tsv(evidence_files["transcriptomics"], context_warnings)
    metabolomics_rows = _read_tsv(evidence_files["metabolomics"], context_warnings)
    annotation_rows = _read_tsv(evidence_files["annotation"], context_warnings)
    genome_variant_rows = _read_tsv(evidence_files["genome_variant"], context_warnings)
    literature_rows = _read_tsv(evidence_files["literature"], context_warnings)

    # 加载外部文献检索结果。
    #
    # 如果调用方已经传入 literature_results，就直接使用；
    # 如果没有传入，但提供了 literature_results_path，则从 JSONL 文件读取。
    loaded_literature_results = list(literature_results or [])
    if literature_results_path is not None and not loaded_literature_results:
        loaded_literature_results = records_to_dicts(
            load_literature_results(literature_results_path)
        )

    # 加载 candidate-region variant calling evidence。
    #
    # 优先使用调用方已经传入的 variant_evidence_rows，
    # 避免重复读取和重复解析。
    loaded_variant_rows = list(variant_evidence_rows or [])

    # 标记当前是否成功接入 variant calling evidence。
    variant_calling_loaded = False

    # 如果传入 variant_calling_dir 且没有预先传入 variant_evidence_rows，
    # 则从 variant_calling_dir 中读取 variant evidence。
    if variant_calling_dir is not None and not loaded_variant_rows:
        variant_result = load_flavonoid_variant_evidence(variant_calling_dir)
        loaded_variant_rows = variant_result.rows
        variant_calling_loaded = variant_result.loaded
        context_warnings.extend(variant_result.warnings)

    # 如果调用方已经传入 variant_evidence_rows，
    # 并且 variant_calling_dir 不为空，则认为 variant calling evidence 已接入。
    elif variant_calling_dir is not None:
        variant_calling_loaded = True

    # 按固定目标基因组织 evidence。
    #
    # evidence_by_gene 是后续 agent 最常用的结构之一。
    # 它把每个 gene_id 的转录组、代谢组、注释、基因组、变异检测、
    # candidate 聚合结果放在同一个字典下。
    #
    # 例如：
    # evidence_by_gene["Si9g04210.1"]["transcriptomics"]
    # evidence_by_gene["Si9g04210.1"]["metabolomics"]
    # evidence_by_gene["Si9g04210.1"]["candidate"]
    evidence_by_gene = {
        gene_id: {
            "transcriptomics": _row_by_gene(transcriptomics_rows, gene_id),
            "metabolomics": _row_by_gene(metabolomics_rows, gene_id),
            "annotation": _row_by_gene(annotation_rows, gene_id),
            "genome_variant": _row_by_gene(genome_variant_rows, gene_id),
            "variant_calling": _row_by_gene(loaded_variant_rows, gene_id),
            "candidate": _row_by_gene(candidate_rows or [], gene_id),
        }
        for gene_id in REQUIRED_GENE_IDS
    }

    # 返回完整 agent context。
    #
    # 这个 context 是“LLM-ready”的意思是：
    # 它结构清晰，适合传给 agent 或 LLM reviewer 使用。
    # 但本函数本身不会调用 LLM。
    return {
        # 当前任务类型。
        "task": "flavonoid_marker_recommendation",

        # 固定目标基因列表。
        "target_genes": list(REQUIRED_GENE_IDS),

        # 硬性业务要求和安全边界。
        #
        # 这些要求会被后续 agent / reviewer / QA 使用，
        # 用于防止报告越界。
        "hard_requirements": {
            # 核心输入文件说明。
            "core_inputs": {
                "transcriptomics": "bam/ 中所有文件",
                "metabolomics": "metabolome_raw_3372.tsv",
                "genome": "genome.fa 和 genome.gff",
                "annotation": "local_region_emapper_annotations.tsv",
            },

            # 报告中必须保持的核心结论方向。
            "required_conclusion": (
                "优先围绕 Si9g04210.1、Si5g31340.1、Si9g34380.1 开发候选 "
                "SNP/InDel/KASP 标记，再用更大群体的基因型和黄酮含量数据验证关联。"
            ),

            # DOI 不允许虚构。
            "do_not_fabricate_doi": True,

            # 不允许虚构 SNP/InDel 位点坐标。
            "do_not_fabricate_variant_positions": True,

            # LowQual 变异不能被优先推荐。
            "lowqual_not_prioritized": True,

            # KASP/CAPS 只能是 preliminary，不能说成最终标记。
            "preliminary_kasp_caps_not_final": True,

            # 当前 candidate-region variant calling 不能说成 WGS/GBS 群体变异检测。
            "variant_calling_not_wgs_gbs_population_calling": True,

            # LLM 不允许新增 DOI。
            "llm_may_not_add_doi": True,

            # demo 文献 fixture 不能当作真实 PubMed evidence。
            "demo_literature_not_real_evidence": True,
        },

        # evidence 输入目录。
        "evidence_dir": str(evidence_dir),

        # 各 evidence 文件路径。
        "evidence_files": {key: str(path) for key, path in evidence_files.items()},

        # 原始读取到的各类 evidence 行。
        "transcriptomics_evidence": transcriptomics_rows,
        "metabolomics_evidence": metabolomics_rows,
        "annotation_evidence": annotation_rows,
        "genome_variant_evidence": genome_variant_rows,
        "literature_evidence": literature_rows,

        # 外部文献结果路径和加载后的文献结果。
        "literature_results_path": (
            str(literature_results_path) if literature_results_path else None
        ),
        "literature_results": loaded_literature_results,

        # candidate-region variant calling evidence。
        "variant_calling_evidence": loaded_variant_rows,

        # 上游聚合出的候选标记记录。
        "candidate_rows": list(candidate_rows or []),

        # 按基因组织的 evidence，方便 agent 逐基因分析。
        "evidence_by_gene": evidence_by_gene,

        # variant calling 接入状态。
        "variant_calling": {
            "dir": str(variant_calling_dir) if variant_calling_dir else None,
            "loaded": variant_calling_loaded,
        },

        # 汇总 warnings。
        "warnings": context_warnings,
    }


def _read_tsv(path: Path, warnings: list[str]) -> list[dict[str, str]]:
    """读取 TSV 文件为字典列表。

    Args:
        path:
            TSV 文件路径。

        warnings:
            用于累计缺失文件 warning。

    Returns:
        rows:
            TSV 记录列表。
            每行是一个 dict，key 为表头字段名。

    行为：
        - 如果文件不存在：
          追加 warning，并返回空列表；
        - 如果文件存在：
          使用 csv.DictReader 按 tab 分隔读取。
    """

    if not path.exists():
        warnings.append(f"Context evidence file missing: {path}")
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def _row_by_gene(rows: list[dict[str, str]], gene_id: str) -> dict[str, str]:
    """从记录列表中查找指定 gene_id 对应的行。

    Args:
        rows:
            evidence 或 candidate 行列表。

        gene_id:
            目标基因 ID。

    Returns:
        如果找到 gene_id 匹配的行，返回该行；
        如果没有找到，返回空字典。

    匹配逻辑：
        读取 row["gene_id"]，去掉首尾空白后与 gene_id 比较。
    """

    for row in rows:
        if row.get("gene_id", "").strip() == gene_id:
            return row

    return {}