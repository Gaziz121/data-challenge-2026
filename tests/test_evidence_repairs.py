"""Formatting recovery is explicit, source-exact and never changes AI scores."""

from copy import deepcopy
import unittest

from cqa.engine import EvaluationRejected, evaluate
from cqa.evidence import normalize_evidence
from cqa.io import load_checklist
from cqa.providers import MockProvider, ProviderReply
from cqa.schemas import EvaluationConfig
from cqa.validation import validate_evaluation
from tests.helpers import conversation, evaluation_data, model


class ReplyFixture(MockProvider):
    def __init__(self, raw):
        self.raw = deepcopy(raw)

    def evaluate(self, *args):
        return ProviderReply(self.raw, model=self.model, response_id="offline-only", usage={"total_tokens": 12})


class EvidenceRepairTests(unittest.TestCase):
    def setUp(self):
        self.conv = conversation().model_copy(deep=True)
        self.conv.messages[3] = self.conv.messages[3].model_copy(update={
            "text": 'Hello, I am Sam. Your plan is «Standard».\n\tCafe\u0301 guide. Goodbye.'})
        self.checklist = load_checklist()
        self.raw = evaluation_data(self.conv, self.checklist)

    def set_quote(self, quote):
        self.raw["decisions"][3]["evidence"][0]["quote"] = quote

    def test_strict_policy_still_rejects_normalized_quotes(self):
        self.set_quote('Your plan is "Standard"')
        with self.assertRaises(ValueError):
            validate_evaluation(model(self.raw), self.conv, self.checklist)

    def test_explicit_repair_keeps_original_reply_and_exact_source_span(self):
        self.set_quote('Your plan is "Standard"')
        result = evaluate(self.conv, self.checklist, ReplyFixture(self.raw),
                          EvaluationConfig(quote_policy="normalize_formatting"))
        self.assertEqual(result.model_evaluation.decisions[3].evidence[0].quote, 'Your plan is "Standard"')
        self.assertEqual(result.validated_evaluation.decisions[3].evidence[0].quote, 'Your plan is «Standard»')
        repair = result.evidence_repairs[0]
        self.assertEqual(self.conv.messages[3].text[repair.source_start:repair.source_end], repair.source_quote)
        self.assertEqual(result.score.total_score, "100.00")
        self.assertEqual([d.response for d in result.model_evaluation.decisions],
                         [d.response for d in result.validated_evaluation.decisions])

    def test_whitespace_and_canonical_unicode_preserve_verbatim_source(self):
        self.set_quote('«Standard». Café guide')
        resolved, repairs = normalize_evidence(model(self.raw), self.conv)
        validate_evaluation(resolved, self.conv, self.checklist)
        self.assertEqual(repairs[0].source_quote, '«Standard».\n\tCafe\u0301 guide')

    def test_letter_changes_and_wrong_message_are_not_repaired(self):
        for quote in ('Your plan is "Standart"', 'your plan is "Standard"'):
            self.set_quote(quote)
            with self.assertRaises(EvaluationRejected):
                evaluate(self.conv, self.checklist, ReplyFixture(self.raw), EvaluationConfig(quote_policy="normalize_formatting"))
        self.set_quote('Your plan is "Standard"')
        self.raw["decisions"][3]["evidence"][0]["message_id"] = "m0000"
        resolved, repairs = normalize_evidence(model(self.raw), self.conv)
        self.assertFalse(repairs)
        with self.assertRaises(ValueError):
            validate_evaluation(resolved, self.conv, self.checklist)

    def test_ambiguous_normalized_match_is_not_guessed(self):
        self.conv.messages[3] = self.conv.messages[3].model_copy(update={"text": '«Standard» and «Standard»'})
        self.raw = evaluation_data(self.conv, self.checklist)
        self.set_quote('"Standard"')
        resolved, repairs = normalize_evidence(model(self.raw), self.conv)
        self.assertFalse(repairs)
        with self.assertRaises(ValueError):
            validate_evaluation(resolved, self.conv, self.checklist)

    def test_atomic_citation_repairs_are_traceable(self):
        self.raw["decisions"][3]["atomic_checks"][0]["evidence"] = [deepcopy(self.raw["decisions"][3]["evidence"][0])]
        self.raw["decisions"][3]["atomic_checks"][0]["evidence"][0]["quote"] = '"Standard"'
        resolved, repairs = normalize_evidence(model(self.raw), self.conv)
        self.assertEqual(repairs[0].evidence_path, "atomic_checks.0.evidence.0")
        validate_evaluation(resolved, self.conv, self.checklist)

    def test_multiple_invalid_criteria_keep_reply_usage_and_individual_diagnostics(self):
        self.raw["decisions"][0]["evidence"][0]["quote"] = "Not said here"
        self.raw["decisions"][4]["evidence"][0]["quote"] = "Also not said"
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, ReplyFixture(self.raw))
        diagnostic = caught.exception.diagnostic
        self.assertEqual({i["criterion_id"] for i in diagnostic["issues"]}, {"01", "05"})
        self.assertEqual(diagnostic["original_model_output"], self.raw)
        self.assertEqual(diagnostic["run"]["usage"]["total_tokens"], 12)
        self.assertNotIn("score", diagnostic)

    def test_schema_error_does_not_hide_another_criterion_applicability_error(self):
        self.raw["decisions"][1]["na_reason"] = "Invalid reason on an applicable response"
        self.raw["decisions"][6].update(response="N/A", na_reason="Invalid interruption assertion")
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, ReplyFixture(self.raw))
        self.assertEqual({i["criterion_id"] for i in caught.exception.diagnostic["issues"]}, {"02", "07"})
        self.assertEqual(len(caught.exception.diagnostic["criterion_validation"]), 8)


if __name__ == "__main__":
    unittest.main()
