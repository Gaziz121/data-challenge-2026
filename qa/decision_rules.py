"""QA reference checker: deterministic decision rules over atomic answers.

An independent Checker, not part of the engine. It never changes a decision; it
only reports where a model's official response disagrees with what its OWN
atomic answers imply. Proposed for adoption as configuration (RCA a94e48f7, fix 4).

Rules:
* Applicability (generic): any criterion with an `applicability_rule` is N/A
  exactly when its applicability question equals `na_when`. Works for new
  criteria with no code change.
* Binary all-of rules (explicit, per criterion): response is yes iff every
  listed question is yes. Only for criteria whose official text is a conjunction.
  Criteria without a rule return None (no derivation), so new criteria keep the
  model's response.
"""

ALL_OF_RULES = {
    "01": ("01.q1", "01.q2"),  # greeting in client language AND self-introduction
    "07": ("07.q2", "07.q3"),  # (summary OR further help) AND farewell; q2 already holds the OR
}


def derive_response(criterion, answers, all_of_rules=ALL_OF_RULES):
    """Return 'N/A', 'yes', 'no', or None when no rule determines the response."""
    rule = criterion.applicability_rule
    if rule is not None and answers.get(rule.question_id) == rule.na_when:
        return "N/A"
    questions = all_of_rules.get(criterion.criterion_id)
    if criterion.kind == "binary" and questions:
        if any(answers.get(q) in (None, "unknown") for q in questions):
            return None
        return "yes" if all(answers[q] == "yes" for q in questions) else "no"
    if rule is not None and criterion.kind != "binary":
        return "applicable"  # level still comes from the model, constrained by consistency rules
    return None


def disagreements(raw, checklist, all_of_rules=ALL_OF_RULES):
    """List decisions whose response contradicts the rule-derived response."""
    criteria = {c.criterion_id: c for c in checklist.criteria}
    found = []
    for decision in raw["decisions"]:
        criterion = criteria.get(decision.get("criterion_id"))
        if criterion is None:
            continue
        answers = {a["question_id"]: a["answer"] for a in decision.get("atomic_checks", [])}
        derived = derive_response(criterion, answers, all_of_rules)
        response = decision.get("response")
        if derived is None:
            continue
        mismatch = (response == "N/A") if derived == "applicable" else (response != derived)
        if mismatch:
            found.append({"criterion_id": criterion.criterion_id, "model_response": response,
                          "derived": derived})
    return found
