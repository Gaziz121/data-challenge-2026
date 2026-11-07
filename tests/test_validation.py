from copy import deepcopy
import unittest

from pydantic import ValidationError

from cqa.io import load_checklist, parse_json
from cqa.schemas import Checklist
from cqa.validation import validate_evaluation
from tests.helpers import conversation, evaluation_data, model, set_response


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.conv, self.checklist = conversation(), load_checklist()
        self.raw = evaluation_data(self.conv, self.checklist)

    def validate(self):
        return validate_evaluation(model(self.raw), self.conv, self.checklist)

    def test_valid_output(self):
        self.assertEqual(len(self.validate().decisions), 8)

    def test_invalid_discrete_binary_and_na_values(self):
        original = deepcopy(self.raw)
        for criterion_id, responses in {"01": [True, False, 1, 0, "Да", "YES", "N/A"],
                                         "04": [-1, 1, 7, 17.5, 21, "10", True],
                                         "06": [-1, 1, 5, 6, 8, 11, "7", "N/A"]}.items():
            for response in responses:
                with self.subTest(criterion=criterion_id, response=response):
                    self.raw = deepcopy(original)
                    set_response(self.raw, self.checklist, criterion_id, response)
                    with self.assertRaises((ValueError, ValidationError)):
                        self.validate()

    def test_missing_duplicate_extra_criteria(self):
        original = deepcopy(self.raw)
        for mode in ("missing", "duplicate", "extra"):
            self.raw = deepcopy(original)
            if mode == "missing":
                self.raw["decisions"].pop()
            else:
                extra = deepcopy(self.raw["decisions"][0])
                if mode == "extra":
                    extra["criterion_id"] = "unknown"
                self.raw["decisions"].append(extra)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.validate()

    def test_all_required_decision_fields(self):
        original = deepcopy(self.raw)
        for field in list(original["decisions"][0]):
            self.raw = deepcopy(original)
            self.raw["decisions"][0].pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.validate()

    def test_llm_cannot_return_weighted_score(self):
        self.raw["total_score"] = 100
        with self.assertRaises(ValidationError):
            self.validate()

    def test_unknown_quote_id(self):
        self.raw["decisions"][0]["evidence"][0]["message_id"] = "invented"
        with self.assertRaises(ValueError):
            self.validate()

    def test_fabricated_quote(self):
        self.raw["decisions"][0]["evidence"][0]["quote"] = "This was never said"
        with self.assertRaises(ValueError):
            self.validate()

    def test_atomic_evidence_is_also_validated(self):
        self.raw["decisions"][0]["atomic_checks"][0]["evidence"][0]["end_message_id"] = "invented"
        with self.assertRaises(ValueError):
            self.validate()

    def test_scope_order_and_unknown_boundaries(self):
        scope = self.raw["decisions"][-1]["evidence"][0]
        for start, end in [("invented", "m0003"), ("m0003", "m0000")]:
            scope.update(start_message_id=start, end_message_id=end)
            with self.subTest(start=start), self.assertRaises(ValueError):
                self.validate()

    def test_bot_cannot_substitute_for_operator_evidence(self):
        bot = self.conv.messages[1]
        self.raw["decisions"][0]["evidence"][0].update(message_id=bot.message_id, quote=bot.text)
        with self.assertRaises(ValueError):
            self.validate()

    def test_omission_scope_has_no_invented_quote(self):
        decision = self.raw["decisions"][0]
        decision.update(response="no", evidence=[deepcopy(self.raw["decisions"][-1]["evidence"][0])])
        decision["evidence"][0]["kind"] = "omission"
        self.validate()
        decision["evidence"][0]["quote"] = "missing greeting"
        with self.assertRaises(ValueError):
            self.validate()

    def test_empty_rationale_evidence_and_na_reason(self):
        original = deepcopy(self.raw)
        for field, value in [("rationale", " "), ("evidence", []), ("review_reason", "unexpected")]:
            self.raw = deepcopy(original)
            self.raw["decisions"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate()
        self.raw = deepcopy(original)
        decision = set_response(self.raw, self.checklist, "02", "N/A")
        decision["na_reason"] = " "
        with self.assertRaises(ValueError):
            self.validate()

    def test_applicability_contradictions_are_rejected(self):
        for criterion_id in ("02", "03", "04", "07"):
            with self.subTest(criterion_id=criterion_id):
                self.raw = evaluation_data(self.conv, self.checklist)
                decision = set_response(self.raw, self.checklist, criterion_id, "N/A")
                rule = next(c.applicability_rule for c in self.checklist.criteria if c.criterion_id == criterion_id)
                atomic = next(a for a in decision["atomic_checks"] if a["question_id"] == rule.question_id)
                atomic["answer"] = "no" if rule.na_when == "yes" else "yes"
                with self.assertRaises(ValueError):
                    self.validate()
                atomic["answer"] = rule.na_when
                decision.update(response="yes" if criterion_id != "04" else 20, na_reason=None)
                with self.assertRaises(ValueError):
                    self.validate()

    def test_unknown_atomic_answer_requires_review(self):
        self.raw["decisions"][0]["atomic_checks"][0]["answer"] = "unknown"
        with self.assertRaises(ValueError):
            self.validate()
        self.raw["decisions"][0].update(needs_review=True, review_reason="Unknown fact")
        self.validate()

    def test_configured_consistency_rule_rejects_contradiction(self):
        self.raw["decisions"][0]["atomic_checks"][0]["answer"] = "no"
        with self.assertRaisesRegex(ValueError, "consistency"):
            self.validate()

    def test_missing_duplicate_and_unknown_atomic_questions(self):
        original = deepcopy(self.raw)
        for mode in ("missing", "duplicate", "unknown"):
            self.raw = deepcopy(original)
            answers = self.raw["decisions"][0]["atomic_checks"]
            if mode == "missing":
                answers.pop()
            elif mode == "duplicate":
                answers.append(deepcopy(answers[0]))
            else:
                answers[0]["question_id"] = "invented"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.validate()

    def test_critical_categories_and_full_scope_rules(self):
        original = deepcopy(self.raw)
        for mode in ("yes-without-category", "no-with-category", "partial-scope", "noncritical-category", "yes-without-agent-quote"):
            self.raw = deepcopy(original)
            critical = self.raw["decisions"][-1]
            if mode == "yes-without-category":
                critical["response"] = "yes"
            elif mode == "no-with-category":
                critical["violation_categories"] = ["insult"]
            elif mode == "partial-scope":
                critical["evidence"][0]["start_message_id"] = "m0001"
            elif mode == "noncritical-category":
                self.raw["decisions"][0]["violation_categories"] = ["insult"]
            else:
                critical.update(response="yes", violation_categories=["insult"])
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.validate()

    def test_bad_checklist_definitions(self):
        original = self.checklist.model_dump()
        for mode in ("duplicate", "missing-anchor", "critical-weight", "missing-rule", "wrong-rule-question"):
            value = deepcopy(original)
            if mode == "duplicate":
                value["criteria"].append(deepcopy(value["criteria"][0]))
            elif mode == "missing-anchor":
                value["criteria"][3]["anchors"].pop("5")
            elif mode == "critical-weight":
                value["criteria"][-1]["weight"] = 5
            elif mode == "missing-rule":
                value["criteria"][1]["applicability_rule"] = None
            else:
                value["criteria"][1]["applicability_rule"]["question_id"] = "bad"
            with self.subTest(mode=mode), self.assertRaises(ValidationError):
                Checklist.model_validate(value)

    def test_nonstandard_and_duplicate_json_rejected(self):
        for value in ('{"x": 1, "x": 2}', '{"x": NaN}', '{"x": Infinity}', 'broken'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_json(value)
