"""Contextual gates, separate from structural schema validation and from inference."""

from pydantic import TypeAdapter, ValidationError

from .schemas import Decision, Evidence, ModelEvaluation, decision_metadata_issues

_FIELD_ADAPTERS = {name: TypeAdapter(field.rebuild_annotation()) for name, field in Decision.model_fields.items()}
_EVIDENCE_ADAPTER = TypeAdapter(Evidence)


class EvaluationValidationError(ValueError):
    """Per-criterion diagnostics without coercing any invalid decision into a score."""
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(issue["message"] for issue in issues))


def diagnose_decision(raw, criterion, conversation, messages):
    """Parse independent fields for diagnostics, without constructing an accepted Decision.

    An invalid metadata/evidence field must not hide an applicability contradiction
    in other valid fields. Partial projections are never passed to the scorer.
    """
    issues, values = [], {}

    def add(message, location=()):
        issues.append({"criterion_id": criterion.criterion_id, "location": list(location), "message": message})

    for name, adapter in _FIELD_ADAPTERS.items():
        if name not in raw:
            add("Field required", (name,))
            continue
        try:
            parsed = adapter.validate_python(raw[name], strict=True)
            values[name] = adapter.dump_python(parsed, mode="python")
        except ValidationError as error:
            for e in error.errors(include_input=False, include_context=False):
                add(e["msg"], (name,) + e["loc"])
    for name in raw.keys() - _FIELD_ADAPTERS.keys():
        add("Extra inputs are not permitted", (name,))

    def valid_references(raw_refs):
        references = []
        for reference in raw_refs if isinstance(raw_refs, list) else []:
            try:
                references.append(_EVIDENCE_ADAPTER.validate_python(reference, strict=True).model_dump())
            except ValidationError:
                pass  # The field-level error is already recorded; inspect valid siblings.
        return references

    if "evidence" not in values and isinstance(raw.get("evidence"), list):
        values["evidence"] = valid_references(raw["evidence"])
    if "atomic_checks" not in values and isinstance(raw.get("atomic_checks"), list):
        values["atomic_checks"] = [
            {"question_id": a["question_id"],
             "answer": a.get("answer") if a.get("answer") in ("yes", "no", "unknown", "not_applicable") else None,
             "evidence": valid_references(a.get("evidence"))}
            for a in raw["atomic_checks"] if isinstance(a, dict) and isinstance(a.get("question_id"), str)]
    for message in decision_metadata_issues(values):
        add(message)
    issues.extend(contextual_issues(values, criterion, conversation, messages))
    return issues


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
            issues.extend(error.issues if isinstance(error, EvaluationValidationError) else
                          [{"criterion_id": decision.criterion_id, "message": str(error)}])
    if issues:
        raise EvaluationValidationError(issues)
    return evaluation


def _validate_decision(decision, criterion, conversation, messages):
    issues = contextual_issues(decision.model_dump(), criterion, conversation, messages)
    if issues:
        raise EvaluationValidationError(issues)


def contextual_issues(values, criterion, conversation, messages):
    """Collect independent violations over typed fields; never derive a response.

    Diagnostic callers may provide only successfully parsed fields. Acceptance
    always supplies a fully validated Decision and rejects any reported issue.
    """
    issues = []

    def add(message, location=()):
        issues.append({"criterion_id": criterion.criterion_id, "location": list(location), "message": message})

    atomics = values.get("atomic_checks")
    answers = {}
    if atomics is not None:
        ids = [a.get("question_id") for a in atomics]
        if len(set(ids)) != len(ids) or set(ids) != {q.question_id for q in criterion.questions}:
            add("Every configured atomic question must be answered exactly once", ("atomic_checks",))
        answers = {a.get("question_id"): a.get("answer") for a in atomics}
        if any(a.get("answer") == "unknown" for a in atomics) and values.get("needs_review") is False:
            add("Unknown atomic answers require explicit review", ("needs_review",))
    response = values.get("response")
    if "response" in values:
        for rule in criterion.consistency_rules:
            if answers.get(rule.question_id) == rule.when_answer and response not in rule.permitted_responses:
                add("Official response contradicts a configured atomic consistency rule", ("response",))
        if criterion.applicability_rule:
            rule = criterion.applicability_rule
            answer = answers.get(rule.question_id)
            if answer is not None:
                if response == "N/A" and answer != rule.na_when:
                    add("N/A conflicts with its configured applicability check", ("response",))
                if answer == rule.na_when and response != "N/A":
                    add("Applicable response conflicts with an asserted N/A condition", ("response",))
        if response == "N/A":
            if criterion.na_condition is None:
                add("N/A forbidden for this criterion", ("response",))
        elif criterion.kind == "discrete":
            if type(response) is not int or response not in criterion.levels:
                add("Response is not a permitted discrete score", ("response",))
        elif type(response) is not str or response not in ("yes", "no"):
            add("Binary/critical response must be yes or no", ("response",))
    evidence = values.get("evidence")
    categories = values.get("violation_categories")
    if criterion.kind == "critical":
        mapped = {q.violation_category for q in criterion.questions if q.violation_category is not None}
        if mapped and categories is not None and atomics is not None and "response" in values:
            asserted = {q.violation_category for q in criterion.questions
                        if q.violation_category is not None and answers.get(q.question_id) == "yes"}
            if set(categories) != asserted or (response == "yes") != bool(asserted):
                add("Critical categories and flag contradict configured atomic category answers", ("violation_categories",))
        if categories is not None and "response" in values and (response == "yes") != bool(categories):
            add("Critical yes requires categories; no forbids categories", ("violation_categories",))
        if evidence is not None:
            if response == "no" and not any(
                    e["kind"] == "scope" and e["start_message_id"] == conversation.messages[0].message_id
                    and e["end_message_id"] == conversation.messages[-1].message_id for e in evidence):
                add("No critical violation requires the full inspected scope", ("evidence",))
            if response == "yes" and not any(
                    e["kind"] == "quote" and e["message_id"] in messages
                    and messages[e["message_id"]].role == "agent" for e in evidence):
                add("Critical violation requires a quoted agent utterance", ("evidence",))
    elif categories:
        add("Critical categories belong only to critical criteria", ("violation_categories",))
    if evidence is not None and criterion.kind != "critical" and (response == "yes" or type(response) is int and response > 0):
        policy = criterion.evidence_policy
        supporting = [e for e in evidence if e["kind"] == "quote" and e["message_id"] in messages
                      and messages[e["message_id"]].role in policy.positive_roles]
        if not supporting:
            add("Positive operator performance needs evidence from a configured allowed role", ("evidence",))
        if policy.positive_locator == "first_agent":
            first = next((m.message_id for m in conversation.messages if m.role == "agent"), None)
            if not any(e["message_id"] == first for e in supporting):
                add("Positive response requires evidence from the first human operator reply", ("evidence",))
    references = [(e, ("evidence", i)) for i, e in enumerate(evidence or [])]
    references += [(e, ("atomic_checks", i, "evidence", j))
                   for i, a in enumerate(atomics or []) for j, e in enumerate(a.get("evidence", []))]
    for e, path in references:
        if e["kind"] == "quote":
            message = messages.get(e["message_id"])
            if message is None:
                add("Unknown evidence message ID", path + ("message_id",))
            if not any(c.isalnum() for c in e["quote"]):
                add("Evidence quotation must contain a letter or digit, not punctuation only", path + ("quote",))
            if message is not None and e["quote"] not in message.text:
                add("Evidence quote is not an exact source substring", path + ("quote",))
        else:
            start, end = messages.get(e["start_message_id"]), messages.get(e["end_message_id"])
            if start is None or end is None:
                add("Unknown evidence scope boundary", path)
            elif start.source_index > end.source_index:
                add("Evidence scope boundaries are reversed", path)
    return issues
