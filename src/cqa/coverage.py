"""Recompute exact source-ID coverage from cited scopes; never extend evidence."""

from .io import digest
from .schemas import CoverageProof


def coverage_proof(conversation, criterion_id, evidence, path):
    messages = conversation.messages
    required = [m.message_id for m in messages]
    positions = {mid: i for i, mid in enumerate(required)}
    covered, invalid = set(), []
    for i, e in enumerate(evidence if isinstance(evidence, list) else []):
        if not isinstance(e, dict) or e.get("kind") != "scope":
            continue  # Quotes and omission markers cannot prove exhaustive inspection.
        start, end = e.get("start_message_id"), e.get("end_message_id")
        if (not isinstance(start, str) or not isinstance(end, str)
                or start not in positions or end not in positions or positions[start] > positions[end]):
            invalid.append(i)
            continue
        covered.update(required[positions[start]:positions[end] + 1])
    missing = [mid for mid in required if mid not in covered]
    return CoverageProof(criterion_id=criterion_id, evidence_path=path,
                         conversation_sha256=digest(conversation.model_dump(mode="json")),
                         messages_sha256=digest([m.model_dump(mode="json") for m in messages]),
                         required_message_ids=required, covered_message_ids=[mid for mid in required if mid in covered],
                         missing_message_ids=missing, invalid_scope_indices=invalid,
                         complete=not missing and not invalid)


def decision_coverage(conversation, criterion, values):
    if criterion.kind != "critical" or values.get("response") != "no":
        return []
    proofs = [coverage_proof(conversation, criterion.criterion_id, values.get("evidence"), ["evidence"])]
    if criterion.evidence_policy.negative_coverage == "decision_and_atomic":
        mapped = {q.question_id for q in criterion.questions if q.violation_category is not None}
        atomics = values.get("atomic_checks")
        for i, atomic in enumerate(atomics if isinstance(atomics, list) else []):
            if (isinstance(atomic, dict) and isinstance(atomic.get("question_id"), str)
                    and atomic["question_id"] in mapped and atomic.get("answer") == "no"):
                proofs.append(coverage_proof(conversation, criterion.criterion_id, atomic.get("evidence"),
                                             ["atomic_checks", i, "evidence"]))
    return proofs


def assess_output(raw, conversation, checklist):
    from .decision_rules import assess_decision
    rules, proofs = [], []
    criteria = {c.criterion_id: c for c in checklist.criteria}
    decisions = raw.get("decisions") if isinstance(raw, dict) else None
    for values in decisions if isinstance(decisions, list) else []:
        cid = values.get("criterion_id") if isinstance(values, dict) else None
        if not isinstance(cid, str) or cid not in criteria:
            continue
        criterion = criteria[cid]
        assessment = assess_decision(criterion, values)
        if assessment:
            rules.append(assessment)
        proofs.extend(decision_coverage(conversation, criterion, values))
    return rules, proofs
