"""Deterministic observable facts, without guessing business-policy applicability."""

from collections import Counter

from .schemas import ApplicabilityConstraint, PreEvaluationFacts


def extract_facts(conversation, checklist):
    agents = [m for m in conversation.messages if m.role == "agent"]
    counts = Counter(m.role for m in conversation.messages)
    return PreEvaluationFacts(
        message_count=len(conversation.messages),
        role_counts={role: counts[role] for role in ("customer", "agent", "bot", "system")},
        first_agent_message_id=agents[0].message_id if agents else None,
        last_agent_message_id=agents[-1].message_id if agents else None,
        applicability_constraints=[ApplicabilityConstraint(
            criterion_id=c.criterion_id, na_allowed=c.na_condition is not None,
            allowed_condition=c.na_condition, rule=c.applicability_rule) for c in checklist.criteria])
