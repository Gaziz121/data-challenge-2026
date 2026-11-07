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
    weighted = [c for c in checklist.criteria if c.kind != "critical"]
    weight = sum(c.weight for c in weighted if decisions[c.criterion_id].response != "N/A")
    total = Fraction(0)
    rows = []
    for criterion in checklist.criteria:
        response = decisions[criterion.criterion_id].response
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
    critical = [d for d in evaluation.decisions
                if next(c for c in checklist.criteria if c.criterion_id == d.criterion_id).kind == "critical"]
    categories = sorted({v for d in critical for v in d.violation_categories})
    return OverallScore(total_score=_round_total(total) if weight else None,
                        total_exact_numerator=total.numerator if weight else None,
                        total_exact_denominator=total.denominator if weight else None,
                        applicable_weight=weight, critical_violation=any(d.response == "yes" for d in critical),
                        violation_categories=categories, criteria=rows, rounding=checklist.rounding)
