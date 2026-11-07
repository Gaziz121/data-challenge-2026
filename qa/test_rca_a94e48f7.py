"""Replay and regression tests from the RCA of genuine evaluation a94e48f7.

Targets the integrated engine (codex/local-mvp-integration, f84d364 or later):

    PYTHONPATH=../data-challenge-2026-integration/src python3 -m unittest qa.test_rca_a94e48f7 -v

On an engine without the v2 checklist and diagnostics, the replay classes skip.
No model is called: the saved model output is replayed through a test double.

Expected on f84d364: the three `OutputContractDefects`/`DiagnosticDefects`
tests FAIL (RCA causes 1-3). Everything else passes.
"""

from copy import deepcopy
import itertools
import json
from pathlib import Path
import unittest

from pydantic import ValidationError

import cqa.engine as engine
import cqa.io as cqa_io
from cqa.io import digest, load_checklist
from cqa.loader import SHARED, load_conversation
from cqa.providers import MockProvider
from cqa.schemas import Checklist, Decision, ModelEvaluation
from qa.decision_rules import derive_response, disagreements
from qa.fixtures import ScriptedProvider

REPLAY = json.loads((Path(__file__).parent / "replays/a94e48f7.json").read_text(encoding="utf-8"))
V2_PATH = Path(cqa_io.__file__).parent / "checklists/official-v2.json"
INTEGRATED = hasattr(engine, "diagnose_output") and V2_PATH.exists()
SKIP = "Needs the integrated engine (diagnose_output + official-v2 checklist)"


def replay_inputs():
    checklist = load_checklist(V2_PATH)
    if digest(checklist.model_dump(mode="json")) != REPLAY["checklist_sha256"]:
        raise unittest.SkipTest("official-v2 checklist changed since the replay was captured")
    conversation = load_conversation(SHARED, REPLAY["conversation_id"])
    assert conversation.source_record_sha256 == REPLAY["source_record_sha256"]
    return conversation, checklist


def decision(cid):
    return deepcopy(next(d for d in REPLAY["original_model_output"]["decisions"] if d["criterion_id"] == cid))


class ReplayProvider(ScriptedProvider):
    name = "qa-replay-a94e48f7"
    model = REPLAY["model_returned"] + " (replayed offline)"


@unittest.skipUnless(INTEGRATED, SKIP)
class ReplayCharacterization(unittest.TestCase):
    """R1: what the engine does with the real response today (passes)."""

    def setUp(self):
        self.conv, self.checklist = replay_inputs()
        self.messages = {m.message_id: m for m in self.conv.messages}
        self.criteria = {c.criterion_id: c for c in self.checklist.criteria}

    def check(self, raw_decision):
        engine._validate_decision(Decision.model_validate(raw_decision), self.criteria[raw_decision["criterion_id"]],
                                  self.conv, self.messages)

    def test_r1_replay_is_rejected_without_a_score(self):
        with self.assertRaises(engine.EvaluationRejected) as caught:
            engine.evaluate(self.conv, self.checklist, ReplayProvider(REPLAY["original_model_output"]))
        diagnostic = caught.exception.diagnostic
        self.assertEqual(diagnostic["status"], "validation_failed")
        self.assertEqual({i["criterion_id"] for i in diagnostic["issues"]}, {"02", "04", "07"})
        self.assertNotIn("score", diagnostic)

    def test_r1_criterion_04_is_rejected_only_for_na_reason_text(self):
        d = decision("04")
        d["na_reason"] = None
        self.check(d)  # the substantive 04 decision is structurally valid

    def test_r1_02_and_07_contradict_their_own_applicability_answers(self):
        for cid, message in (("02", "Applicable response conflicts"), ("07", "N/A conflicts")):
            d = decision(cid)
            if d["response"] != "N/A":
                d["na_reason"] = None
            with self.subTest(criterion=cid), self.assertRaisesRegex(ValueError, message):
                self.check(d)

    def test_r1_other_five_decisions_validate(self):
        for cid in ("01", "03", "05", "06", "08"):
            with self.subTest(criterion=cid):
                self.check(decision(cid))


@unittest.skipUnless(INTEGRATED, SKIP)
class DiagnosticDefects(unittest.TestCase):
    """RCA cause 3: a schema error masks the contextual contradiction (fails on f84d364)."""

    def test_r1_diagnostic_reports_masked_applicability_conflict_for_02(self):
        conv, checklist = replay_inputs()
        issues, _ = engine.diagnose_output(REPLAY["original_model_output"], conv, checklist)
        messages_02 = [i["message"] for i in issues if i["criterion_id"] == "02"]
        self.assertTrue(any("Applicable response conflicts with an asserted N/A condition" in m
                            for m in messages_02), messages_02)


class OutputContractDefects(unittest.TestCase):
    """RCA causes 1-2: generation order and the unexplained na_reason field (fail on f84d364)."""

    def setUp(self):
        self.decision_schema = ModelEvaluation.model_json_schema()["$defs"]["Decision"]

    def test_r3_atomic_checks_are_generated_before_response(self):
        # OpenAI Structured Outputs produce keys in schema order (guide: "Key ordering").
        keys = list(self.decision_schema["properties"])
        self.assertLess(keys.index("atomic_checks"), keys.index("response"), keys)

    def test_r4_na_reason_is_described_in_the_schema(self):
        description = self.decision_schema["properties"]["na_reason"].get("description", "")
        self.assertIn("null", description.lower(), "na_reason needs a schema description sent to the model")


class SafeguardTests(unittest.TestCase):
    """R2 and ordering guards that must survive any fix (pass)."""

    def test_r2_applicable_decision_with_na_text_is_still_rejected(self):
        d = decision("04")
        self.assertIsNotNone(d["na_reason"])
        with self.assertRaises(ValidationError):
            Decision.model_validate(d)

    def test_applicability_question_is_asked_first(self):
        for criterion in load_checklist().criteria:
            if criterion.applicability_rule:
                with self.subTest(criterion=criterion.criterion_id):
                    self.assertEqual(criterion.questions[0].question_id, criterion.applicability_rule.question_id)


class DecisionRuleChecker(unittest.TestCase):
    """R5-R7: the QA reference checker (fix 4 proposal)."""

    def setUp(self):
        self.checklist = load_checklist()
        self.c = {c.criterion_id: c for c in self.checklist.criteria}

    def test_r5_replay_disagreements_are_exactly_02_and_07(self):
        found = disagreements(REPLAY["original_model_output"], self.checklist)
        self.assertEqual(found, [{"criterion_id": "02", "model_response": "yes", "derived": "N/A"},
                                 {"criterion_id": "07", "model_response": "N/A", "derived": "yes"}])

    def test_r6_criterion_07_truth_table(self):
        for q1, q2, q3 in itertools.product(("yes", "no"), repeat=3):
            expected = "N/A" if q1 == "yes" else ("yes" if q2 == q3 == "yes" else "no")
            with self.subTest(q1=q1, q2=q2, q3=q3):
                self.assertEqual(derive_response(self.c["07"], {"07.q1": q1, "07.q2": q2, "07.q3": q3}), expected)

    def test_r6_unknown_atomic_answer_derives_nothing(self):
        self.assertIsNone(derive_response(self.c["07"], {"07.q1": "no", "07.q2": "unknown", "07.q3": "yes"}))

    def test_r6_discrete_criterion_only_derives_applicability(self):
        self.assertEqual(derive_response(self.c["04"], {"04.q1": "no"}), "N/A")
        self.assertEqual(derive_response(self.c["04"], {"04.q1": "yes"}), "applicable")

    def test_r7_new_criterion_uses_generic_applicability_but_no_invented_rule(self):
        value = self.checklist.model_dump()
        new = deepcopy(next(c for c in value["criteria"] if c["criterion_id"] == "02"))
        new.update(criterion_id="organizer-new", title="Replacement criterion", consistency_rules=[])
        new["questions"][0]["question_id"] = "new.q1"
        new["questions"][1]["question_id"] = "new.q2"
        new["applicability_rule"]["question_id"] = "new.q1"
        value["criteria"].append(new)
        criterion = next(c for c in Checklist.model_validate(value).criteria if c.criterion_id == "organizer-new")
        self.assertEqual(derive_response(criterion, {"new.q1": "yes", "new.q2": "no"}), "N/A")
        self.assertIsNone(derive_response(criterion, {"new.q1": "no", "new.q2": "no"}))


class MockUnaffected(unittest.TestCase):
    """R8 (pass)."""

    def test_r8_mock_still_evaluates_and_checker_finds_nothing_to_derive_from_unknowns(self):
        checklist = load_checklist()
        conv = load_conversation(SHARED, REPLAY["conversation_id"])
        result = engine.evaluate(conv, checklist, MockProvider())
        self.assertEqual(result.status, "mock_only")
        raw = result.model_evaluation.model_dump(mode="json")
        self.assertEqual([d["criterion_id"] for d in disagreements(raw, checklist)], [])


if __name__ == "__main__":
    unittest.main()
