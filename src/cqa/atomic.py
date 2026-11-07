"""Validate atomic observations, then explicitly materialize official decisions.

This is an input stage in the existing engine, not another evaluator/scorer.
An unsolicited model judgment on an atomic criterion is a conflict, never an
answer to overwrite. Unresolved/invalid criteria prevent a complete total.
"""

from pydantic import ValidationError

from .coverage import coverage_proof
from .decision_rules import assess_decision
from .schemas import AtomicCriterionOutput, AtomicCheck, CriterionReview, Decision, ModelEvaluation
from .validation import REVIEWABLE_EVIDENCE_POLICY, _validate_decision


class AtomicReviewRequired(ValueError):
    def __init__(self, reviews, issues, accepted):
        self.reviews, self.issues, self.accepted = reviews, issues, accepted
        super().__init__("Atomic observations require review; no complete total")


def _reference_issues(evidence, messages):
    issues = []
    for e in evidence:
        if e.kind == "quote":
            message = messages.get(e.message_id)
            if message is None or e.quote not in message.text or not any(c.isalnum() for c in e.quote):
                issues.append("Atomic quote must match meaningful text in its exact source message")
        else:
            start, end = messages.get(e.start_message_id), messages.get(e.end_message_id)
            if start is None or end is None or start.source_index > end.source_index:
                issues.append("Atomic scope has unknown or reversed source boundaries")
    return issues


def _identification_issues(criterion, observations, conversation, messages):
    policy = criterion.identification_policy
    if policy is None:
        return ["Event evidence is not configured for this criterion"] if any(a.events for a in observations.values()) else []
    need = observations[policy.need_question_id]
    verified = observations[policy.verified_question_id]
    issues, events = [], {}
    for qid, atomic in observations.items():
        if atomic.events and qid not in (policy.need_question_id, policy.verified_question_id):
            issues.append("Identification events must belong to configured identification questions")
        for event in atomic.events:
            message = messages.get(event.message_id)
            if (message is None or event.quote not in message.text or not any(c.isalnum() for c in event.quote)
                    or not any(e.kind == "quote" and e.message_id == event.message_id and e.quote == event.quote
                               for e in atomic.evidence)):
                issues.append("Identification event needs an exact matching atomic source quote")
                continue
            roles = (policy.verification_roles if event.kind == "verification" else
                     policy.action_roles if event.kind == "protected_action" else ["customer"])
            if message.role not in roles:
                issues.append("Identification event is attributed to an ineligible source role")
                continue
            events[(event.kind, event.message_id, event.quote)] = message.source_index
    requests = [index for (kind, _, _), index in events.items() if kind == "protected_request"]
    actions = [index for (kind, _, _), index in events.items() if kind == "protected_action"]
    confirmations = [index for (kind, _, _), index in events.items() if kind == "verification"]
    if need.answer == "no":
        if requests or actions:
            issues.append("Identification unnecessary conflicts with cited protected request/action events")
        if verified.answer != "not_applicable":
            issues.append("Verification check must be not_applicable when identification is unnecessary")
        if not coverage_proof(conversation, criterion.criterion_id,
                              [e.model_dump() for e in need.evidence], ["atomic_checks"]).complete:
            issues.append("Identification unnecessary requires full-dialogue source coverage")
    elif need.answer == "yes":
        if not requests and not actions:
            issues.append("Identification need requires a cited protected request or protected action")
        if verified.answer == "not_applicable":
            issues.append("Required identification cannot use not_applicable for verification")
        if verified.answer == "yes":
            if not confirmations or not actions:
                issues.append("Positive verification requires confirmation and a relevant protected action")
            elif any(not any(v < action for v in confirmations) for action in actions):
                issues.append("Verification must precede every protected action in source order; ties are unresolved")
        elif verified.answer == "no":
            if actions and all(any(v < action for v in confirmations) for action in actions):
                issues.append("Negative verification conflicts with confirmed-before-action events")
            if not coverage_proof(conversation, criterion.criterion_id,
                                  [e.model_dump() for e in verified.evidence], ["atomic_checks"]).complete:
                issues.append("Missing/late verification requires full-dialogue source coverage")
    return issues


def process_atomic_output(raw, conversation, checklist, evidence_gate="strict", exceptions=None):
    """Return validated projection + review ledger; never guess missing facts.

    evidence_gate="review" (explicit opt-in) records REVIEWABLE_EVIDENCE_POLICY issues as needs_review
    exceptions, appended to `exceptions`, instead of blocking. Everything else still blocks.
    """
    review_gate = evidence_gate == "review"
    exceptions = [] if exceptions is None else exceptions
    reviews, issues, accepted = [], [], []
    expected = {c.criterion_id: c for c in checklist.criteria}
    messages = {m.message_id: m for m in conversation.messages}
    if not isinstance(raw, dict) or raw.get("schema_version") != "1.2" or not isinstance(raw.get("criteria"), list):
        raise AtomicReviewRequired([], [{"criterion_id": None, "message": "Atomic output requires schema 1.2 and criteria array"}], [])
    if set(raw) != {"schema_version", "criteria"}:
        issues.append({"criterion_id": None, "message": "Unexpected atomic output root fields"})
    by_id = {}
    for item in raw["criteria"]:
        cid = item.get("criterion_id") if isinstance(item, dict) else None
        if not isinstance(cid, str) or cid not in expected:
            issues.append({"criterion_id": None, "message": "Unknown/missing atomic criterion ID"})
            continue
        by_id.setdefault(cid, []).append(item)
    for criterion in checklist.criteria:
        cid = criterion.criterion_id
        origin = "derived" if criterion.output_source == "atomic" else "model"
        entries = by_id.get(cid, [])
        if len(entries) != 1:
            review = CriterionReview(criterion_id=cid, state="schema_invalid", decision_origin=origin,
                                     issues=["Every configured criterion must occur exactly once"])
            reviews.append(review)
            continue
        item = entries[0]
        original_judgment = item.get("judgment") if isinstance(item.get("judgment"), dict) else None
        try:
            parsed = AtomicCriterionOutput.model_validate(item)
        except ValidationError as error:
            reviews.append(CriterionReview(criterion_id=cid, state="schema_invalid", decision_origin=origin,
                                           original_judgment=original_judgment,
                                           issues=[e["msg"] for e in error.errors(include_input=False, include_context=False)]))
            continue
        ids = [a.question_id for a in parsed.atomic_checks]
        local = []
        if len(set(ids)) != len(ids) or set(ids) != {q.question_id for q in criterion.questions}:
            local.append("Every configured atomic question must occur exactly once")
        observations = {a.question_id: a for a in parsed.atomic_checks}
        for a in parsed.atomic_checks:
            if not a.rationale.strip():
                local.append("Atomic fact rationale cannot be whitespace")
            local.extend(_reference_issues(a.evidence, messages))
            question = next((q for q in criterion.questions if q.question_id == a.question_id), None)
            policy = question.fact_policy if question else None
            if policy and a.answer == "yes" and policy.yes_roles:
                eligible = [e for e in a.evidence if e.kind == "quote" and e.message_id in messages
                            and messages[e.message_id].role in policy.yes_roles]
                if not eligible:
                    local.append("Positive atomic fact requires a quote from an eligible source role")
                if policy.yes_locator == "first_agent":
                    first = next((m.message_id for m in conversation.messages if m.role == "agent"), None)
                    if not any(e.message_id == first for e in eligible):
                        local.append("Positive atomic fact must cite the first human operator reply")
            if policy and a.answer in policy.full_scope_answers and not coverage_proof(
                    conversation, cid, [e.model_dump() for e in a.evidence], ["atomic_checks"]).complete:
                local.append("Atomic absence/context claim requires full-dialogue source coverage")
        if set(observations) == {q.question_id for q in criterion.questions}:
            local.extend(_identification_issues(criterion, observations, conversation, messages))
        notes = []
        if review_gate:
            notes = [m for m in local if m in REVIEWABLE_EVIDENCE_POLICY]
            local = [m for m in local if m not in REVIEWABLE_EVIDENCE_POLICY]
        if local:
            reviews.append(CriterionReview(criterion_id=cid, state="invalid_facts", decision_origin=origin,
                                           original_judgment=original_judgment, issues=local))
            continue
        applicability = criterion.applicability_rule
        if any(a.answer == "unknown" for a in parsed.atomic_checks) or (
                applicability and observations[applicability.question_id].answer not in ("yes", "no")):
            reviews.append(CriterionReview(criterion_id=cid, state="needs_review", decision_origin=origin,
                                           original_judgment=original_judgment, issues=["Unresolved atomic facts prevent an official decision"]))
            continue
        na = applicability and observations[applicability.question_id].answer == applicability.na_when
        if (criterion.output_source == "atomic" or na) and parsed.judgment is not None:
            reviews.append(CriterionReview(criterion_id=cid, state="conflict", decision_origin="derived",
                                           original_judgment=original_judgment,
                                           issues=["A model judgment was supplied for a backend-derived decision; no override performed"]))
            continue
        atomics = [AtomicCheck.model_validate(a.model_dump(exclude={"events"})) for a in parsed.atomic_checks]
        categories, response = [], None
        if na:
            response, origin = "N/A", "derived"
            evidence = list(observations[applicability.question_id].evidence)
            rationale = "Derived N/A from the configured applicability fact: " + observations[applicability.question_id].rationale
        elif criterion.output_source == "atomic":
            if criterion.kind == "critical":
                if any(a.answer not in ("yes", "no") for a in parsed.atomic_checks):
                    local.append("Critical category facts must be yes/no, never not_applicable")
                categories = [q.violation_category for q in criterion.questions if observations[q.question_id].answer == "yes"]
                response = "yes" if categories else "no"
            else:
                assessment = assess_decision(criterion, {"atomic_checks": [a.model_dump() for a in atomics]})
                response = assessment.derived_response if assessment else None
                local.extend(assessment.issues if assessment else [])
            evidence = [e for a in parsed.atomic_checks for e in a.evidence]
            rationale = "Backend-derived from configured rule over validated atomic observations: " + "; ".join(
                a.question_id + "=" + a.answer for a in parsed.atomic_checks)
        else:
            if parsed.judgment is None:
                local.append("Applicable discretionary criterion requires its original model judgment")
                evidence, rationale = [], "Missing model judgment"
            else:
                judgment = parsed.judgment
                response, evidence, rationale, categories = judgment.response, judgment.evidence, judgment.rationale, judgment.violation_categories
                if judgment.needs_review:
                    reviews.append(CriterionReview(criterion_id=cid, state="needs_review", decision_origin=origin,
                                                   original_judgment=original_judgment, response=response,
                                                   issues=[judgment.review_reason or "Model requested semantic review"]))
                    continue
                if judgment.review_reason is not None:
                    local.append("Unflagged judgment requires null review_reason")
                if review_gate and criterion.kind != "critical" and categories:
                    notes.append("Critical categories belong only to critical criteria")
                    categories = []
        if local or response is None:
            reviews.append(CriterionReview(criterion_id=cid, state="invalid_facts", decision_origin=origin,
                                           original_judgment=original_judgment, issues=local or ["Configured rule cannot derive a decision"]))
            continue
        def build(review_notes):
            reason = ("Evidence-policy exception (opt-in review gate): " + "; ".join(dict.fromkeys(review_notes))
                      if review_notes else None)
            return Decision(criterion_id=cid, atomic_checks=atomics, response=response, rationale=rationale,
                            na_reason=criterion.na_condition if response == "N/A" else None, evidence=evidence,
                            violation_categories=categories, needs_review=bool(review_notes), review_reason=reason)
        try:
            decision = build(notes)
            try:
                _validate_decision(decision, criterion, conversation, messages)
            except ValueError as error:
                found = [i["message"] for i in error.issues] if hasattr(error, "issues") else None
                if not (review_gate and found and all(m in REVIEWABLE_EVIDENCE_POLICY for m in found)):
                    raise
                notes.extend(found)
                decision = build(notes)
        except ValueError as error:
            reviews.append(CriterionReview(criterion_id=cid, state="invalid_facts", decision_origin=origin,
                                           original_judgment=original_judgment, response=response,
                                           issues=[i["message"] for i in error.issues] if hasattr(error, "issues") else ["Decision/evidence failed validation"]))
            continue
        exceptions.extend({"criterion_id": cid, "message": m} for m in dict.fromkeys(notes))
        accepted.append(decision)
        reviews.append(CriterionReview(criterion_id=cid, state="accepted_derived" if origin == "derived" else "accepted_model",
                                       decision_origin=origin, original_judgment=original_judgment, response=response,
                                       rule_source=(criterion.na_condition if na else criterion.decision_rule.source
                                                    if origin == "derived" and criterion.decision_rule else
                                                    "Configured critical category mapping" if origin == "derived" else "Official discretionary scale"),
                                       atomic_answers={a.question_id: a.answer for a in parsed.atomic_checks}))
    # Retain valid raw answer fields even when evidence/schema validation failed.
    # This is diagnostic context only; it is never passed to the scorer.
    for i, review in enumerate(reviews):
        entries = by_id.get(review.criterion_id, [])
        raw_checks = entries[0].get("atomic_checks", []) if len(entries) == 1 else []
        raw_checks = raw_checks if isinstance(raw_checks, list) else []
        answers = {a["question_id"]: a["answer"] for a in raw_checks if isinstance(a, dict)
                   and isinstance(a.get("question_id"), str) and a.get("answer") in ("yes", "no", "unknown", "not_applicable")}
        reviews[i] = review.model_copy(update={"atomic_answers": answers})
    issues.extend({"criterion_id": r.criterion_id, "message": message} for r in reviews for message in r.issues)
    if issues or any(not r.state.startswith("accepted_") for r in reviews):
        raise AtomicReviewRequired(reviews, issues, accepted)
    return ModelEvaluation(schema_version="1.1", decisions=accepted), reviews
