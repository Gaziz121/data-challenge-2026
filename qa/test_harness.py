"""Tests of the scenario labels and harness logic. None of this is semantic accuracy."""

import hashlib
import unittest

from cqa.io import load_checklist
from cqa.loader import SHARED
from cqa.providers import MockProvider
from qa.fixtures import ScriptedProvider
from qa.harness import apply_edits, build_cases, compare, load_scenarios, run

CHECKLIST = load_checklist()
SPEC = load_scenarios()


def permitted(criterion):
    values = list(criterion.levels) if criterion.kind == "discrete" else ["yes", "no"]
    return values + (["N/A"] if criterion.na_condition else [])


class ScenarioLabelTests(unittest.TestCase):
    def test_metadata_marks_labels_as_unreviewed_qa_proposals(self):
        self.assertEqual(SPEC["label_origin"], "team_qa_synthetic")
        self.assertEqual(SPEC["review_state"], "proposed_unreviewed")

    def test_every_expected_value_is_a_permitted_checklist_response(self):
        criteria = {c.criterion_id: c for c in CHECKLIST.criteria}
        items = SPEC["scenarios"] + SPEC["counterfactuals"]
        self.assertEqual(len({i["id"] for i in items}), len(items))
        for item in items:
            for key in ("expect", "base_expect"):
                for cid, row in item.get(key, {}).items():
                    with self.subTest(item=item["id"], criterion=cid):
                        self.assertIn(cid, criteria)
                        self.assertTrue(row["accept"] and row["why"].strip())
                        self.assertTrue(set(row["accept"]) <= set(permitted(criteria[cid])), row["accept"])

    def test_language_and_failure_mode_coverage(self):
        self.assertEqual({s["language"] for s in SPEC["scenarios"]}, {"RU", "KZ", "EN"})
        locked = {cid for s in SPEC["scenarios"] for cid, r in s["expect"].items() if r["lock"]}
        self.assertTrue({"01", "03", "04", "05", "07", "08"} <= locked)


class CounterfactualTests(unittest.TestCase):
    def test_variants_change_only_edited_turns_and_source_file_is_untouched(self):
        before = hashlib.sha256(SHARED.read_bytes()).hexdigest()
        cases = {case_id: conv for case_id, _, conv, _ in build_cases(SPEC)}
        self.assertEqual(hashlib.sha256(SHARED.read_bytes()).hexdigest(), before)
        for cf in SPEC["counterfactuals"]:
            base, variant = cases[cf["id"] + ":base"], cases[cf["id"] + ":variant"]
            edited = {e["index"] for e in cf["edits"]}
            with self.subTest(cf=cf["id"]):
                self.assertEqual(len(base.messages), len(variant.messages))
                for b, v in zip(base.messages, variant.messages):
                    self.assertEqual((b.role, b.timestamp), (v.role, v.timestamp))
                    self.assertEqual(b.text != v.text, b.source_index in edited)

    def test_ambiguous_or_missing_edit_target_is_rejected(self):
        record = {"transcript": [{"text": "a a"}]}
        for find in ("a", "zzz"):
            with self.subTest(find=find), self.assertRaises(ValueError):
                apply_edits(record, [{"index": 0, "find": find, "replace": "b"}])


class HarnessLogicTests(unittest.TestCase):
    expect = {"01": {"accept": ["no"], "lock": True, "why": "x"},
              "04": {"accept": [0, 5], "lock": False, "why": "x"}}

    def test_compare_pass_fail_recorded(self):
        rows = {r["criterion_id"]: r["verdict"] for r in compare(self.expect, {"01": "no", "04": 20}, True)}
        self.assertEqual(rows, {"01": "pass", "04": "recorded"})
        rows = {r["criterion_id"]: r["verdict"] for r in compare(self.expect, {"01": "yes"}, True)}
        self.assertEqual(rows["01"], "fail")

    def test_without_semantic_credit_nothing_passes_even_when_labels_match(self):
        rows = compare(self.expect, {"01": "no", "04": 0}, False)
        self.assertEqual([r["verdict"] for r in rows], ["not_assessed", "recorded"])

    def test_mock_run_end_to_end_earns_no_semantic_credit(self):
        report = run(MockProvider(), CHECKLIST, SPEC)
        summary = report["summary"]
        self.assertFalse(report["semantic_credit"])
        self.assertEqual(summary["pass"], 0)
        self.assertEqual(summary["fail"], 0)
        self.assertEqual(summary["not_assessed"], summary["locked_rows"])
        self.assertEqual(summary["engine_errors"], 0)
        self.assertEqual(summary["cases"], len(SPEC["scenarios"]) + 2 * len(SPEC["counterfactuals"]))

    def test_scripted_test_double_earns_no_semantic_credit(self):
        class Echo(ScriptedProvider):
            def evaluate(self, conversation, checklist, request, config):
                return MockProvider().evaluate(conversation, checklist, request, config)
        report = run(Echo(None), CHECKLIST, SPEC)
        self.assertFalse(report["semantic_credit"])
        self.assertEqual(report["summary"]["pass"], 0)

    def test_real_provider_engine_error_counts_as_failure(self):
        class Broken:
            name, model, is_mock = "broken-real", "none", False
            def evaluate(self, *args):
                raise ValueError("Simulated invalid structured output")
        report = run(Broken(), CHECKLIST, SPEC)
        self.assertTrue(report["semantic_credit"])
        self.assertEqual(report["summary"]["engine_errors"], report["summary"]["cases"])
        self.assertEqual(report["summary"]["fail"], report["summary"]["locked_rows"])
        self.assertEqual(report["summary"]["pass"], 0)


if __name__ == "__main__":
    unittest.main()
