"""Deterministic adversarial tests of the engine's validation gates and loader.

Three groups, kept deliberately separate:

* DefectTests assert the behavior the official checklist requires. They FAIL
  on commit ebcab33; each failure is a recorded defect (QA-Dxx), not noise.
* GuardTests close coverage gaps not in the 53 existing tests and PASS today.
* CharacterizationTests PASS and pin current behavior that is a reliability or
  requirement risk needing an owner decision (QA-Cxx). If one starts failing,
  the behavior changed: update the report, do not silently edit the test.

No LLM is called. Nothing here measures semantic scoring accuracy.
"""

from copy import deepcopy
import random
import unittest

from pydantic import ValidationError

from cqa.engine import evaluate
from cqa.io import load_checklist
from cqa.loader import normalize_record, require_approved_synthetic
from cqa.preprocessing import extract_facts
from cqa.schemas import Checklist, Decision
from cqa.scoring import score_evaluation
from cqa.validation import validate_evaluation
from qa.fixtures import (GATES_EN, GATES_KZ, GATES_RU, LATE_INTRO_EN, ScriptedProvider, as_model,
                         decision, make_conversation, make_record, quote, scope, set_atomic, valid_raw)

CHECKLIST = load_checklist()


class Base:
    """Mixin, not itself collected as a test case."""
    turns = GATES_EN

    def setUp(self):
        self.conv = make_conversation(self.turns)
        self.raw = valid_raw(self.conv, CHECKLIST)
        self.m = self.conv.messages

    def validate(self, raw=None):
        return validate_evaluation(as_model(raw or self.raw), self.conv, CHECKLIST)

    def assertAccepted(self, raw=None):
        try:
            self.validate(raw)
        except ValueError as error:
            self.fail(f"Rejected a checklist-valid evaluation: {error}")


class DefectTests(Base, unittest.TestCase):
    """Expected official behavior. Failures here are defects on ebcab33."""

    def test_d01_greeting_credit_must_come_from_first_operator_reply(self):
        # Checklist C1: greeting AND introduction in the operator's FIRST reply.
        # First operator reply (index 3) has no greeting; index 4 greets.
        conv = make_conversation(LATE_INTRO_EN)
        raw = valid_raw(conv, CHECKLIST, evidence_index={"01": 4})
        with self.assertRaises(ValueError, msg="01=yes cited a later operator turn, not the first reply"):
            validate_evaluation(as_model(raw), conv, CHECKLIST)

    def test_d02a_identity_required_but_unconfirmed_cannot_be_yes(self):
        # C1/C3: verification required and not confirmed before the protected
        # action => No (explicitly not N/A, and certainly not Yes).
        set_atomic(self.raw, "03.q1", "yes")
        set_atomic(self.raw, "03.q2", "no")
        with self.assertRaises(ValueError):
            self.validate()

    def test_d02b_closing_without_farewell_cannot_be_yes(self):
        # C1 07 working reading (summary OR further help) AND farewell; C3 gives a
        # closure without farewell as an explicit No example.
        set_atomic(self.raw, "07.q3", "no")
        with self.assertRaises(ValueError):
            self.validate()

    def test_d02c_open_material_question_cannot_score_full_consultation(self):
        # C2 04 anchor 20 requires ALL material questions addressed or a correct
        # next step. An atomic "no" to exactly that question contradicts 20.
        set_atomic(self.raw, "04.q2", "no")
        with self.assertRaises(ValueError):
            self.validate()

    def test_d02d_incorrect_key_advice_must_be_zero(self):
        # C2 04 anchor 0: "key recommendation is incorrect".
        set_atomic(self.raw, "04.q3", "no")
        with self.assertRaises(ValueError):
            self.validate()

    def test_d02e_impolite_operator_cannot_pass_empathy(self):
        # C1 05: Yes requires the operator to be polite.
        set_atomic(self.raw, "05.q1", "no")
        with self.assertRaises(ValueError):
            self.validate()

    def test_d02f_client_forced_to_ask_again_cannot_score_ten(self):
        # C2 06: forcing the client to ask again is the anchor-4 description.
        set_atomic(self.raw, "06.q2", "yes")
        with self.assertRaises(ValueError):
            self.validate()

    def test_d02g_missing_clarification_cannot_pass_need_identification(self):
        # C1 02: information missing (q1=no) and not clarified (q2=no) => No.
        set_atomic(self.raw, "02.q2", "no")
        with self.assertRaises(ValueError):
            self.validate()

    def test_d03_system_verification_event_is_valid_evidence_for_identification(self):
        # G2/C3 allow citing "a specific utterance or system message". In DEV the
        # verification itself is a system event. Citing only that event must not
        # make the whole evaluation fail.
        verified = self.m[5]
        self.assertEqual(verified.role, "system")
        d = decision(self.raw, "03")
        d["evidence"] = [quote(verified, why="Identity verified before disclosure in index 6.")]
        for atomic in d["atomic_checks"]:
            atomic["evidence"] = [quote(verified)]
        self.assertAccepted()

    def test_d04a_critical_yes_requires_a_yes_atomic_category_answer(self):
        # 08=yes while all three category questions answer "no" is self-contradictory.
        d = decision(self.raw, "08")
        d.update(response="yes", violation_categories=["insult"], evidence=[quote(self.m[6])])
        with self.assertRaises(ValueError):
            self.validate()

    def test_d04b_critical_categories_must_match_atomic_answers(self):
        # 08.q1 (insult) = yes but the listed category is confidential_disclosure.
        d = decision(self.raw, "08")
        d.update(response="yes", violation_categories=["confidential_disclosure"], evidence=[quote(self.m[6])])
        set_atomic(self.raw, "08.q1", "yes")
        with self.assertRaises(ValueError):
            self.validate()

    def test_d05_punctuation_only_quote_is_not_evidence(self):
        # "!" is an exact substring of "...Goodbye!" but supports nothing.
        d = decision(self.raw, "05")
        d["evidence"] = [quote(self.m[8], text="!")]
        with self.assertRaises(ValueError):
            self.validate()


class GuardTests(Base, unittest.TestCase):
    """New coverage that passes today."""

    def test_real_quote_attributed_to_wrong_message_is_rejected(self):
        d = decision(self.raw, "04")
        d["evidence"] = [quote(self.m[3], text=self.m[6].text)]
        with self.assertRaises(ValueError):
            self.validate()

    def test_customer_quote_cannot_carry_positive_operator_score(self):
        d = decision(self.raw, "05")
        d["evidence"] = [quote(self.m[7])]
        with self.assertRaises(ValueError):
            self.validate()

    def test_ru_kz_end_to_end_roles_quotes_and_score(self):
        for turns, language in ((GATES_RU, "RU"), (GATES_KZ, "KZ")):
            with self.subTest(language=language):
                conv = make_conversation(turns, language=language)
                facts = extract_facts(conv, CHECKLIST)
                self.assertEqual(facts.role_counts, {"customer": 2, "agent": 2, "bot": 1, "system": 1})
                self.assertEqual(facts.first_agent_message_id, "m0003")
                result = evaluate(conv, CHECKLIST, ScriptedProvider(valid_raw(conv, CHECKLIST)))
                self.assertEqual(result.status, "structurally_valid")
                self.assertEqual(result.score.total_score, "100.00")
                self.assertEqual([m.text for m in result.conversation.messages], [t for _, t in turns])

    def test_single_altered_kazakh_letter_is_rejected(self):
        conv = make_conversation(GATES_KZ, language="KZ")
        raw = valid_raw(conv, CHECKLIST)
        operator = conv.messages[3]
        decision(raw, "01")["evidence"] = [quote(operator, text=operator.text.replace("Сәлеметсіз", "Салеметсіз"))]
        with self.assertRaises(ValueError):
            validate_evaluation(as_model(raw), conv, CHECKLIST)

    def test_score_is_invariant_to_decision_order(self):
        decision(self.raw, "02").update(response="N/A", na_reason="Enough information from the outset.")
        set_atomic(self.raw, "02.q1", "yes")
        decision(self.raw, "06")["response"] = 7
        expected = score_evaluation(as_model(self.raw), self.conv, CHECKLIST)
        shuffled = deepcopy(self.raw)
        random.Random(7).shuffle(shuffled["decisions"])
        self.assertEqual(score_evaluation(as_model(shuffled), self.conv, CHECKLIST), expected)
        # Independent check: W=85, earned=10+20+20+15+10.5+5=80.5 -> 94.7058... -> 94.71
        self.assertEqual(expected.total_score, "94.71")
        self.assertEqual(expected.applicable_weight, 85)


class CharacterizationTests(Base, unittest.TestCase):
    """Current behavior that is a risk. These pass; see qa/REPORT.md."""

    def test_c01_typographic_quote_normalization_rejects_evidence(self):
        # Source uses «Standard»; LLMs often normalize to straight quotes.
        # 42 of 882 shared DEV messages contain typographic quote marks.
        d = decision(self.raw, "04")
        d["evidence"] = [quote(self.m[6], text='your plan is "Standard"')]
        with self.assertRaises(ValueError):
            self.validate()

    def test_c02_one_bad_citation_discards_the_entire_evaluation(self):
        raw = valid_raw(self.conv, CHECKLIST)
        decision(raw, "05")["atomic_checks"][0]["evidence"] = [quote(self.m[8], text="Goodbye now")]
        with self.assertRaises(ValueError):
            evaluate(self.conv, CHECKLIST, ScriptedProvider(raw))  # no partial result, no score

    def test_c03_empty_turn_makes_the_whole_conversation_unloadable(self):
        record = make_record(GATES_EN)
        record["transcript"][4]["text"] = ""
        with self.assertRaises(ValueError):
            normalize_record(record, "QA", "0" * 64)

    def test_c04_unmapped_speaker_labels_fail_closed(self):
        for label in ("Operator", "agent", "customer", "оператор"):
            record = make_record(GATES_EN)
            record["transcript"][3]["speaker"] = label
            with self.subTest(label=label), self.assertRaises(ValueError):
                normalize_record(record, "QA", "0" * 64)

    def test_c05_language_code_is_not_validated(self):
        for language in ("kz", "Kazakh", "xx"):
            with self.subTest(language=language):
                self.assertEqual(make_conversation(GATES_KZ, language=language).language, language)

    def test_c06_non_zero_based_scale_cannot_be_configured(self):
        value = CHECKLIST.model_dump()
        criterion = value["criteria"][5]
        criterion.update(criterion_id="new-1to5", levels=[1, 2, 3, 4, 5],
                         anchors={str(i): f"Level {i}" for i in range(1, 6)})
        with self.assertRaises(ValidationError):
            Checklist.model_validate(value)

    def test_c07_new_critical_criterion_limited_to_three_official_categories(self):
        base = decision(valid_raw(self.conv, CHECKLIST), "08")
        base.update(response="yes", violation_categories=["guaranteed_returns_promise"])
        with self.assertRaises(ValidationError):
            Decision.model_validate(base)

    def test_c08_external_gate_rejects_any_team_synthetic_fixture(self):
        # Counterfactual/adversarial fixtures can never reach the OpenAI adapter
        # as configured, so semantic QA scenarios cannot run there without a
        # separately reviewed export policy.
        with self.assertRaises(ValueError):
            require_approved_synthetic(self.conv, True)

    def test_c09_critical_violation_does_not_escalate_status(self):
        raw = valid_raw(self.conv, CHECKLIST)
        d = decision(raw, "08")
        d.update(response="yes", violation_categories=["insult"], evidence=[quote(self.m[6]), scope(self.conv)])
        set_atomic(raw, "08.q1", "yes")
        result = evaluate(self.conv, CHECKLIST, ScriptedProvider(raw))
        self.assertTrue(result.score.critical_violation)
        self.assertEqual(result.status, "structurally_valid")
        self.assertEqual(result.score.total_score, "100.00")


class BaselineFixtureTest(Base, unittest.TestCase):
    def test_baseline_fixture_is_valid(self):
        self.assertAccepted()
        for turns in (GATES_RU, GATES_KZ, LATE_INTRO_EN):
            conv = make_conversation(turns)
            validate_evaluation(as_model(valid_raw(conv, CHECKLIST)), conv, CHECKLIST)


if __name__ == "__main__":
    unittest.main()
