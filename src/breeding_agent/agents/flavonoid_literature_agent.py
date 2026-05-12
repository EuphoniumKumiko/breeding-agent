"""Rule-based literature evidence reader for flavonoid marker reports.

本文件实现 LiteratureAgent。它读取 literature_evidence.tsv 和可选 literature_results JSONL，生成文献分析、query plan、allowed_report_dois 和文献综述文本。

边界：不在线调用 PubMed，不调用 LLM，不补写 DOI；source=PubMedFixture 或 is_demo=true 的记录只能作为 demo，不计入真实 PubMed evidence。"""

from __future__ import annotations

from pathlib import Path

from breeding_agent.agents.base import AgentOutput, LLMReadyAgentMixin, RuleBasedAgent
from breeding_agent.agents.prompt_templates import literature_agent_prompt
from breeding_agent.integration.flavonoid_marker_aggregator import (
    read_literature_evidence,
)
from breeding_agent.literature.analyzer import (
    LiteratureAnalysis,
    analyze_literature,
)
from breeding_agent.literature.loader import load_literature_results
from breeding_agent.literature.normalizer import normalize_literature_row
from breeding_agent.literature.query_builder import build_literature_query_plan
from breeding_agent.literature.schema import LiteratureRecord


# LiteratureAgent 只读取已有文献 evidence 和本地 JSONL，不在线检索、不补 DOI。
class FlavonoidLiteratureAgent(LLMReadyAgentMixin, RuleBasedAgent):
    """Read seed literature evidence without fabricating DOI values."""

    agent_name = "literature_agent"
    prompt_template = literature_agent_prompt

    def __init__(
        self,
        evidence_dir: Path,
        literature_results_path: Path | None = None,
    ) -> None:
        self.evidence_dir = evidence_dir
        self.literature_results_path = literature_results_path

    def run(self) -> dict[str, object]:
        """顺序执行规则版黄酮候选标记推荐流程，并返回完整 agent_result。"""
        literature_rows = read_literature_evidence(self.evidence_dir)
        literature_results = load_literature_results(self.literature_results_path)
        result = self._run_rule(literature_rows, literature_results, {})
        agent_output = self._agent_output(result)
        return {
            **result,
            "agent_output": agent_output.to_dict(),
        }

    def run_with_context(self, context: dict[str, object]) -> AgentOutput:
        # Context-based entry point used by LangGraph: evidence rows, optional
        # external results, and the already-built agent context all flow here.
        literature_rows = _as_rows(context.get("literature_evidence", []))
        literature_results = _as_literature_records(
            context.get("literature_results", [])
        )
        if not literature_results:
            path_text = str(context.get("literature_results_path", "") or "").strip()
            if path_text:
                literature_results = load_literature_results(Path(path_text))
        result = self._run_rule(literature_rows, literature_results, context)
        return self._agent_output(result)

    def _run_rule(
        self,
        literature_rows: list[dict[str, str]],
        literature_results: list[LiteratureRecord],
        context: dict[str, object],
    ) -> dict[str, object]:
        # The rule path keeps verified DOI evidence and external search results
        # separate, then derives a query plan from the same evidence context.
        warnings = []
        if not literature_rows:
            warnings.append(
                f"Literature evidence file missing or empty: {self.evidence_dir}"
            )

        missing_doi_rows = [
            row.get("title", row.get("query", "unknown"))
            for row in literature_rows
            if not row.get("doi", "").strip()
        ]
        if missing_doi_rows:
            warnings.append(
                "Literature rows without DOI: " + ", ".join(missing_doi_rows)
            )
        demo_count = sum(1 for record in literature_results if not record.is_real_evidence)
        if demo_count:
            warnings.append(
                f"External literature results contain {demo_count} demo fixture row(s); "
                "they are excluded from real DOI evidence counts."
            )

        analysis = analyze_literature(
            verified_literature_rows=literature_rows,
            literature_results=literature_results,
        )
        query_plan = build_literature_query_plan(
            {
                **context,
                "literature_evidence": literature_rows,
            }
        )

        return {
            "literature_rows": literature_rows,
            "literature_results": [record.to_dict() for record in literature_results],
            "literature_analysis": analysis.to_dict(),
            "literature_query_plan": [row.to_dict() for row in query_plan],
            "allowed_report_dois": sorted(analysis.allowed_report_dois),
            "literature_review_text": self._render_literature_review(
                literature_rows,
                analysis,
            ),
            "warnings": warnings,
        }

    def _agent_output(self, result: dict[str, object]) -> AgentOutput:
        literature_rows = _as_rows(result.get("literature_rows", []))
        analysis = result.get("literature_analysis", {})
        result_count = (
            analysis.get("literature_result_count", 0)
            if isinstance(analysis, dict)
            else 0
        )
        warnings = [str(warning) for warning in result.get("warnings", [])]
        return AgentOutput(
            agent_name=self.agent_name,
            summary=(
                f"Read {len(literature_rows)} verified DOI seed rows and "
                f"{result_count} external literature result rows."
            ),
            evidence_used=["literature_evidence.tsv", "literature_results_jsonl"],
            warnings=warnings,
            limitations=[
                "Only DOI values present in evidence are displayed.",
                "No external literature API is called.",
                "Demo fixture rows are marked and excluded from real DOI evidence counts.",
            ],
            structured_payload=result,
        )

    def _render_literature_review(
        self,
        literature_rows: list[dict[str, str]],
        analysis: LiteratureAnalysis,
    ) -> str:
        # The review text explains evidence provenance first, then shows the
        # external search table with explicit relevance and boundary labels.
        if not literature_rows and analysis.literature_result_count == 0:
            return (
                "文献查询与分析：未读取到 `literature_evidence.tsv` 或外部 JSONL。当前不能展示 DOI；"
                "后续只能补充经过核验的 DOI，不能编造 DOI。"
            )

        lines = [
            "文献查询与分析：文献查阅过程只读取 `literature_evidence.tsv` 与可选 `--literature-results` JSONL，",
            "不调用外部 API，不补写未核对 DOI；LLM 只能做筛选、归纳、解释和建议，不能新增 DOI。",
            "",
            f"- verified DOI seed evidence: {analysis.verified_doi_count}",
            f"- external literature results: {analysis.literature_result_count}",
            f"- external query count: {analysis.literature_query_count}",
            f"- real external result rows: {analysis.real_result_count}",
            f"- demo fixture rows: {analysis.demo_result_count}（不计入真实 PubMed evidence）",
            "- external relevance counts: "
            f"high={analysis.literature_relevance_counts.get('high', 0)}, "
            f"medium={analysis.literature_relevance_counts.get('medium', 0)}, "
            f"background={analysis.literature_relevance_counts.get('background', 0)}",
            f"- matched terms: {', '.join(analysis.matched_terms) if analysis.matched_terms else 'NA'}",
            "",
            "### 已核验 DOI evidence",
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
        if not literature_rows:
            lines.append("| NA | NA | NA | NA | NA |")

        lines.extend(
            [
                "",
                "### 外部文献检索结果分析",
                "| type | query | title | year | DOI | source | relevance_level | matched_terms | conclusion_boundary |",
                "| --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
            ]
        )
        selected_records = [
            *analysis.real_records[:8],
            *analysis.demo_records[:5],
        ]
        for record in selected_records:
            is_demo = bool(record.get("is_demo")) or record.get("source") == "PubMedFixture"
            doi_display = "DEMO_ONLY" if is_demo and record.get("doi") else _cell(record, "doi")
            relevance_level = str(record.get("relevance_level", "background") or "background")
            lines.append(
                "| {kind} | {query} | {title} | {year} | {doi} | {source} | {relevance_level} | {terms} | {boundary} |".format(
                    kind="demo fixture" if is_demo else "real result",
                    query=_cell(record, "query"),
                    title=_cell(record, "title"),
                    year=_cell(record, "year"),
                    doi=doi_display,
                    source=_cell(record, "source"),
                    relevance_level=relevance_level,
                    terms=", ".join(str(item) for item in record.get("matched_terms", []))
                    or "NA",
                    boundary=(
                        "demo only; excluded from real DOI evidence"
                        if is_demo
                        else _relevance_boundary(relevance_level, record)
                    ),
                )
            )
        if not selected_records:
            lines.append("| NA | NA | NA | NA | NA | NA | NA | NA | NA |")

        lines.extend(
            [
                "",
                "分析边界：上述文献结果只能支持候选基因、黄酮通路、代谢组或标记开发背景的解释；",
                "不能据此声称已经完成最终 KASP/CAPS 标记、WGS/GBS 群体验证或湿实验验证。",
            ]
        )
        return "\n".join(lines)


def _relevance_boundary(relevance_level: str, record: dict[str, object]) -> str:
    gene_hits = record.get("gene_hit_ids", [])
    if isinstance(gene_hits, list) and gene_hits:
        return (
            "gene-id matched literature context; not direct experimental evidence "
            "unless manually verified"
        )
    if relevance_level == "high":
        return "directly relevant candidate/background support"
    if relevance_level == "medium":
        return "related millet/flavonoid background"
    return "background only; not used as gene-specific support"


def _cell(row: dict[str, str], key: str) -> str:
    value = row.get(key, "")
    if value is None or value == "":
        return "NA"
    return str(value).replace("\n", " ").replace("|", "\\|")


def _as_rows(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _as_literature_records(value: object) -> list[LiteratureRecord]:
    if not isinstance(value, list):
        return []
    records: list[LiteratureRecord] = []
    for item in value:
        if isinstance(item, LiteratureRecord):
            records.append(item)
        elif isinstance(item, dict):
            records.append(normalize_literature_row(item))
    return records
