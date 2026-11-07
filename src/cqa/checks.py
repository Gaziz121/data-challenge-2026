"""Small extension seam: checks receive snapshots and return findings, never scores.

Pre checks can flag input concerns; post checks can perform criterion verification,
including a separately authorized second LLM later. No orchestration framework.
"""

from typing import Protocol

from .schemas import CheckInput, CheckOutcome, CheckFinding


class EvaluationCheck(Protocol):
    name: str
    version: str
    phase: str

    def run(self, context: CheckInput) -> CheckOutcome:
        ...


class AgentPresenceCheck:
    """Flag bot-only inputs for review; absence does not create an N/A exception."""
    name = "agent-presence"
    version = "1"
    phase = "pre_evaluation"

    def run(self, context):
        findings = []
        if context.facts.first_agent_message_id is None:
            findings.append(CheckFinding(
                code="no-human-agent", severity="review",
                criterion_ids=[c.criterion_id for c in context.checklist.criteria],
                explanation="No human agent turn is present; inspect operator-evaluation applicability. "
                            "This finding does not assign N/A or alter any decision."))
        return CheckOutcome(check_name=self.name, check_version=self.version,
                            phase=self.phase, findings=findings)
