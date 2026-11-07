"""Offline real-failure replay and conditional/coverage security boundaries."""

from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import unittest

from cqa.coverage import coverage_proof, decision_coverage
from cqa.decision_rules import assess_decision
from cqa.engine import EvaluationRejected, diagnose_output, evaluate
from cqa.io import digest, load_checklist
from cqa.loader import ROOT, SHARED, load_conversation
from cqa.prompt import build_request
from cqa.providers import MockProvider, ProviderReply
from cqa.schemas import Checklist, ModelEvaluation
from cqa.validation import validate_evaluation
from tests.helpers import conversation, evaluation_data


class Replayed(MockProvider):
    def __init__(self, raw):
        self.raw = raw

    def evaluate(self, *args):
        return ProviderReply(deepcopy(self.raw), model="offline-replay-not-new-inference")


def scope(start, end):
    return {"kind": "scope", "message_id": None, "quote": None,
            "start_message_id": start, "end_message_id": end,
            "explanation": "Offline fixture: exactly this source interval was inspected."}


class DecisionCoverageTests(unittest.TestCase):
    def setUp(self):
        self.conv, self.checklist = conversation(), load_checklist()
        self.criterion = next(c for c in self.checklist.criteria if c.criterion_id == "05")

    def values(self, polite="yes", trigger="yes", addressed="yes", response="yes"):
        return {"response": response, "atomic_checks": [
            {"question_id": "05.q1", "answer": polite}, {"question_id": "05.q3", "answer": trigger},
            {"question_id": "05.q2", "answer": addressed}]}

    def test_official_conditional_truth_table_and_absent_complaint(self):
        for polite, trigger, addressed in product(("yes", "no"), repeat=3):
            expected = "yes" if polite == "yes" and (trigger == "no" or addressed == "yes") else "no"
            value = self.values(polite, trigger, "not_applicable" if trigger == "no" else addressed, expected)
            result = assess_decision(self.criterion, value)
            self.assertEqual((result.derived_response, result.status, result.issues), (expected, "agreed", []))
        self.assertIsNone(self.criterion.na_condition)  # No complaint never creates criterion N/A.

    def test_unknown_missing_duplicate_and_illegal_atomic_na_do_not_derive(self):
        for index in range(3):
            value = self.values(); value["atomic_checks"][index]["answer"] = "unknown"
            self.assertIsNone(assess_decision(self.criterion, value).derived_response)
            value = self.values(); del value["atomic_checks"][index]
            self.assertIsNone(assess_decision(self.criterion, value).derived_response)
        value = self.values(); value["atomic_checks"].append(value["atomic_checks"][0])
        self.assertIsNone(assess_decision(self.criterion, value).derived_response)
        for trigger, addressed in (("no", "no"), ("yes", "not_applicable")):
            assessment = assess_decision(self.criterion, self.values(trigger=trigger, addressed=addressed))
            self.assertIsNone(assessment.derived_response)
            self.assertTrue(assessment.issues)

    def test_disagreement_retains_original_response_and_blocks_score(self):
        raw = evaluation_data(self.conv, self.checklist)
        decision = next(d for d in raw["decisions"] if d["criterion_id"] == "05")
        next(a for a in decision["atomic_checks"] if a["question_id"] == "05.q2")["answer"] = "no"
        before = deepcopy(raw)
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, Replayed(raw))
        diagnostic = caught.exception.diagnostic
        check = diagnostic["decision_rule_checks"][0]
        self.assertEqual((check["model_response"], check["derived_response"], check["status"]), ("yes", "no", "disagreed"))
        self.assertEqual(diagnostic["original_model_output"], before)
        self.assertEqual(raw, before)
        self.assertNotIn("score", diagnostic)

    def test_absent_complaint_passes_with_atomic_not_applicable(self):
        raw = evaluation_data(self.conv, self.checklist)
        decision = next(d for d in raw["decisions"] if d["criterion_id"] == "05")
        answers = {a["question_id"]: a for a in decision["atomic_checks"]}
        answers["05.q3"]["answer"], answers["05.q2"]["answer"] = "no", "not_applicable"
        result = evaluate(self.conv, self.checklist, Replayed(raw))
        self.assertEqual(result.decision_rule_checks[0].derived_response, "yes")
        self.assertEqual(result.model_evaluation, result.validated_evaluation)
        self.assertEqual(result.score.total_score, "100.00")  # Calculation fixture, not a semantic judgment.

    def test_new_ids_edited_questions_no_rule_and_invalid_references(self):
        value = self.criterion.model_dump()
        value["criterion_id"] = "organizer-new"
        mapping = {q["question_id"]: "renamed-" + str(i) for i, q in enumerate(value["questions"])}
        for q in value["questions"]:
            q["question_id"], q["question"] = mapping[q["question_id"]], "Edited " + q["question"]
        value["decision_rule"]["all_of"] = [mapping[q] for q in value["decision_rule"]["all_of"]]
        cond = value["decision_rule"]["conditional"]
        for key in ("trigger_question_id", "requirement_question_id"):
            cond[key] = mapping[cond[key]]
        value["consistency_rules"] = []
        from cqa.schemas import Criterion
        custom = Criterion.model_validate(value)
        answers = self.values()
        for a in answers["atomic_checks"]:
            a["question_id"] = mapping[a["question_id"]]
        self.assertEqual(assess_decision(custom, answers).derived_response, "yes")
        value["decision_rule"] = None
        self.assertIsNone(assess_decision(Criterion.model_validate(value), answers))
        value = custom.model_dump(); value["decision_rule"]["all_of"] = ["missing"]
        with self.assertRaises(ValueError):
            Criterion.model_validate(value)

    def test_full_source_coverage_union_gaps_overlap_bad_ids_and_quotes(self):
        first, last = self.conv.messages[0].message_id, self.conv.messages[-1].message_id
        for refs, complete in (([scope(first, last)], True),
                               ([scope(first, "m0001"), scope("m0002", last)], True),
                               ([scope(first, "m0002"), scope("m0001", last)], True),
                               ([scope(first, "m0000"), scope("m0002", last)], False),
                               ([scope(last, last)] * len(self.conv.messages), False),
                               ([scope(last, first)], False),
                               ([scope(first, last), scope("invented", last)], False)):
            proof = coverage_proof(self.conv, "custom-critical", refs, ["evidence"])
            self.assertEqual(proof.complete, complete)
        quote = evaluation_data(self.conv, self.checklist)["decisions"][0]["evidence"]
        self.assertFalse(coverage_proof(self.conv, "08", quote, ["evidence"]).complete)
        complete = coverage_proof(self.conv, "08", [scope(first, last)], ["evidence"])
        changed = self.conv.model_copy(deep=True)
        changed.messages[0] = changed.messages[0].model_copy(update={"text": "Different source text"})
        changed_proof = coverage_proof(changed, "08", [scope(first, last)], ["evidence"])
        self.assertNotEqual(complete.conversation_sha256, changed_proof.conversation_sha256)
        self.assertNotEqual(complete.messages_sha256, changed_proof.messages_sha256)

    def test_full_decision_scope_does_not_hide_partial_negative_atomic_scope(self):
        raw = evaluation_data(self.conv, self.checklist)
        decision = raw["decisions"][-1]
        decision["atomic_checks"][0]["evidence"] = [scope("m0003", "m0003")]
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, Replayed(raw))
        proofs = caught.exception.diagnostic["coverage_proofs"]
        self.assertTrue(proofs[0]["complete"])
        self.assertFalse(proofs[1]["complete"])
        self.assertEqual(proofs[1]["missing_message_ids"], ["m0000", "m0001", "m0002"])
        self.assertEqual(proofs[1]["evidence_path"], ["atomic_checks", 0, "evidence"])

    def test_prompt_supplies_exact_scope_and_trigger_first_without_mutation(self):
        before = digest(self.checklist.model_dump(mode="json"))
        request, _ = build_request(self.conv, self.checklist)
        payload = json.loads(request["input"])
        c = next(c for c in payload["checklist"]["criteria"] if c["criterion_id"] == "05")
        self.assertEqual(c["questions"][0]["question_id"], "05.q3")
        requirement = payload["source_coverage_requirements"][0]
        self.assertEqual(requirement["required_message_ids"], [m.message_id for m in self.conv.messages])
        self.assertEqual(requirement["scope_template"]["end_message_id"], "m0003")
        self.assertIn("not_applicable, NOT no", request["instructions"])
        self.assertEqual(before, digest(self.checklist.model_dump(mode="json")))


class RealFailureReplayTests(unittest.TestCase):
    def setUp(self):
        self.replay = json.loads((Path(__file__).parent / "fixtures/live_c379231.json").read_text())
        self.conv = load_conversation(SHARED, self.replay["conversation_id"])
        self.assertEqual(self.conv.source_record_sha256, self.replay["source_record_sha256"])
        self.old = load_checklist(ROOT / "src/cqa/checklists/official-v2.json")
        self.raw = deepcopy(self.replay["original_model_output"])

    def test_exact_second_live_response_still_rejected_with_two_precise_causes(self):
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.old, Replayed(self.raw))
        diagnostic = caught.exception.diagnostic
        self.assertEqual({i["criterion_id"] for i in diagnostic["issues"]}, {"05", "08"})
        self.assertEqual(diagnostic["original_model_output"], self.raw)
        self.assertNotIn("score", diagnostic)
        self.assertEqual(diagnostic["coverage_proofs"][0]["missing_message_ids"], [f"m{i:04d}" for i in range(9)])

    def test_old_ambiguous_answers_are_not_migrated_or_used_to_infer_trigger(self):
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, load_checklist(), Replayed(self.raw))
        diagnostic = caught.exception.diagnostic
        check = diagnostic["decision_rule_checks"][0]
        self.assertIsNone(check["derived_response"])
        self.assertEqual(check["status"], "undetermined")
        self.assertEqual(diagnostic["original_model_output"], self.raw)
        self.assertNotIn("score", diagnostic)
        self.assertTrue(any(i["criterion_id"] == "05" and "exactly once" in i["message"] for i in diagnostic["issues"]))

    def test_old_checklist_hash_and_explicit_version_selection_preserved(self):
        import tempfile
        from cqa.web import Application, EvaluationRequest
        self.assertEqual(digest(self.old.model_dump(mode="json")), digest(json.loads((ROOT / "src/cqa/checklists/official-v2.json").read_text())))
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as folder:
            app = Application(api_key="", output_dir=Path(folder) / "app", live_call_limit=0)
            result = app.run(EvaluationRequest(conversation_id="p1-ru-001", checklist={
                "checklist_id": self.old.checklist_id, "version": self.old.version}))
            self.assertEqual(result.checklist.version, "2026-11-07.v2")
            self.assertEqual(app.checklist.version, "2026-11-07.v3")
