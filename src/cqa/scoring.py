"""Exact rational weighting; only the final total is rounded for scoring."""

from decimal import Decimal, localcontext
from fractions import Fraction

from .schemas import CriterionScore, OverallScore


def _display(value):
    # Display approximations only; never fed back into the exact calculation.
    with localcontext() as context:
        context.prec = 50
        return format(Decimal(value.numerator) / Decimal(value.denominator), ".12f")


def _round_total(value):
    # Exact rational HALF_UP, independent of decimal context or binary floats.
    hundredths = value * 100
    rounded = (2 * hundredths.numerator + hundredths.denominator) // (2 * hundredths.denominator)
    return f"{rounded // 100}.{rounded % 100:02d}"


def score_evaluation(evaluation, conversation, checklist):
    from .validation import validate_evaluation
    evaluation = validate_evaluation(evaluation, conversation, checklist)
    decisions = {d.criterion_id: d for d in evaluation.decisions}
    critical_ids = {c.criterion_id for c in checklist.criteria if c.kind == "critical"}
    categories = sorted({v for d in evaluation.decisions if d.criterion_id in critical_ids
                         for v in d.violation_categories})
    return score_responses({cid: d.response for cid, d in decisions.items()}, checklist, categories)


def score_responses(responses, checklist, violation_categories=()):
    """The official arithmetic over raw responses, shared by evaluation and appeal recalculation.

    `responses` maps every checklist criterion ID to its raw response (yes/no/N/A or a level).
    Validation of evidence is the caller's job; this function only refuses impossible values.
    """
    if set(responses) != {c.criterion_id for c in checklist.criteria}:
        raise ValueError("Scoring needs exactly one response per checklist criterion")
    for criterion in checklist.criteria:
        response = responses[criterion.criterion_id]
        permitted = (list(criterion.levels) if criterion.kind == "discrete" else ["yes", "no"]) + (
            ["N/A"] if criterion.na_condition is not None else [])
        if response not in permitted or isinstance(response, bool):
            raise ValueError("Response outside the configured scale for criterion %s" % criterion.criterion_id)
    weighted = [c for c in checklist.criteria if c.kind != "critical"]
    weight = sum(c.weight for c in weighted if responses[c.criterion_id] != "N/A")
    total = Fraction(0)
    rows = []
    for criterion in checklist.criteria:
        response = responses[criterion.criterion_id]
        applicable = response != "N/A"
        effective = Fraction(100 * criterion.weight, weight) if weight and applicable else Fraction(0)
        if criterion.kind == "critical" or not applicable:
            ratio = Fraction(0)
        elif criterion.kind == "discrete":
            ratio = Fraction(response, max(criterion.levels))
        else:
            ratio = Fraction(int(response == "yes"))
        points = effective * ratio
        total += points
        rows.append(CriterionScore(criterion_id=criterion.criterion_id, applicable=applicable,
                                   base_weight=criterion.weight, effective_weight=_display(effective),
                                   earned_points=_display(points)))
    critical = [c for c in checklist.criteria if c.kind == "critical"]
    return OverallScore(total_score=_round_total(total) if weight else None,
                        total_exact_numerator=total.numerator if weight else None,
                        total_exact_denominator=total.denominator if weight else None,
                        applicable_weight=weight,
                        critical_violation=any(responses[c.criterion_id] == "yes" for c in critical),
                        violation_categories=sorted(set(violation_categories)), criteria=rows,
                        rounding=checklist.rounding)
