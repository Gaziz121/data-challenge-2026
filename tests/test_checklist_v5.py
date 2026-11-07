"""Draft checklist v5: unambiguous C06 waiting fact. Offline fixtures only.

The p1-ru-001 case below is a HAND-AUTHORED counterfactual built from the live
a958142 reply (06 facts rewritten for v5); it is not model output or a label.
"""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from cqa.atomic_prompt import compile_atomic_schema
from cqa.engine import EvaluationRejected, evaluate
from cqa.io import load_checklist
from cqa.loader import ROOT, SHARED, load_conversation
from cqa.schemas import EvaluationConfig
from cqa.strict_schema import strict_issues
from tests.test_atomic_path import Scripted, decision, quote, scope
from tests.test_schema_reliability import FIXTURES, entry_conforms, record

V4CONFIG = EvaluationConfig(prompt_version="atomic-v5")


def v4():
    return load_checklist(ROOT / "src/cqa/checklists/official-v4.json")


def v5():
    return load_checklist(ROOT / "src/cqa/checklists/official-v5.json")


def with_c06(raw, conv, answer, evidence, response):
    raw = deepcopy(raw)
    c06 = decision(raw, "06")
    c06["atomic_checks"] = [a for a in c06["atomic_checks"] if a["question_id"] not in ("06.q3", "06.q4")] + [
        {"question_id": "06.q4", "answer": answer, "rationale": "Hand-authored v5 fixture.",
         "evidence": evidence, "events": []}]
    c06["judgment"]["response"] = response
    return raw


class ChecklistV5Tests(unittest.TestCase):
    def setUp(self):
        self.conv = load_conversation(SHARED, "p1-ru-001")
        self.live = json.loads((FIXTURES / "live_atomic_v3_a958142.json").read_text())["original_model_output"]

    def test_only_the_c06_waiting_fact_changes(self):
        old, new = v4(), v5()
        self.assertEqual(new.version, "2026-11-07.v5")
        for a, b in zip(old.criteria, new.criteria):
            for field in ("criterion_id", "title", "kind", "weight", "levels", "anchors", "na_condition",
                          "applicability_rule", "evidence_policy", "decision_rule", "output_source"):
                self.assertEqual(getattr(a, field), getattr(b, field), (a.criterion_id, field))
            if a.criterion_id != "06":
                self.assertEqual(a, b)
        c06 = next(c for c in new.criteria if c.criterion_id == "06")
        self.assertEqual([q.question_id for q in c06.questions], ["06.q1", "06.q2", "06.q4"])
        self.assertEqual([(r.question_id, r.when_answer, r.permitted_responses) for r in c06.consistency_rules],
                         [("06.q1", "no", [0, 4, 7]), ("06.q2", "yes", [0, 4]), ("06.q4", "yes", [0, 4, 7])])

    def test_no_waiting_now_permits_the_rationale_consistent_ten(self):
        raw = with_c06(self.live, self.conv, "no", [scope(self.conv)], 10)
        result = evaluate(self.conv, v5(), Scripted(raw), V4CONFIG)
        self.assertEqual({d.criterion_id: d.response for d in result.validated_evaluation.decisions}["06"], 10)
        self.assertEqual(result.score.total_score, "100.00")
        schema = compile_atomic_schema(self.conv, v5())
        self.assertTrue(entry_conforms(decision(raw, "06"), schema))
        quote_only = with_c06(self.live, self.conv, "no", [quote(self.conv.messages[9])], 10)
        self.assertFalse(entry_conforms(decision(quote_only, "06"), schema))  # Absence needs the full scope.
        with self.assertRaises(EvaluationRejected):
            evaluate(self.conv, v5(), Scripted(quote_only), V4CONFIG)

    def test_unwarned_operator_wait_still_caps_c06_without_forcing(self):
        conv = record([("client", "Can you check my order status?"), ("operator", "Hello, I am Sam."),
                       ("client", "Hello? Are you still there?"), ("operator", "Your order shipped. Goodbye.")])
        from tests.test_atomic_path import raw_fixture
        base = raw_fixture(conv, v5())
        for entry in base["criteria"]:  # Fixture absence facts cite only the full scope.
            for a in entry["atomic_checks"]:
                if a["answer"] == "no" and a["question_id"] in ("03.q1", "05.q3", "08.q1", "08.q2", "08.q3"):
                    a["evidence"] = [scope(conv)]
        schema = compile_atomic_schema(conv, v5())
        for response, accepted in ((10, False), (7, True), (4, True)):
            raw = with_c06(base, conv, "yes", [quote(conv.messages[2])], response)
            self.assertTrue(entry_conforms(decision(raw, "06"), schema))  # Scores are never grammar-forced.
            if accepted:
                result = evaluate(conv, v5(), Scripted(raw), V4CONFIG)
                self.assertEqual({d.criterion_id: d.response for d in result.validated_evaluation.decisions}["06"], response)
            else:
                with self.assertRaises(EvaluationRejected) as caught:
                    evaluate(conv, v5(), Scripted(raw), V4CONFIG)
                self.assertEqual({i["criterion_id"] for i in caught.exception.diagnostic["issues"]}, {"06"})

    def test_old_v4_fact_is_not_silently_migrated(self):
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, v5(), Scripted(self.live), V4CONFIG)
        self.assertEqual({i["criterion_id"] for i in caught.exception.diagnostic["issues"]}, {"06"})

    def test_strict_schema_and_backend_selection(self):
        records = json.loads(Path(SHARED).read_text())["data"]["records"]
        for r in records:
            self.assertEqual(strict_issues(compile_atomic_schema(load_conversation(SHARED, r["conversation_id"]), v5())), [])
        from cqa.checklists import ChecklistRegistry
        from cqa.web import ChecklistReference
        with tempfile.TemporaryDirectory() as folder:  # Runtime save, as POST /api/checklists does.
            registry = ChecklistRegistry(v4(), Path(folder), additional=[])
            saved = registry.save(v5())
            self.assertEqual(saved["version"], "2026-11-07.v5")
            self.assertEqual(registry.get(ChecklistReference(checklist_id=saved["checklist_id"],
                                                             version=saved["version"])), v5())

if __name__ == "__main__":
    unittest.main()


class LiveV4DuplicateRegressionTests(unittest.TestCase):
    """The one genuine atomic-v4 + v5 reply (2fcd958): rejected only for a duplicate 04.q1."""

    def setUp(self):
        from cqa.prompt import build_request
        self.build = build_request
        self.conv, self.checklist = load_conversation(SHARED, "p1-ru-001"), v5()
        self.fixture = json.loads((FIXTURES / "live_atomic_v4_2fcd958.json").read_text())
        self.raw = self.fixture["original_model_output"]

    def test_duplicate_was_legal_in_v4_and_is_not_in_v5(self):
        from cqa.strict_schema import conforms
        v4req, sha = self.build(self.conv, self.checklist, prompt_version="atomic-v4")
        self.assertEqual(sha, self.fixture["prompt_sha256"])
        self.assertTrue(conforms(self.raw, v4req["schema"]))  # Root cause: no upper item bound.
        v5req, _ = self.build(self.conv, self.checklist, prompt_version="atomic-v5")
        self.assertFalse(entry_conforms(decision(self.raw, "04"), v5req["schema"]))
        self.assertEqual([c["criterion_id"] for c in self.raw["criteria"] if not entry_conforms(c, v5req["schema"])], ["04"])
        self.assertEqual(strict_issues(v5req["schema"]), [])
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, Scripted(self.raw), V4CONFIG)
        self.assertEqual({i["criterion_id"] for i in caught.exception.diagnostic["issues"]}, {"04"})

    def test_bounded_repair_pins_agreeing_duplicate_and_fixes_only_c04(self):
        from cqa.schemas import RepairPolicy
        from tests.test_schema_reliability import CountingRepairProvider
        fixed = deepcopy(decision(self.raw, "04"))
        fixed["atomic_checks"] = fixed["atomic_checks"][:4]  # Hand-authored repair: duplicate dropped.
        provider = CountingRepairProvider(self.raw, {"schema_version": "1.2", "criteria": [fixed]})
        result = evaluate(self.conv, self.checklist, provider, V4CONFIG,
                          repair=RepairPolicy(authorization="offline unit test; no paid call"))
        attempt = result.repair_attempts[0]
        self.assertEqual((attempt.status, attempt.criterion_ids, provider.repair_calls), ("merged", ["04"], 1))
        self.assertEqual(attempt.pinned_answers["04.q1"], "yes")
        self.assertEqual(result.original_provider_output, self.raw)
        self.assertEqual(result.score.total_score, "100.00")  # Scripted repair: a fixture, not a measurement.


class LiveV5AcceptedRegressionTests(unittest.TestCase):
    """First genuine reply accepted without repair (atomic-v5 + v5, f20d00d). Not a label."""

    def test_replays_identically_and_request_reproduces(self):
        from cqa.prompt import build_request
        conv, checklist = load_conversation(SHARED, "p1-ru-001"), v5()
        fixture = json.loads((FIXTURES / "live_atomic_v5_f20d00d.json").read_text())
        _, sha = build_request(conv, checklist, prompt_version="atomic-v5")
        self.assertEqual(sha, fixture["prompt_sha256"])
        result = evaluate(conv, checklist, Scripted(fixture["original_model_output"]), V4CONFIG)
        self.assertEqual(result.score.total_score, "100.00")
        self.assertEqual(result.repair_attempts, [])
        self.assertEqual(result.original_provider_output, fixture["original_model_output"])
        # Semantic caveat pinned, not corrected: 07.q2 credits a farewell as an offer of help.
        c07 = next(c for c in fixture["original_model_output"]["criteria"] if c["criterion_id"] == "07")
        self.assertEqual(next(a["answer"] for a in c07["atomic_checks"] if a["question_id"] == "07.q2"), "yes")
