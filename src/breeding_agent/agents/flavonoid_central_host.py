"""DeepRare-like lightweight central host for flavonoid marker aggregation."""

from __future__ import annotations

from pathlib import Path

from breeding_agent.agents.flavonoid_final_qa_agent import FlavonoidFinalQAAgent
from breeding_agent.agents.flavonoid_literature_agent import (
    FlavonoidLiteratureAgent,
)
from breeding_agent.agents.flavonoid_marker_recommendation_agent import (
    FlavonoidMarkerRecommendationAgent,
)
from breeding_agent.agents.flavonoid_reviewer_agent import FlavonoidReviewerAgent
from breeding_agent.agents.flavonoid_validation_agent import (
    FlavonoidValidationAgent,
)
from breeding_agent.integration.flavonoid_marker_aggregator import (
    REQUIRED_GENE_IDS,
    aggregate_flavonoid_marker_candidates,
)
from breeding_agent.reports.flavonoid_marker_report import (
    render_flavonoid_marker_report,
)


class FlavonoidCentralHost:
    """Coordinate rule-based flavonoid marker agents without external calls."""

    def __init__(
        self,
        *,
        evidence_dir: Path,
        outdir: Path,
        target_genes: list[str] | None = None,
    ) -> None:
        self.evidence_dir = evidence_dir
        self.outdir = outdir
        self.target_genes = target_genes or list(REQUIRED_GENE_IDS)

    def run(self) -> dict[str, object]:
        aggregation_result = aggregate_flavonoid_marker_candidates(
            evidence_dir=self.evidence_dir,
            outdir=self.outdir,
        )
        candidate_rows = aggregation_result.candidate_rows
        warnings = list(aggregation_result.warnings)

        if self.target_genes != REQUIRED_GENE_IDS:
            warnings.append(
                "CentralHost received non-default target_genes; current aggregator "
                "keeps the fixed high-priority gene set."
            )

        literature_result = FlavonoidLiteratureAgent(self.evidence_dir).run()
        marker_result = FlavonoidMarkerRecommendationAgent().run(candidate_rows)
        validation_result = FlavonoidValidationAgent().run(candidate_rows)
        warnings.extend(literature_result.get("warnings", []))

        base_report_text = render_flavonoid_marker_report(
            evidence_dir=self.evidence_dir,
            candidate_rows=candidate_rows,
            literature_rows=literature_result["literature_rows"],
            warnings=warnings,
            literature_review_text=str(literature_result["literature_review_text"]),
            marker_recommendation_text=str(
                marker_result["marker_recommendation_text"]
            ),
            validation_plan_text=str(validation_result["validation_plan_text"]),
        )
        reviewer_result = FlavonoidReviewerAgent().run(
            candidate_rows=candidate_rows,
            literature_review_text=str(literature_result["literature_review_text"]),
            marker_recommendation_text=str(
                marker_result["marker_recommendation_text"]
            ),
            validation_plan_text=str(validation_result["validation_plan_text"]),
            report_text=base_report_text,
        )
        report_text_without_qa = render_flavonoid_marker_report(
            evidence_dir=self.evidence_dir,
            candidate_rows=candidate_rows,
            literature_rows=literature_result["literature_rows"],
            warnings=warnings,
            literature_review_text=str(literature_result["literature_review_text"]),
            marker_recommendation_text=str(
                marker_result["marker_recommendation_text"]
            ),
            validation_plan_text=str(validation_result["validation_plan_text"]),
            reviewer_notes=str(reviewer_result["reviewer_notes"]),
        )
        qa_result = FlavonoidFinalQAAgent().run(report_text_without_qa)
        final_report_text = render_flavonoid_marker_report(
            evidence_dir=self.evidence_dir,
            candidate_rows=candidate_rows,
            literature_rows=literature_result["literature_rows"],
            warnings=warnings,
            literature_review_text=str(literature_result["literature_review_text"]),
            marker_recommendation_text=str(
                marker_result["marker_recommendation_text"]
            ),
            validation_plan_text=str(validation_result["validation_plan_text"]),
            reviewer_notes=str(reviewer_result["reviewer_notes"]),
            qa_result=qa_result,
        )
        qa_result = FlavonoidFinalQAAgent().run(final_report_text)

        return {
            "candidate_file": aggregation_result.candidate_file,
            "candidate_rows": candidate_rows,
            "literature_rows": literature_result["literature_rows"],
            "literature_review_text": literature_result["literature_review_text"],
            "marker_recommendations": marker_result["recommendations_by_gene"],
            "marker_recommendation_text": marker_result[
                "marker_recommendation_text"
            ],
            "validation_plan_text": validation_result["validation_plan_text"],
            "reviewer_notes": reviewer_result["reviewer_notes"],
            "reviewer_result": reviewer_result,
            "qa_result": qa_result,
            "report_text": final_report_text,
            "warnings": warnings,
            "agent_layer": {
                "mode": "rule_based_deeprare_like_lightweight",
                "uses_llm": False,
                "uses_external_api": False,
                "target_genes": self.target_genes,
            },
        }
