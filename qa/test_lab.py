"""Tests of the offline Accuracy Lab (qa/lab). No model is called; nothing here is accuracy.

    PYTHONPATH=<engine>/src python3 -B -m unittest qa.test_lab -v

Capture-based tests need the integrated engine (EvaluationRejected); they skip otherwise.
"""

import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import cqa.engine as engine
from cqa.io import load_checklist
from cqa.loader import SHARED, read_dataset

from qa.harness import DEFAULT_SCENARIOS, load_scenarios
from qa.lab import __main__ as cli
from qa.lab.artifacts import MANIFEST, load_artifact, load_run, origin_of, source_catalogue
from qa.lab.checks import check_decision, exact_total, quote_status, round_half_up
from qa.lab.compare import assess_case, compare_runs, redact_for_holdout, render, _cf_outcome
from qa.lab.labels import human_labels, load_human_export, load_registry, scenario_labels
from qa.lab.splits import (SYNTHETIC_SPLIT, FrozenHoldoutChanged, build_synthetic_split, load_split,
                           make_dataset_split)

SPEC = load_scenarios()
REGISTRY = load_registry()
ROWS = scenario_labels(SPEC, REGISTRY, DEFAULT_SCENARIOS.read_bytes())
SPLIT = load_split(SYNTHETIC_SPLIT, ROWS)
CAN_CAPTURE = hasattr(engine, "EvaluationRejected")
DEMO = Path(cli.__file__).parent / "demo"


class LabelClassificationTests(unittest.TestCase):
    def test_every_scenario_row_is_classified_once_and_registry_is_pinned(self):
        expected = sum(len(s["expect"]) for s in SPEC["scenarios"]) + sum(
            len(c["base_expect"]) + len(c["expect"]) for c in SPEC["counterfactuals"])
        self.assertEqual(len(ROWS), expected)
        self.assertEqual(REGISTRY["scenario_file_sha256"], hashlib.sha256(DEFAULT_SCENARIOS.read_bytes()).hexdigest())
        self.assertEqual({r["tier"] for r in ROWS}, {"proposed_unreviewed", "ambiguous"})

    def test_unlocked_rows_are_ambiguous_and_scored_rows_have_one_answer(self):
        lock = {(s["id"], cid): r["lock"] for s in SPEC["scenarios"] for cid, r in s["expect"].items()}
        for row in ROWS:
            with self.subTest(item=row["item_id"], criterion=row["criterion_id"]):
                if not lock.get((row["item_id"], row["criterion_id"]), True):
                    self.assertEqual(row["tier"], "ambiguous")
                if row["tier"] == "proposed_unreviewed":
                    self.assertEqual(len(row["accept"]), 1, "exact match needs a single expected response")
                self.assertEqual(row["origin"], "team_qa_synthetic")

    def test_stale_registry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "re-classify"):
            scenario_labels(SPEC, REGISTRY, DEFAULT_SCENARIOS.read_bytes() + b" ")


class SplitTests(unittest.TestCase):
    def test_split_is_reproducible_from_metadata(self):
        rebuilt = build_synthetic_split(SPEC, ROWS, SPLIT["seed"])
        for key in ("groups", "case_split", "strata", "holdout_label_sha256"):
            self.assertEqual(rebuilt[key], SPLIT[key], key)
        self.assertEqual(set(SPLIT["groups"].values()), {"calibration", "holdout"})

    def test_counterfactual_base_and_variants_share_one_side(self):
        for cf in SPEC["counterfactuals"]:
            self.assertEqual(SPLIT["case_split"][cf["id"]], SPLIT["case_split"][cf["conversation_id"]])

    def test_editing_a_holdout_label_breaks_the_freeze_but_calibration_does_not(self):
        rows = deepcopy(ROWS)
        holdout = next(r for r in rows if SPLIT["case_split"][r["conversation_id"]] == "holdout")
        calibration = next(r for r in deepcopy(ROWS) if SPLIT["case_split"][r["conversation_id"]] == "calibration")
        holdout["accept"] = ["N/A"]
        with self.assertRaises(FrozenHoldoutChanged):
            load_split(SYNTHETIC_SPLIT, rows)
        rows = deepcopy(ROWS)
        next(r for r in rows if r["conversation_id"] == calibration["conversation_id"])["accept"] = ["N/A"]
        load_split(SYNTHETIC_SPLIT, rows)

    def test_demo_fixtures_use_calibration_cases_only(self):
        for name in ("baseline", "candidate"):
            plan = json.loads((DEMO / f"{name}.json").read_text(encoding="utf-8"))
            for cid in plan["cases"]:
                self.assertEqual(SPLIT["case_split"].get(cid), "calibration", cid)

    def test_dev_split_is_stratified_metadata_only(self):
        data, _ = read_dataset(SHARED)
        manifest = make_dataset_split(data["records"], "seed-a")
        self.assertEqual(manifest, make_dataset_split(data["records"], "seed-a"))
        for stratum in manifest["strata"].values():
            self.assertEqual((stratum["calibration"], stratum["holdout"]), (3, 2))
        self.assertIsNone(manifest["holdout_label_sha256"])

    def test_holdout_requires_confirmation_and_is_aggregate_only(self):
        args = argparse.Namespace(dataset=SHARED, human_labels=None, split="holdout", split_manifest=None,
                                  holdout_confirm=False)
        with self.assertRaises(SystemExit):
            cli.context(args)
        report = redact_for_holdout({"fixed": [{"x": 1}], "regressed": [], "baseline": {"counterfactuals": {}}})
        self.assertEqual(report["fixed"], "withheld on holdout (1 items)")
        self.assertIn("exposed", report["holdout_notice"])


class EvidenceAndInvariantTests(unittest.TestCase):
    def test_quote_status_ru_kz_en(self):
        ru = "Откройте раздел «Пополнение» и выберите оплату картой."
        kz = "Сәлеметсіз бе, менің атым Айгерім."
        self.assertEqual(quote_status("раздел «Пополнение»", ru), "exact")
        self.assertEqual(quote_status('раздел "Пополнение"', ru), "formatting_only")
        self.assertEqual(quote_status("менің атым Айгерім", kz), "exact")
        self.assertEqual(quote_status("менің атым Айгерим", kz), "invalid")  # і -> и is a letter change
        self.assertEqual(quote_status("Сәлеметсіз  бе", kz), "formatting_only")
        self.assertEqual(quote_status("сәлеметсіз бе", kz), "invalid")  # no case folding
        self.assertEqual(quote_status("!", "Goodbye!"), "invalid")

    def test_exact_total_and_rounding(self):
        checklist = load_checklist().model_dump(mode="json")
        responses = {"01": "yes", "02": "N/A", "03": "yes", "04": 15, "05": "yes", "06": 7, "07": "yes", "08": "no"}
        total = exact_total(responses, checklist)
        self.assertEqual(total, Fraction(100, 85) * (10 + 20 + 15 + 15 + Fraction(105, 10) + 5))
        self.assertEqual(round_half_up(total), "88.82")  # 75.5 / 85 * 100
        self.assertEqual(round_half_up(Fraction(-1, 200)), "-0.01")
        self.assertEqual(round_half_up(Fraction(-1, 1000)), "0.00")

    def test_cf_monotonicity_flags_a_more_favorable_variant(self):
        criterion = {"criterion_id": "07", "kind": "binary", "levels": []}
        case = lambda r: {"valid_output": True, "criteria": {"07": criterion}, "cells": {"07": {"response": r}},
                          "origin": "model"}
        cf = {"id": "cf-x", "expect": {"07": {}}}
        self.assertFalse(_cf_outcome(case("no"), case("yes"), cf, [], False)["07"]["monotonic"])
        self.assertTrue(_cf_outcome(case("yes"), case("no"), cf, [], False)["07"]["monotonic"])
        self.assertIsNone(_cf_outcome(case("yes"), case("N/A"), cf, [], False)["07"]["monotonic"])

    def test_origin_classification(self):
        self.assertEqual(origin_of({"is_mock": True, "provider": "mock"}), "mock")
        self.assertEqual(origin_of({"is_mock": False, "provider": "qa-scripted"}), "test_double")
        self.assertEqual(origin_of({"is_mock": False, "provider": "qa-replay-a94e48f7"}), "test_double")
        self.assertEqual(origin_of({"is_mock": False, "provider": "openai"}), "model")


def human_export(records, dataset_sha, reviewer, cid, responses, evidence_index=0):
    record = records[cid]
    turn = record["transcript"][evidence_index]
    criteria = []
    for criterion_id in ("01", "02", "03", "04", "05", "06", "07", "08"):
        criteria.append({"criterion_id": criterion_id, "response": responses.get(criterion_id),
                         "justification": "FICTIONAL TEST LABEL - not a human assessment.",
                         "evidence": [{"transcript_index": evidence_index, "original_message_id": None,
                                       "timestamp": turn["timestamp"], "speaker": turn["speaker"],
                                       "text": turn["text"]}], "scope_note": "test fixture"})
    return {"schema_version": "dev-team-human-1", "label_source": "team_human", "official_ground_truth": False,
            "reviewer_id": reviewer, "created_at": "2026-11-07T00:00:00Z", "exported_at": "2026-11-07T00:00:00Z",
            "dataset": {"path": "data/shared/DEV_synthetic_60.json", "sha256": dataset_sha},
            "rubric_version": "dev-human-review-2026-11-07.v1", "rubric_sha256": "fixture",
            "assessments": [{"conversation_id": cid, "language": record["language"], "channel": record["channel"],
                             "updated_at": "2026-11-07T00:00:00Z", "status": "draft", "criteria": criteria}]}


class HumanImportTests(unittest.TestCase):
    """The Viewer's real export contract (tools/dev_review/viewer.js `bundle`), fictional values."""

    def setUp(self):
        _, self.records, self.sha = source_catalogue(SPEC, SHARED)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, value, name):
        path = Path(self.tmp.name) / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def test_valid_export_imports_scored_cells_only(self):
        path = self.write(human_export(self.records, self.sha, "r1", "p1-kz-001", {"01": "yes", "04": 0}), "a.json")
        export = load_human_export(path, self.records, self.sha)
        self.assertEqual({(c["criterion_id"], c["response"]) for c in export["cells"]}, {("01", "yes"), ("04", 0)})
        rows = human_labels([export])
        self.assertEqual({r["tier"] for r in rows}, {"team_human"})

    def test_disagreeing_reviewers_are_disputed_not_merged(self):
        a = load_human_export(self.write(human_export(self.records, self.sha, "r1", "p1-ru-002", {"07": "yes"}),
                                         "a.json"), self.records, self.sha)
        b = load_human_export(self.write(human_export(self.records, self.sha, "r2", "p1-ru-002", {"07": "no"}),
                                         "b.json"), self.records, self.sha)
        (row,) = human_labels([a, b])
        self.assertEqual((row["tier"], row["reviewers"]), ("disputed", ["r1", "r2"]))
        with self.assertRaisesRegex(ValueError, "twice"):
            human_labels([a, a])

    def test_invalid_exports_are_rejected(self):
        base = human_export(self.records, self.sha, "r1", "p1-en-001", {"01": "no"})
        for name, change in (("official", lambda x: x.update(official_ground_truth=True)),
                             ("dataset", lambda x: x["dataset"].update(sha256="0" * 64)),
                             ("evidence", lambda x: x["assessments"][0]["criteria"][0]["evidence"][0].update(text="edited")),
                             ("index", lambda x: x["assessments"][0]["criteria"][0]["evidence"][0].update(transcript_index=999)),
                             ("language", lambda x: x["assessments"][0].update(language="RU"))):
            value = deepcopy(base)
            change(value)
            with self.subTest(name), self.assertRaises(ValueError):
                load_human_export(self.write(value, name + ".json"), self.records, self.sha)


@unittest.skipUnless(CAN_CAPTURE, "Needs the integrated engine (EvaluationRejected) for scripted capture")
class PairedComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dirs = {}
        for name in ("baseline", "candidate"):
            cls.dirs[name] = cli.cmd_capture(argparse.Namespace(
                fixture=DEMO / f"{name}.json", out=Path(cls.tmp.name) / name, engine_commit="test", dataset=SHARED))
        cls.catalogue, cls.records, cls.sha = source_catalogue(SPEC, SHARED)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def compare(self, demo, rows=ROWS, base=None, cand=None):
        return compare_runs(load_run(base or self.dirs["baseline"]), load_run(cand or self.dirs["candidate"]),
                            self.catalogue, rows, SPEC, SPLIT["case_split"], "calibration", demo)

    def copy_run(self, name, edit):
        target = Path(tempfile.mkdtemp(prefix=name + "-edited-", dir=self.tmp.name))
        for path in self.dirs[name].glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if path.name != MANIFEST:
                edit(path.stem, value)
            (target / path.name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return target

    def test_test_double_outputs_earn_no_semantic_credit(self):
        report = self.compare(demo=False)
        self.assertEqual(report["measurement_status"], "not_assessed (or partial)")
        self.assertEqual(report["fixed"] + report["regressed"], [])
        self.assertTrue(all("not_assessed" in k or "excluded" in k for k in report["label_transitions"]))
        self.assertEqual(report["baseline"]["label_metrics"], {})

    def test_demo_mechanics_report_paired_changes_and_regressions(self):
        report = self.compare(demo=True)
        self.assertEqual(report["measurement_status"], "demonstration_only")
        self.assertIn("NOT a semantic accuracy measurement", render(report))
        self.assertEqual(report["validation_transitions"], {"accepted -> accepted": 5, "rejected -> accepted": 2})
        self.assertEqual(report["label_transitions"]["proposed_unreviewed: fixed"], 4)
        self.assertEqual([(d["conversation_id"], d["criterion_id"]) for d in report["regressed"]],
                         [("qa-kz-positive-control", "07")])
        self.assertEqual(report["label_transitions"]["ambiguous: excluded_ambiguous"], 1)
        self.assertEqual(report["changed_unlabeled"], [{"conversation_id": "qa-en-prompt-injection",
                                                        "criterion_id": "06", "baseline": 10, "candidate": 7}])
        self.assertEqual(report["candidate"]["evidence"]["formatting_only"], 5)
        self.assertEqual(report["total_differences_skipped"], {"baseline invalid": 2})
        self.assertNotIn("qa-en-late-intro", [d["conversation_id"] for d in report["total_differences"]])
        cf = report["counterfactual_changes"]["cf-en-009-remove-intro"]["01"]
        self.assertEqual((cf["baseline"]["label_flip"], cf["candidate"]["label_flip"]), (False, True))

    def test_genuine_origin_is_assessed_without_demo_flag(self):
        def as_model(_, value):
            value["run"]["provider"] = "openai"  # plumbing test: provider identity only
        report = self.compare(demo=False, base=self.copy_run("baseline", as_model),
                              cand=self.copy_run("candidate", as_model))
        self.assertEqual(report["measurement_status"], "genuine_model_outputs")
        self.assertEqual(len(report["regressed"]), 1)

    def test_source_tampering_invalidates_the_case(self):
        def tamper(stem, value):
            if stem == "qa-kz-positive-control":
                message = value["conversation"]["messages"][3]
                message["text"] = message["text"].replace("Айгерім", "Айгерим")
        run = load_run(self.copy_run("candidate", tamper))
        case = assess_case(run["cases"]["qa-kz-positive-control"], self.catalogue["qa-kz-positive-control"])
        self.assertFalse(case["valid_output"])
        self.assertIn("INV-SRC", {i["invariant"] for i in case["issues"]})
        report = self.compare(demo=True, cand=self.copy_run("candidate", tamper))
        regressed = {(d["criterion_id"], d["candidate"]) for d in report["regressed"]
                     if d["conversation_id"] == "qa-kz-positive-control"}
        self.assertIn(("01", "invalid output; raw 'yes'"), regressed)

    def test_different_source_versions_are_not_paired(self):
        def other_version(stem, value):
            if stem == "p1-en-009":
                value["conversation"]["source_record_sha256"] = "0" * 64
        report = self.compare(demo=True, cand=self.copy_run("candidate", other_version))
        self.assertIn({"conversation_id": "p1-en-009", "reason": "different source conversation content"},
                      report["unpaired"])
        self.assertNotIn("p1-en-009", report["paired_cases"])

    def test_recorded_total_must_reconcile(self):
        def tamper(stem, value):
            if stem == "p1-en-009":
                value["score"]["total_exact_numerator"] += 1
        case = assess_case(load_run(self.copy_run("candidate", tamper))["cases"]["p1-en-009"],
                           self.catalogue["p1-en-009"])
        self.assertIsNone(case["total"])
        self.assertIn("INV-TOTAL", {i["invariant"] for i in case["issues"]})

    def test_human_labels_are_a_separate_tier(self):
        path = Path(self.tmp.name) / "human.json"
        path.write_text(json.dumps(human_export(self.records, self.sha, "r1", "p1-en-009", {"01": "yes", "03": "N/A"})),
                        encoding="utf-8")
        rows = ROWS + human_labels([load_human_export(path, self.records, self.sha)])
        report = self.compare(demo=True, rows=rows)
        metrics = report["candidate"]["label_metrics"]
        self.assertEqual(metrics["team_human"]["cells"], 2)
        self.assertEqual(metrics["proposed_unreviewed"]["cells"], 10)

    def test_saved_artifacts_load_in_both_engine_formats(self):
        rejected = load_artifact(self.dirs["baseline"] / "qa-en-late-intro.json")
        accepted = load_artifact(self.dirs["candidate"] / "qa-en-late-intro.json")
        self.assertEqual((rejected["kind"], rejected["recorded_total"]), ("rejected", None))
        self.assertEqual(accepted["kind"], "accepted")
        self.assertIsNotNone(accepted["recorded_total"])

    def test_capture_and_report_never_touch_sources(self):
        before = hashlib.sha256(SHARED.read_bytes()).hexdigest(), hashlib.sha256(DEFAULT_SCENARIOS.read_bytes()).hexdigest()
        cli.cmd_capture(argparse.Namespace(fixture=DEMO / "baseline.json", out=Path(self.tmp.name) / "again",
                                           engine_commit="test", dataset=SHARED))
        self.assertEqual(before, (hashlib.sha256(SHARED.read_bytes()).hexdigest(),
                                  hashlib.sha256(DEFAULT_SCENARIOS.read_bytes()).hexdigest()))
        with self.assertRaises(SystemExit):  # never overwrites
            cli.cmd_capture(argparse.Namespace(fixture=DEMO / "baseline.json", out=Path(self.tmp.name) / "again",
                                               engine_commit="test", dataset=SHARED))


if __name__ == "__main__":
    unittest.main()
