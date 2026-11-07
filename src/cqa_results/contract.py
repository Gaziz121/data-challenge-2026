"""Official results-submission contract (organizer appendix "Как сдать результаты", JSON 1.0).

Source: CQA_Student_Guide_Appendix_Results.pdf, pages 1-3 (criterion table, value
domains, weights, N/A redistribution, critical_flag, error records). This module
is stdlib-only so the validator stays independent of the evaluation engine.
"""

from decimal import Decimal
from fractions import Fraction

SCHEMA_VERSION = "1.0"
MODEL_MODES = ("local", "external_api", "hybrid")
SET_COUNTS = {"dev": 65, "prod": 10}  # Appendix p.1: DEV = 60 chats + 5 calls; PROD = 10 controls.
PLACEHOLDERS = {"", "Название команды", "Название модели", "<actual team name>",
                "<actual model or models used>", "TEAM", "MODEL"}

# (official_id, internal engine criterion_id, kind, weight, discrete levels, N/A allowed)
CRITERIA = (
    ("contact", "01", "binary", 10, None, False),
    ("discovery", "02", "binary", 15, None, True),
    ("identification", "03", "binary", 20, None, True),
    ("consultation", "04", "discrete", 20, (0, 5, 10, 15, 20), True),
    ("empathy", "05", "binary", 15, None, False),
    ("dialogue", "06", "discrete", 15, (0, 4, 7, 10), False),
    ("closure", "07", "binary", 5, None, True),
    ("critical", "08", "critical", 0, None, False),
)
OFFICIAL_IDS = tuple(c[0] for c in CRITERIA)
INTERNAL_TO_OFFICIAL = {c[1]: c[0] for c in CRITERIA}
BY_OFFICIAL = {c[0]: c for c in CRITERIA}


def is_bool(value):
    return type(value) is bool


def is_int(value):
    return type(value) is int


def value_issue(official_id, value):
    """Return None when value is a correctly typed official value, else a reason."""
    _, _, kind, _, levels, nullable = BY_OFFICIAL[official_id]
    if value is None:
        return None if nullable else "null (N/A) is not allowed for this criterion"
    if kind == "discrete":
        if not is_int(value) or value not in levels:
            return "must be one of %s%s" % (list(levels), " or null" if nullable else "")
        return None
    if not is_bool(value):
        return "must be a JSON boolean%s" % (" or null" if nullable else "")
    return None


def exact_score(values):
    """Exact 0..100 total: N/A criteria are excluded and their weight redistributed
    proportionally over applicable weighted criteria; critical carries no weight."""
    weight, earned = 0, Fraction(0)
    for official_id, _, kind, base, levels, _ in CRITERIA:
        value = values[official_id]
        if kind == "critical" or value is None:
            continue
        weight += base
        ratio = Fraction(value, max(levels)) if kind == "discrete" else Fraction(int(value))
        earned += base * ratio
    if weight == 0:
        return None
    return Fraction(100) * earned / weight


def round_half_up_2dp(value):
    """Exact rational HALF_UP to two decimals, returned as a Decimal."""
    hundredths = value * 100
    rounded = (2 * hundredths.numerator + hundredths.denominator) // (2 * hundredths.denominator)
    return Decimal(rounded).scaleb(-2)
