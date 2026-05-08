"""Final QA agent wrapping the existing flavonoid report QA rules."""

from __future__ import annotations

from breeding_agent.integration.flavonoid_marker_qa import (
    check_flavonoid_marker_report,
)


class FlavonoidFinalQAAgent:
    """Run the canonical rule-based QA without duplicating QA logic."""

    def run(self, report_text: str) -> dict[str, object]:
        return check_flavonoid_marker_report(report_text)
