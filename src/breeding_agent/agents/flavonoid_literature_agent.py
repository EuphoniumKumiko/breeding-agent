"""Rule-based literature evidence reader for flavonoid marker reports."""

from __future__ import annotations

from pathlib import Path

from breeding_agent.agents.base import AgentOutput, LLMReadyAgentMixin, RuleBasedAgent
from breeding_agent.agents.prompt_templates import literature_agent_prompt
from breeding_agent.integration.flavonoid_marker_aggregator import (
    read_literature_evidence,
)


class FlavonoidLiteratureAgent(LLMReadyAgentMixin, RuleBasedAgent):
    """Read seed literature evidence without fabricating DOI values."""

    agent_name = "literature_agent"
    prompt_template = literature_agent_prompt

    def __init__(self, evidence_dir: Path) -> None:
        self.evidence_dir = evidence_dir

    def run(self) -> dict[str, object]:
        literature_rows = read_literature_evidence(self.evidence_dir)
        result = self._run_rule(literature_rows)
        agent_output = self._agent_output(result)
        return {
            **result,
            "agent_output": agent_output.to_dict(),
        }

    def run_with_context(self, context: dict[str, object]) -> AgentOutput:
        literature_rows = _as_rows(context.get("literature_evidence", []))
        result = self._run_rule(literature_rows)
        return self._agent_output(result)

    def _run_rule(
        self,
        literature_rows: list[dict[str, str]],
    ) -> dict[str, object]:
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

        return {
            "literature_rows": literature_rows,
            "literature_review_text": self._render_literature_review(
                literature_rows
            ),
            "warnings": warnings,
        }

    def _agent_output(self, result: dict[str, object]) -> AgentOutput:
        literature_rows = _as_rows(result.get("literature_rows", []))
        warnings = [str(warning) for warning in result.get("warnings", [])]
        return AgentOutput(
            agent_name=self.agent_name,
            summary=f"Read {len(literature_rows)} literature evidence rows.",
            evidence_used=["literature_evidence.tsv"],
            warnings=warnings,
            limitations=[
                "Only DOI values present in evidence are displayed.",
                "No external literature API is called.",
            ],
            structured_payload=result,
        )

    def _render_literature_review(
        self,
        literature_rows: list[dict[str, str]],
    ) -> str:
        if not literature_rows:
            return (
                "文献查阅过程：未读取到 `literature_evidence.tsv`。当前不能展示 DOI；"
                "后续只能补充经过核验的 DOI，不能编造 DOI。"
            )

        lines = [
            "文献查阅过程：本步骤只读取 `literature_evidence.tsv` 中已有记录，",
            "不调用外部 API，不补写未核对 DOI；以下 DOI 均按 evidence 原样展示。",
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


def _cell(row: dict[str, str], key: str) -> str:
    value = row.get(key, "")
    if value is None or value == "":
        return "NA"
    return str(value).replace("\n", " ").replace("|", "\\|")


def _as_rows(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]
