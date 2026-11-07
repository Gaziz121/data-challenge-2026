from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from itertools import product
import unittest

from cqa.io import load_checklist
from cqa.schemas import Checklist
from cqa.scoring import score_evaluation
from tests.helpers import conversation, evaluation_data, model, set_response


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.conv, self.checklist = conversation(), load_checklist()
        self.raw = evaluation_data(self.conv, self.checklist)

    def score(self, raw=None, checklist=None):
        return score_evaluation(model(raw or self.raw), self.conv, checklist or self.checklist)

    def test_full_and_zero_scores(self):
        self.assertEqual(self.score().total_score, "100.00")
        for c in self.checklist.criteria:
            set_response(self.raw, self.checklist, c.criterion_id, 0 if c.kind == "discrete" else "no")
        self.assertEqual(self.score().total_score, "0.00")

    def test_every_official_scale_and_applicability_combination(self):
        # Independent Decimal calculation over 2,592 combinations, including all
        # permitted N/A combinations. This verifies the denominator as well as levels.
        choices = [("yes", "no"), ("yes", "no", "N/A"), ("yes", "no", "N/A"),
                   (0, 5, 10, 15, 20, "N/A"), ("yes", "no"), (0, 4, 7, 10), ("yes", "no", "N/A")]
        count = 0
        for responses in product(*choices):
            earned, weight = Decimal(0), 0
            for c, response in zip(self.checklist.criteria[:7], responses):
                set_response(self.raw, self.checklist, c.criterion_id, response)
                if response == "N/A":
                    continue
                weight += c.weight
                ratio = Decimal(response) / Decimal(max(c.levels)) if c.kind == "discrete" else Decimal(int(response == "yes"))
                earned += Decimal(c.weight) * ratio
            score = self.score()
            expected = (100 * earned / Decimal(weight)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            self.assertEqual(score.total_score, format(expected, ".2f"))
            self.assertEqual(score.applicable_weight, weight)
            self.assertEqual(Fraction(score.total_exact_numerator, score.total_exact_denominator), Fraction(100 * earned) / weight)
            count += 1
        self.assertEqual(count, 2592)

    def test_na_redistributes_instead_of_zeroing(self):
        set_response(self.raw, self.checklist, "02", "N/A")
        set_response(self.raw, self.checklist, "03", "N/A")
        set_response(self.raw, self.checklist, "04", 10)
        score = self.score()
        self.assertEqual(score.total_score, "84.62")  # 55 / 65 * 100
        self.assertEqual(score.applicable_weight, 65)
        self.assertEqual(next(r for r in score.criteria if r.criterion_id == "03").effective_weight, "0.000000000000")

    def test_critical_flag_never_changes_quality_total(self):
        original = self.score().total_score
        for category in ("insult", "paid_service_bypassing_company", "confidential_disclosure"):
            with self.subTest(category=category):
                critical = set_response(self.raw, self.checklist, "08", "yes")
                critical["violation_categories"] = [category]
                definition = next(c for c in self.checklist.criteria if c.criterion_id == "08")
                for atomic, question in zip(critical["atomic_checks"], definition.questions):
                    atomic["answer"] = "yes" if question.violation_category == category else "no"
                critical["evidence"] = self.raw["decisions"][0]["evidence"]
                score = self.score()
                self.assertEqual(score.total_score, original)
                self.assertTrue(score.critical_violation)
                self.assertEqual(score.violation_categories, [category])

    def test_empty_weighted_applicability_returns_null(self):
        value = self.checklist.model_dump()
        value["criteria"] = [value["criteria"][1]]
        checklist = Checklist.model_validate(value)
        raw = evaluation_data(self.conv, checklist)
        set_response(raw, checklist, "02", "N/A")
        score = self.score(raw, checklist)
        self.assertIsNone(score.total_score)
        self.assertIsNone(score.total_exact_numerator)
        self.assertIsNone(score.total_exact_denominator)

    def test_new_criterion_and_half_up_tie(self):
        value = self.checklist.model_dump()
        a, b = value["criteria"][0], value["criteria"][4]
        a.update(criterion_id="new-a", weight=1)
        b.update(criterion_id="new-b", weight=31)
        value["criteria"] = [a, b]
        value["version"] = "test-custom"
        checklist = Checklist.model_validate(value)
        raw = evaluation_data(self.conv, checklist)
        set_response(raw, checklist, "new-b", "no")
        score = self.score(raw, checklist)
        self.assertEqual(score.total_score, "3.13")  # exact 3.125, local HALF_UP convention

    def test_criterion_06_seven_is_ten_point_five_weighted_points(self):
        set_response(self.raw, self.checklist, "06", 7)
        self.assertEqual(self.score().total_score, "95.50")


if __name__ == "__main__":
    unittest.main()
