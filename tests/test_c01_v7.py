"""Checklist v7 (C01 wording only): reproducibility, non-default status, no DEV hardcoding, derivation
and the offline C01 comparison tooling. Offline only; no labels for real/DEV conversations are created."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from cqa.atomic_prompt import compile_atomic_schema
from cqa.engine import EvaluationRejected, evaluate
from cqa.io import load_checklist
from cqa.loader import ROOT, SHARED, load_conversation, normalize_record, read_dataset
from cqa.providers import MockProvider, ProviderReply
from cqa.schemas import EvaluationConfig
from cqa.strict_schema import strict_issues
from cqa_results.batch import run_batch
from cqa_results.export import check_checklist
from tests.test_atomic_path import raw_fixture, scope
from tests.test_schema_reliability import full_scope_normalized

sys.path.insert(0, str(ROOT / "tools"))
import c01_compare  # noqa: E402

CHECKLISTS = ROOT / "src/cqa/checklists"
FICTIONAL = ROOT / "docs/demo/c01_variants_fictional.json"
EXPECTED = ROOT / "tests/fixtures/c01_fictional_expectations.json"
V6_SHA256 = "c69b58142003f6b412d84478d41b0ab4cc8d70a854893468a0d9bc0aad995f69"
CONFIG = EvaluationConfig(prompt_version="atomic-v5", quote_policy="normalize_formatting")


def fixture_reply(conversation, checklist, q1="yes", q2="yes"):
    raw = raw_fixture(conversation, checklist)
    for entry in raw["criteria"]:
        criterion = next(c for c in checklist.criteria if c.criterion_id == entry["criterion_id"])
        for a in entry["atomic_checks"]:
            if a["question_id"] == "06.q4":
                a.update(answer="no", evidence=[scope(conversation)])
            if a["question_id"] in ("01.q1", "01.q2"):
                answer = q1 if a["question_id"] == "01.q1" else q2
                a["answer"] = answer
                if answer == "no":
                    a["evidence"] = [scope(conversation)]
        entry.update(full_scope_normalized(entry, criterion))
    return raw


class C01Fixture(MockProvider):
    model = "offline-c01-fixture"

    def __init__(self, answers):
        self.answers = answers

    def evaluate(self, conversation, checklist, request, config):
        q1, q2 = self.answers.get(conversation.conversation_id, ("yes", "yes"))
        return ProviderReply(fixture_reply(conversation, checklist, q1, q2), model=self.model)


class ChecklistV7Tests(unittest.TestCase):
    def setUp(self):
        self.v6 = json.loads((CHECKLISTS / "official-v6.json").read_text())
        self.v7 = json.loads((CHECKLISTS / "official-v7.json").read_text())

    def test_v6_is_byte_pinned_and_v7_changes_only_c01_wording(self):
        self.assertEqual(hashlib.sha256((CHECKLISTS / "official-v6.json").read_bytes()).hexdigest(), V6_SHA256)
        self.assertEqual(self.v7["version"], "2026-11-07.v7")
        strip_top = lambda c: {k: v for k, v in c.items() if k not in ("version", "source", "criteria")}
        self.assertEqual(strip_top(self.v6), strip_top(self.v7))
        for a, b in zip(self.v6["criteria"], self.v7["criteria"]):
            if a["criterion_id"] != "01":
                self.assertEqual(a, b)
                continue
            strip = lambda c: {**c, "instructions": None, "questions": [{**q, "question": None} for q in c["questions"]]}
            self.assertEqual(strip(a), strip(b))  # Weight, rule, fact policies, IDs, consistency unchanged.
            self.assertIn("поздоровался на языке клиента и представился в первом ответе", b["instructions"])
        check_checklist(load_checklist(CHECKLISTS / "official-v7.json"))

    def test_v7_is_not_a_default(self):
        self.assertNotEqual(load_checklist().version, "2026-11-07.v7")
        from cqa import web
        self.assertIn("official-v7.json", Path(web.__file__).read_text())  # Selectable only.
        import inspect
        self.assertNotIn("official-v7", inspect.getsource(web.main))

    def test_no_dev_conversation_hardcoding(self):
        text = (CHECKLISTS / "official-v7.json").read_text()
        data, _ = read_dataset(SHARED)
        for record in data["records"]:
            self.assertNotIn(record["conversation_id"], text)
            first = next((t["text"] for t in record["transcript"] if t["speaker"] == "operator"), "")
            self.assertNotIn(first[:25], text)
        fictional_ids = [r["conversation_id"] for r in json.loads(FICTIONAL.read_text())["data"]["records"]]
        self.assertTrue(all("yes" not in i and "no" not in i for i in fictional_ids))  # IDs do not leak labels.

    def test_strict_schema_for_all_dev_chats_and_fictional_cases(self):
        checklist = load_checklist(CHECKLISTS / "official-v7.json")
        data, _ = read_dataset(SHARED)
        for record in data["records"]:
            self.assertEqual(strict_issues(compile_atomic_schema(load_conversation(SHARED, record["conversation_id"]), checklist)), [])
        fictional, digest = read_dataset(FICTIONAL)
        for record in fictional["data"]["records"] if "data" in fictional else fictional["records"]:
            conv = normalize_record(record, fictional["dataset_group_id"], digest)
            self.assertEqual(strict_issues(compile_atomic_schema(conv, checklist)), [])

    def test_c01_derivation_is_the_unchanged_conjunction(self):
        conv = load_conversation(SHARED, "p1-en-011")
        for version in ("v6", "v7"):
            checklist = load_checklist(CHECKLISTS / ("official-%s.json" % version))
            for q1, q2, expected in (("yes", "yes", "yes"), ("yes", "no", "no"), ("no", "yes", "no"), ("no", "no", "no")):
                with self.subTest(version=version, q1=q1, q2=q2):
                    provider = C01Fixture({conv.conversation_id: (q1, q2)})
                    result = evaluate(conv, checklist, provider, CONFIG)
                    decision = next(d for d in result.validated_evaluation.decisions if d.criterion_id == "01")
                    self.assertEqual(decision.response, expected)
            with self.assertRaises(EvaluationRejected):  # Unknown greeting fact still blocks; nothing guessed.
                evaluate(conv, checklist, C01Fixture({conv.conversation_id: ("unknown", "yes")}), CONFIG)


class C01ToolingTests(unittest.TestCase):
    def setUp(self):
        self.expected = {c["conversation_id"]: c for c in json.loads(EXPECTED.read_text())["cases"]}
        self.records = json.loads(FICTIONAL.read_text())["data"]["records"]

    def test_fictional_set_is_balanced_and_heuristic_matches_construction(self):
        values = [c["c01"] for c in self.expected.values()]
        self.assertEqual((values.count("yes"), values.count("no")), (4, 4))
        self.assertEqual({c["language"] for c in self.expected.values()}, {"RU", "KZ", "EN"})
        for record in self.records:
            exp = self.expected[record["conversation_id"]]
            self.assertEqual(c01_compare.heuristic(record), (exp["01.q1"], exp["01.q2"]), record["conversation_id"])

    def test_compare_reads_original_answers_and_counts_flips(self):
        (ROOT / "outputs").mkdir(exist_ok=True)
        checklists = {v: load_checklist(CHECKLISTS / ("official-%s.json" % v)) for v in ("v6", "v7")}
        # Arm A answers like the observed v6 failure (greeting missed); arm B follows construction.
        arm_a = {cid: ("no", e["01.q2"]) for cid, e in self.expected.items()}
        arm_b = {cid: (e["01.q1"], e["01.q2"]) for cid, e in self.expected.items()}
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as folder:
            for name, answers in (("v6", arm_a), ("v7", arm_b)):
                run_batch(FICTIONAL, Path(folder) / name, C01Fixture(answers), checklist=checklists[name],
                          config=CONFIG, log=lambda *_: None)
            runs = {n: c01_compare.collect(Path(folder) / n) for n in ("v6", "v7")}
        report = c01_compare.compare(self.records, runs, self.expected)
        self.assertEqual(report["summary"]["v7"]["constructed_agree"], 8)
        self.assertEqual(report["summary"]["v6"]["constructed_false_no"], 4)
        self.assertEqual(len(report["flips"]), 4)


if __name__ == "__main__":
    unittest.main()
