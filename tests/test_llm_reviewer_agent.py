"""Tests for optional local LLM ReviewerAgent integration."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from breeding_agent.agents.flavonoid_reviewer_agent import FlavonoidReviewerAgent
from breeding_agent.graphs.flavonoid_marker_graph import (
    initial_graph_state,
    reviewer_agent_node,
)
from breeding_agent.llm.adapter_base import LLMConfig, LLMRequest, LLMResponse
from breeding_agent.llm.executor import load_llm_config, run_llm_reviewer
from breeding_agent.llm.openai_compatible_adapter import OpenAICompatibleAdapter
from breeding_agent.llm.output_guard import guard_reviewer_output


class TestLLMReviewerAgent(unittest.TestCase):
    def test_config_loader_reads_openai_compatible_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "llm.yaml"
            path.write_text(
                "\n".join(
                    [
                        "enabled: false",
                        "provider: openai_compatible",
                        "base_url: http://127.0.0.1:1234/v1",
                        "model: qwen/qwen3.5-9b",
                        "temperature: 0.1",
                        "max_output_tokens: 888",
                        "chat_template_kwargs:",
                        "  enable_thinking: false",
                        "enabled_agents:",
                        "  - reviewer_agent",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_llm_config(path)

        self.assertFalse(config.enabled)
        self.assertEqual(config.provider, "openai_compatible")
        self.assertEqual(config.base_url, "http://127.0.0.1:1234/v1")
        self.assertEqual(config.model, "qwen/qwen3.5-9b")
        self.assertEqual(config.max_tokens, 888)
        self.assertEqual(config.chat_template_kwargs["enable_thinking"], False)
        self.assertEqual(config.enabled_agents, ["reviewer_agent"])

    def test_openai_compatible_adapter_passes_enable_thinking_false(self) -> None:
        captured: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {"model": "qwen/qwen3.5-9b", "choices": [{"message": {"content": "ok"}}]}
                ).encode("utf-8")

        def fake_urlopen(req: object, timeout: int) -> FakeResponse:
            captured["timeout"] = timeout
            captured["payload"] = json.loads(getattr(req, "data").decode("utf-8"))
            return FakeResponse()

        config = LLMConfig(
            enabled=False,
            base_url="http://127.0.0.1:1234/v1",
            model="qwen/qwen3.5-9b",
            max_tokens=100,
            timeout_seconds=12,
        )
        llm_request = LLMRequest(
            messages=[{"role": "user", "content": "review"}],
            model=config.model,
            temperature=0.1,
            max_tokens=100,
            chat_template_kwargs={"enable_thinking": False},
        )
        with mock.patch(
            "breeding_agent.llm.openai_compatible_adapter.request.urlopen",
            side_effect=fake_urlopen,
        ):
            response = OpenAICompatibleAdapter(config).complete(llm_request)

        self.assertEqual(response.content, "ok")
        self.assertEqual(captured["timeout"], 12)
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})

    def test_output_guard_blocks_fabricated_doi_and_coordinates(self) -> None:
        context = {
            "literature_evidence": [{"doi": "10.3390/life11060578"}],
            "report_text": "当前结果不能替代 WGS/GBS 群体变异检测。",
        }
        result = guard_reviewer_output(
            content=(
                "文献 DOI 10.9999/fake 不在输入中。chr1:12345 可作为 SNP。"
                "当前结果不能替代 WGS/GBS 群体变异检测。"
            ),
            context=context,
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("fabricated_doi" in reason for reason in result.reasons))
        self.assertIn("possible_fabricated_snp_indel_coordinate", result.reasons)

    def test_output_guard_accepts_boundary_preserving_review(self) -> None:
        context = {"literature_evidence": [{"doi": "10.3390/life11060578"}]}
        result = guard_reviewer_output(
            content=(
                "可保留 DOI 10.3390/life11060578。LowQual 位点不应直接优先用于开发。"
                "preliminary KASP/CAPS screening 不是最终标记或最终引物。"
                "当前结果不能替代 WGS/GBS 群体变异检测。"
            ),
            context=context,
        )
        self.assertTrue(result.passed, result.reasons)

    def test_executor_falls_back_on_empty_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "llm.yaml"
            path.write_text(
                "\n".join(
                    [
                        "enabled: true",
                        "provider: openai_compatible",
                        "base_url: http://127.0.0.1:1234/v1",
                        "model: qwen/qwen3.5-9b",
                        "enabled_agents:",
                        "  - reviewer_agent",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "breeding_agent.llm.executor.OpenAICompatibleAdapter"
            ) as adapter_cls:
                adapter_cls.return_value.complete.return_value = LLMResponse(
                    content="",
                    model="qwen/qwen3.5-9b",
                    raw_response={},
                )
                result = run_llm_reviewer(
                    context={},
                    llm_config_path=path,
                    rule_reviewer_notes="rule reviewer notes",
                    enabled=True,
                )

        self.assertFalse(result.llm_used)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.fallback_reason, "empty_final_content")

    def test_enabled_flag_reaches_initial_graph_state_agent_context(self) -> None:
        state = initial_graph_state(
            evidence_dir=Path("outputs/flavonoid_marker_from_package/evidence"),
            outdir=Path("outputs/flavonoid_marker_langgraph_llm"),
            variant_calling_dir=Path("outputs/genomics_variant_calling"),
            llm_reviewer_enabled=True,
            llm_config_path=Path("configs/llm.local.yaml"),
        )

        agent_context = state["agent_context"]
        self.assertIsInstance(agent_context, dict)
        llm_config = agent_context["_llm_reviewer_config"]
        self.assertEqual(llm_config["llm_reviewer_enabled"], True)
        self.assertEqual(llm_config["llm_config_path"], "configs/llm.local.yaml")

    def test_reviewer_node_enabled_config_does_not_report_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "llm.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "enabled: true",
                        "provider: openai_compatible",
                        "base_url: http://127.0.0.1:9/v1",
                        "model: qwen/qwen3.5-9b",
                        "enabled_agents:",
                        "  - reviewer_agent",
                    ]
                ),
                encoding="utf-8",
            )
            state = initial_graph_state(
                evidence_dir=Path("outputs/flavonoid_marker_from_package/evidence"),
                outdir=Path(tmpdir),
                llm_reviewer_enabled=True,
                llm_config_path=config_path,
            )
            state["candidate_rows"] = [
                {
                    "gene_id": "Si9g04210.1",
                    "baseMean": "1",
                    "log2FC": "2",
                    "pvalue": "0.01",
                    "padj": "0.02",
                }
            ]
            state["literature_review_text"] = "DOI 10.3390/life11060578"
            state["marker_recommendation_text"] = "SNP InDel KASP CAPS"
            state["validation_plan_text"] = "Sanger qRT-PCR LC-MS/MS"

            with mock.patch(
                "breeding_agent.llm.executor.OpenAICompatibleAdapter"
            ) as adapter_cls:
                adapter_cls.return_value.complete.side_effect = RuntimeError(
                    "adapter down"
                )
                result_state = reviewer_agent_node(state)

        metadata = result_state["agent_context"]["_llm_reviewer_metadata"]
        self.assertEqual(metadata["llm_reviewer_enabled"], True)
        self.assertEqual(metadata["llm_used"], False)
        self.assertEqual(metadata["fallback_used"], True)
        self.assertEqual(metadata["model"], "qwen/qwen3.5-9b")
        self.assertIn("llm_request_failed", metadata["fallback_reason"])
        self.assertNotEqual(metadata["fallback_reason"], "llm_reviewer_disabled")

    def test_disabled_reviewer_never_calls_adapter(self) -> None:
        with mock.patch("breeding_agent.llm.executor.OpenAICompatibleAdapter") as adapter_cls:
            result = run_llm_reviewer(
                context={},
                llm_config_path=None,
                rule_reviewer_notes="rule reviewer notes",
                enabled=False,
            )
        adapter_cls.assert_not_called()
        self.assertFalse(result.llm_reviewer_enabled)
        self.assertFalse(result.llm_used)
        self.assertEqual(result.fallback_reason, "llm_reviewer_disabled")

    def test_reviewer_agent_preserves_rule_notes_when_llm_is_attached(self) -> None:
        agent = FlavonoidReviewerAgent()
        output = agent.run_with_context(
            {
                "candidate_rows": [
                    {
                        "gene_id": "Si9g04210.1",
                        "baseMean": "1",
                        "log2FC": "2",
                        "pvalue": "0.01",
                        "padj": "0.02",
                    }
                ],
                "literature_review_text": "DOI 10.3390/life11060578",
                "marker_recommendation_text": "SNP InDel KASP CAPS",
                "validation_plan_text": "Sanger qRT-PCR LC-MS/MS",
                "report_text": "不能替代 WGS/GBS 群体变异检测。",
            }
        )
        merged = agent.add_llm_review(
            output,
            llm_review_text="LLM guarded reviewer note.",
            llm_metadata={
                "llm_reviewer_enabled": True,
                "llm_used": True,
                "fallback_used": False,
                "model": "qwen/qwen3.5-9b",
                "guard_passed": True,
                "fallback_reason": "",
            },
        )

        payload = merged.structured_payload
        self.assertIn("rule_reviewer_notes", payload)
        self.assertIn("LLM guarded reviewer note.", str(payload["reviewer_notes"]))
        self.assertEqual(payload["llm_reviewer"]["llm_used"], True)


if __name__ == "__main__":
    unittest.main()
