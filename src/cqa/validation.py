"""Contextual gates, separate from structural schema validation and from inference."""

from .schemas import ModelEvaluation


class EvaluationValidationError(ValueError):
    """Per-criterion diagnostics without coercing any invalid decision into a score."""
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(issue["message"] for issue in issues))


def validate_evaluation(evaluation, conversation, checklist):
    # Revalidate even typed inputs: callers may have used model_copy/model_construct.
    evaluation = ModelEvaluation.model_validate(evaluation.model_dump())
    expected = {c.criterion_id: c for c in checklist.criteria}
    ids = [d.criterion_id for d in evaluation.decisions]
    if len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise ValueError("Model must return every checklist criterion exactly once")
    messages = {m.message_id: m for m in conversation.messages}
    issues = []
    for decision in evaluation.decisions:
        criterion = expected[decision.criterion_id]
        try:
            _validate_decision(decision, criterion, conversation, messages)
        except ValueError as error:
            issues.append({"criterion_id": decision.criterion_id, "message": str(error)})
    if issues:
        raise EvaluationValidationError(issues)
    return evaluation


def _validate_decision(decision, criterion, conversation, messages):
    question_ids = [a.question_id for a in decision.atomic_checks]
    if (len(set(question_ids)) != len(question_ids)
            or set(question_ids) != {q.question_id for q in criterion.questions}):
        raise ValueError("Every configured atomic question must be answered exactly once")
    if any(a.answer == "unknown" for a in decision.atomic_checks) and not decision.needs_review:
        raise ValueError("Unknown atomic answers require explicit review")
    response = decision.response
    answers = {a.question_id: a.answer for a in decision.atomic_checks}
    for rule in criterion.consistency_rules:
        if answers[rule.question_id] == rule.when_answer and response not in rule.permitted_responses:
            raise ValueError("Official response contradicts a configured atomic consistency rule")
    if criterion.applicability_rule:
        rule = criterion.applicability_rule
        applicability_answer = next(a.answer for a in decision.atomic_checks if a.question_id == rule.question_id)
        if response == "N/A" and applicability_answer != rule.na_when:
            raise ValueError("N/A conflicts with its configured applicability check")
        if applicability_answer == rule.na_when and response != "N/A":
            raise ValueError("Applicable response conflicts with an asserted N/A condition")
    if response == "N/A":
        if criterion.na_condition is None:
            raise ValueError("N/A forbidden for this criterion")
    elif criterion.kind == "discrete":
        if type(response) is not int or response not in criterion.levels:
            raise ValueError("Response is not a permitted discrete score")
    elif type(response) is not str or response not in ("yes", "no"):
        raise ValueError("Binary/critical response must be yes or no")
    if criterion.kind == "critical":
        mapped = {q.violation_category for q in criterion.questions if q.violation_category is not None}
        if mapped:
            asserted = {q.violation_category for q in criterion.questions
                        if q.violation_category is not None and answers[q.question_id] == "yes"}
            if set(decision.violation_categories) != asserted or (response == "yes") != bool(asserted):
                raise ValueError("Critical categories and flag contradict configured atomic category answers")
        if (response == "yes") != bool(decision.violation_categories):
            raise ValueError("Critical yes requires categories; no forbids categories")
        if response == "no" and not any(
                e.kind == "scope" and e.start_message_id == conversation.messages[0].message_id
                and e.end_message_id == conversation.messages[-1].message_id
                for e in decision.evidence):
            raise ValueError("No critical violation requires the full inspected scope")
        if response == "yes" and not any(
                e.kind == "quote" and e.message_id in messages
                and messages[e.message_id].role == "agent" for e in decision.evidence):
            raise ValueError("Critical violation requires a quoted agent utterance")
    elif decision.violation_categories:
        raise ValueError("Critical categories belong only to critical criteria")
    if criterion.kind != "critical" and (response == "yes" or type(response) is int and response > 0):
        policy = criterion.evidence_policy
        supporting = [e for e in decision.evidence if e.kind == "quote" and e.message_id in messages
                      and messages[e.message_id].role in policy.positive_roles]
        if not supporting:
            raise ValueError("Positive operator performance needs evidence from a configured allowed role")
        if policy.positive_locator == "first_agent":
            first = next((m.message_id for m in conversation.messages if m.role == "agent"), None)
            if not any(e.message_id == first for e in supporting):
                raise ValueError("Positive response requires evidence from the first human operator reply")
    for evidence in decision.evidence + [e for a in decision.atomic_checks for e in a.evidence]:
        if evidence.kind == "quote":
            message = messages.get(evidence.message_id)
            if message is None:
                raise ValueError("Unknown evidence message ID")
            if not any(character.isalnum() for character in evidence.quote):
                raise ValueError("Evidence quotation must contain a letter or digit, not punctuation only")
            if evidence.quote not in message.text:
                raise ValueError("Evidence quote is not an exact source substring")
        else:
            start, end = messages.get(evidence.start_message_id), messages.get(evidence.end_message_id)
            if start is None or end is None:
                raise ValueError("Unknown evidence scope boundary")
            if start.source_index > end.source_index:
                raise ValueError("Evidence scope boundaries are reversed")
