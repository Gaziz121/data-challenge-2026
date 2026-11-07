"""Configurable conditional binary checks. Never replace a model response."""

from .schemas import DecisionRuleAssessment


def assess_decision(criterion, values):
    rule = criterion.decision_rule
    if rule is None:
        return None  # No inferred rule for an arbitrary new criterion.
    atomics = values.get("atomic_checks")
    atomics = atomics if isinstance(atomics, list) else []
    ids = [a.get("question_id") for a in atomics if isinstance(a, dict)]
    answers = {a["question_id"]: a.get("answer") for a in atomics
               if isinstance(a, dict) and isinstance(a.get("question_id"), str)}
    response = values.get("response")
    response = response if type(response) is int or type(response) is str and response in ("yes", "no", "N/A") else None
    derived, issues = None, []
    unique = all(isinstance(q, str) for q in ids) and len(set(q for q in ids if isinstance(q, str))) == len(ids)
    applicable = True
    if criterion.applicability_rule:
        applicability = criterion.applicability_rule
        answer = answers.get(applicability.question_id)
        if answer == applicability.na_when:
            derived, applicable = "N/A", False
        elif answer not in ("yes", "no"):
            applicable = False  # Unknown applicability never means applicable.
    if unique and applicable:
        required = [answers.get(q) for q in rule.all_of]
        conditional = True
        if rule.conditional:
            c = rule.conditional
            trigger, requirement = answers.get(c.trigger_question_id), answers.get(c.requirement_question_id)
            if trigger not in ("yes", "no"):
                conditional = None
            elif trigger == c.required_when:
                conditional = requirement == "yes" if requirement in ("yes", "no") else None
                if requirement == "not_applicable":
                    issues.append("Triggered conditional obligation cannot be not_applicable")
            else:
                conditional = True
                if requirement != "not_applicable":
                    issues.append("Untriggered conditional obligation must be not_applicable")
        if all(a in ("yes", "no") for a in required) and conditional is not None and not issues:
            derived = "yes" if all(a == "yes" for a in required) and conditional else "no"
    if not unique:
        derived = None
    status = "undetermined" if derived is None or response is None else ("agreed" if response == derived else "disagreed")
    return DecisionRuleAssessment(criterion_id=criterion.criterion_id, rule_source=rule.source,
                                  model_response=response, derived_response=derived, status=status, issues=issues)
