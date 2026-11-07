"""Official results.json exporter/validator: dry runs and adversarial cases.

All inputs are the reviewed synthetic 60 chats or INVENTED records. No network.
"""

import contextlib
import copy
from decimal import Decimal
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from cqa.io import load_checklist
from cqa.loader import ROOT
from cqa.providers import MockProvider
from cqa_results import validate as V
from cqa_results.batch import run_batch, scan_attempts
from cqa_results.contract import CRITERIA, exact_score, round_half_up_2dp
from cqa_results.dryrun import (LEGACY_CHECKLIST, ScriptedProvider, envelope, prod10_dryrun_dataset,
                                run_dryrun, simulated_control_record, write_json)
from cqa_results.export import ExportError, build_submission, serialize, write_submission

OUTPUTS = ROOT / "outputs"


def appendix_example():
    """Structure of the organizer appendix page 2 example (demo-001), transcribed."""
    rows = [("contact", True, [4]), ("discovery", None, [1]), ("identification", None, [1]),
            ("consultation", 15, [5, 6]), ("empathy", True, [4, 5]), ("dialogue", 7, [5, 6]),
            ("closure", True, [8]), ("critical", False, [4, 5, 6, 8])]
    return {"schema_version": "1.0", "team_name": "Example Team", "model": {"mode": "local", "name": "example-model"},
            "results": [{"conversation_id": "demo-001", "status": "ok",
                         "criteria": [{"criterion_id": c, "value": v, "rationale": "Пример.", "evidence_turns": t}
                                      for c, v, t in rows],
                         "score": {"final_score": 85.38, "critical_flag": False}}]}


def roundtrip(value):
    return V.strict_load(json.dumps(value, ensure_ascii=False).encode("utf-8"))


class ContractTests(unittest.TestCase):
    def test_appendix_example_score_reproduces_85_38(self):
        values = {c["criterion_id"]: c["value"] for c in appendix_example()["results"][0]["criteria"]}
        self.assertEqual(round_half_up_2dp(exact_score(values)), Decimal("85.38"))

    def test_appendix_example_validates_with_relaxed_count(self):
        index = [("demo-001", 8)]
        report = V.validate_submission(roundtrip(appendix_example()), index, "prod")
        self.assertEqual([e for e in report["errors"] if "exactly 10" not in e and "requires 10" not in e], [])

    def test_mapping_table_matches_appendix_weights_and_order(self):
        self.assertEqual([(c[0], c[1], c[3]) for c in CRITERIA], [
            ("contact", "01", 10), ("discovery", "02", 15), ("identification", "03", 20),
            ("consultation", "04", 20), ("empathy", "05", 15), ("dialogue", "06", 15),
            ("closure", "07", 5), ("critical", "08", 0)])
        checklist = load_checklist(LEGACY_CHECKLIST)
        self.assertEqual([(c.criterion_id, c.weight) for c in checklist.criteria], [(c[1], c[3]) for c in CRITERIA])

    def test_half_up_rounding_is_exact(self):
        from fractions import Fraction
        self.assertEqual(round_half_up_2dp(Fraction(2, 8)), Decimal("0.25"))
        self.assertEqual(round_half_up_2dp(Fraction(1, 200)), Decimal("0.01"))
        self.assertEqual(round_half_up_2dp(Fraction(1, 201)), Decimal("0.00"))


class DryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUTPUTS.mkdir(exist_ok=True)
        cls.tmp = Path(tempfile.mkdtemp(dir=OUTPUTS, prefix="test-results-"))
        cls.summary = run_dryrun(cls.tmp / "dry", log=lambda *_: None)
        cls.dev = json.loads((cls.tmp / "dry/dev/results.json").read_text("utf-8"))
        cls.prod = json.loads((cls.tmp / "dry/prod/results.json").read_text("utf-8"))
        cls.dev_data = json.loads((cls.tmp / "dry/dev/dataset.json").read_text("utf-8"))["data"]["records"]
        cls.prod_data = json.loads((cls.tmp / "dry/prod/dataset.json").read_text("utf-8"))["data"]["records"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def validate(self, value, set_name="prod", **kw):
        records = self.prod_data if set_name == "prod" else self.dev_data
        index = [(r["conversation_id"], len(r["transcript"])) for r in records]
        return V.validate_submission(roundtrip(value), index, set_name, **kw)

    def assertInvalid(self, value, fragment, set_name="prod"):
        report = self.validate(value, set_name)
        self.assertFalse(report["valid"])
        self.assertTrue(any(fragment in e for e in report["errors"]), report["errors"])

    # ---- full dry runs
    def test_dev65_dryrun_is_complete_valid_and_ordered(self):
        s = self.summary["dev"]
        self.assertTrue(s["valid"])
        self.assertEqual(len(self.dev["results"]), 65)
        self.assertEqual([r["conversation_id"] for r in self.dev["results"]],
                         [r["conversation_id"] for r in self.dev_data])
        self.assertEqual(sum(r["channel"] == "voice call" for r in self.dev_data), 5)
        self.assertTrue(all(r["conversation_id"].startswith("SYNTH-VOICE-")
                            for r in self.dev_data if r["channel"] == "voice call"))
        self.assertEqual((s["export"]["ok"], s["export"]["rejected"], s["export"]["error"]), (63, 1, 1))

    def test_prod10_dryrun_is_exactly_ten_with_errors_kept(self):
        self.assertTrue(self.summary["prod"]["valid"])
        self.assertEqual(len(self.prod["results"]), 10)
        errors = {r["conversation_id"]: r for r in self.prod["results"] if r["status"] == "error"}
        self.assertEqual(set(errors), {"SIM-PROD-004", "SIM-PROD-007"})
        for r in errors.values():
            self.assertEqual((r["criteria"], r["score"]), ([], None))
        self.assertIn("rejected by engine validation", errors["SIM-PROD-004"]["error"])
        self.assertIn("ProviderError", errors["SIM-PROD-007"]["error"])

    def test_model_metadata_is_the_actual_fixture(self):
        self.assertEqual(self.prod["model"], {"mode": "local", "name": "scripted-dryrun-fixture-v1"})
        self.assertEqual(self.prod["schema_version"], "1.0")

    def test_evidence_turns_map_to_original_one_based_indexes(self):
        checked = 0
        for results, data in ((self.dev, self.dev_data), (self.prod, self.prod_data)):
            source = {r["conversation_id"]: r["transcript"] for r in data}
            for r in results["results"]:
                if r["status"] != "ok":
                    continue
                transcript = source[r["conversation_id"]]
                first_operator = next((i + 1 for i, t in enumerate(transcript) if t["speaker"] == "operator"), None)
                for c in r["criteria"]:
                    positive = c["value"] is True or type(c["value"]) is int and c["value"] > 0
                    if positive and c["criterion_id"] != "critical":
                        self.assertEqual(c["evidence_turns"], [first_operator])
                        self.assertEqual(transcript[first_operator - 1]["speaker"], "operator")
                    else:  # Full-scope locator spans every original turn, bot/system included.
                        self.assertEqual(c["evidence_turns"], list(range(1, len(transcript) + 1)))
                    checked += 1
        self.assertGreater(checked, 500)

    def test_na_redistribution_and_critical_without_auto_zero(self):
        by_id = {r["conversation_id"]: r for r in self.dev["results"] + self.prod["results"]}
        scores = {r["score"]["final_score"] for r in by_id.values() if r["status"] == "ok"}
        self.assertIn(85.38, scores)   # appendix-like: two N/A criteria
        self.assertIn(88.75, scores)   # four N/A criteria
        critical = [r for r in by_id.values() if r["status"] == "ok" and r["score"]["critical_flag"]]
        self.assertTrue(critical)
        self.assertTrue(all(r["score"]["final_score"] == 41.0 for r in critical))
        self.assertTrue(all(r["criteria"][-1]["value"] is True for r in critical))

    # ---- validator adversarial cases
    def test_repeated_id(self):
        bad = copy.deepcopy(self.prod)
        bad["results"][1] = copy.deepcopy(bad["results"][0])
        self.assertInvalid(bad, "duplicate conversation IDs")

    def test_missing_record_and_wrong_count(self):
        bad = copy.deepcopy(self.prod)
        del bad["results"][3]
        self.assertInvalid(bad, "missing from results")
        self.assertInvalid(bad, "exactly 10 records")
        dev = copy.deepcopy(self.dev)
        dev["results"].pop()
        self.assertInvalid(dev, "exactly 65 records", "dev")

    def test_unknown_id_and_order(self):
        bad = copy.deepcopy(self.prod)
        bad["results"][0]["conversation_id"] = "SIM-PROD-999"
        self.assertInvalid(bad, "not a conversation ID in the source dataset")
        swapped = copy.deepcopy(self.prod)
        swapped["results"][0], swapped["results"][1] = swapped["results"][1], swapped["results"][0]
        self.assertInvalid(swapped, "original source dataset order")

    def ok(self):
        return copy.deepcopy(next(r for r in self.prod["results"] if r["conversation_id"] == "SIM-PROD-001"))

    def with_record(self, record):
        value = copy.deepcopy(self.prod)
        value["results"][0] = record
        return value

    def test_bad_indexes(self):
        length = len(self.prod_data[0]["transcript"])
        for turns, fragment in (([0], "outside original transcript"), ([length + 1], "outside original transcript"),
                                (["4"], "JSON integers"), ([True], "JSON integers"), ([], "nonempty array"),
                                ([4, 4], "duplicate indexes"), ([4.0], "JSON integers")):
            record = self.ok()
            record["criteria"][0]["evidence_turns"] = turns
            self.assertInvalid(self.with_record(record), fragment)

    def test_value_types_and_na(self):
        for cid, value, fragment in (("contact", None, "null (N/A) is not allowed"), ("contact", 1, "JSON boolean"),
                                     ("discovery", "N/A", "boolean or null"), ("consultation", 12, "one of"),
                                     ("consultation", True, "one of"), ("dialogue", None, "not allowed"),
                                     ("critical", None, "not allowed"), ("closure", 0, "boolean or null")):
            record = self.ok()
            next(c for c in record["criteria"] if c["criterion_id"] == cid)["value"] = value
            self.assertInvalid(self.with_record(record), fragment)

    def test_na_written_as_zero_breaks_score(self):
        record = self.ok()  # appendix-like: discovery is N/A; writing false must change the total.
        record["criteria"][1]["value"] = False
        self.assertInvalid(self.with_record(record), "official weighting")

    def test_criteria_set_and_order(self):
        record = self.ok()
        record["criteria"][0], record["criteria"][1] = record["criteria"][1], record["criteria"][0]
        self.assertInvalid(self.with_record(record), "exactly once in order")
        record = self.ok()
        record["criteria"].pop()
        self.assertInvalid(self.with_record(record), "exactly once in order")
        record = self.ok()
        record["criteria"][0]["criterion_id"] = "C01"
        self.assertInvalid(self.with_record(record), "unknown official criterion ID")

    def test_score_checks(self):
        for score, fragment in (({"final_score": 85.39, "critical_flag": False}, "official weighting"),
                                ({"final_score": 85.381, "critical_flag": False}, "two decimals"),
                                ({"final_score": "85.38", "critical_flag": False}, "JSON number"),
                                ({"final_score": 101, "critical_flag": False}, "between 0 and 100"),
                                ({"final_score": 85.38, "critical_flag": True}, "equal the critical"),
                                ({"final_score": 85.38}, "exactly final_score")):
            record = self.ok()
            record["score"] = score
            self.assertInvalid(self.with_record(record), fragment)

    def test_critical_violation_zeroed_score_is_rejected(self):
        value = copy.deepcopy(self.prod)
        record = next(r for r in value["results"] if r["score"] and r["score"]["critical_flag"])
        record["score"]["final_score"] = 0.0
        self.assertInvalid(value, "official weighting")

    def test_error_record_shape(self):
        for mutate, fragment in ((lambda r: r.update(score={"final_score": 0, "critical_flag": False}), "null for status"),
                                 (lambda r: r.update(criteria=self.ok()["criteria"]), "must be []"),
                                 (lambda r: r.update(error=" "), "actual reason"),
                                 (lambda r: r.pop("error"), "exactly"),
                                 (lambda r: r.update(status="failed"), '"ok" or "error"')):
            value = copy.deepcopy(self.prod)
            mutate(next(r for r in value["results"] if r["status"] == "error"))
            self.assertInvalid(value, fragment)

    def test_top_level_metadata(self):
        for mutate, fragment in ((lambda v: v.update(team_name="Название команды"), "team_name"),
                                 (lambda v: v.update(schema_version=1.0), "schema_version"),
                                 (lambda v: v.update(model={"mode": "cloud", "name": "x"}), "model.mode"),
                                 (lambda v: v.update(model={"mode": "local"}), "exactly \"mode\""),
                                 (lambda v: v.update(extra=1), "keys must be exactly")):
            value = copy.deepcopy(self.prod)
            mutate(value)
            self.assertInvalid(value, fragment)

    def test_submission_mode_rejects_dryrun_model_and_wrong_path(self):
        index = [(r["conversation_id"], len(r["transcript"])) for r in self.prod_data]
        report = V.validate_submission(roundtrip(self.prod), index, "prod", submission=True,
                                       output_path=self.tmp / "dry/prod/results.json")
        self.assertFalse(report["valid"])
        self.assertTrue(any("model.name" in e for e in report["errors"]))
        self.assertTrue(any("results/prod/results.json" in e for e in report["errors"]))

    def test_invalid_json_inputs(self):
        good = serialize(self.prod)
        cases = {"trailing comma": good.rstrip()[:-1] + b",}", "comment": b"// c\n" + good,
                 "nan": good.replace(b"85.38", b"NaN", 1), "bom": b"\xef\xbb\xbf" + good,
                 "invalid utf-8": good.replace(b'"DRY-RUN TEAM', b'"\xff\xfe TEAM', 1),
                 "duplicate key": good.replace(b'"schema_version": "1.0",', b'"schema_version": "1.0", "schema_version": "1.0",', 1)}
        for name, raw in cases.items():
            with self.subTest(name):
                path = self.tmp / ("bad-%s.json" % name.replace(" ", "-"))
                path.write_bytes(raw)
                report = V.validate_file(path, self.tmp / "dry/prod/dataset.json", "prod")
                self.assertFalse(report["valid"])
                self.assertTrue(report["errors"][0].startswith("$file"), report["errors"])

    def test_rationale_privacy_warning(self):
        record = self.ok()
        record["criteria"][0]["rationale"] = "Client gave number 7701 234 5678."
        report = self.validate(self.with_record(record))
        self.assertTrue(report["valid"])
        self.assertTrue(any("personal data" in w for w in report["warnings"]))

    def test_remote_verification_compares_bytes_offline(self):
        from cqa_results.verify_remote import verify
        local = self.tmp / "dry/prod/results.json"
        data = self.tmp / "dry/prod/dataset.json"
        same = verify("prod", local, data, local.read_bytes())
        self.assertTrue(same["identical"])
        self.assertFalse(same["ok"])  # Dry-run fixture model is never a valid submission.
        changed = verify("prod", local, data, local.read_bytes().replace(b"85.38", b"85.39", 1))
        self.assertFalse(changed["identical"])

    def test_validator_cli_exit_codes(self):
        data = str(self.tmp / "dry/prod/dataset.json")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(V.main([str(self.tmp / "dry/prod/results.json"), "--set", "prod", "--dataset", data]), 0)
            self.assertEqual(V.main([str(self.tmp / "dry/prod/results.json"), "--set", "dev", "--dataset", data]), 1)


class ExporterTests(unittest.TestCase):
    def setUp(self):
        OUTPUTS.mkdir(exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=OUTPUTS, prefix="test-export-"))
        self.data = write_json(self.tmp / "dataset.json", prod10_dryrun_dataset())
        self.checklist = load_checklist(LEGACY_CHECKLIST)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def batch(self, provider, name="run", **kw):
        return run_batch(self.data, self.tmp / name, provider, checklist=self.checklist, log=lambda *_: None, **kw)

    def test_all_error_export(self):
        ids = ["SIM-PROD-%03d" % n for n in range(1, 11)]
        self.batch(ScriptedProvider(fail_ids=ids))
        submission, report = build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        self.assertEqual(report["error"], 10)
        self.assertTrue(all(r["status"] == "error" and r["score"] is None for r in submission["results"]))
        self.assertEqual(submission["model"]["name"], "scripted-dryrun-fixture-v1")
        write_submission(submission, self.tmp / "out.json", self.data, "prod", allow_mock=True)

    def test_mock_outputs_refused_without_dry_run_flag(self):
        self.batch(ScriptedProvider())
        with self.assertRaisesRegex(ExportError, "not a genuine evaluation"):
            build_submission(self.data, self.tmp / "run", "Team", "prod")

    def test_engine_mock_provider_exports_as_local_mock_only(self):
        self.batch(MockProvider())
        submission, _ = build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        self.assertEqual(submission["model"], {"mode": "local", "name": "deterministic-fixture-v1"})
        self.assertTrue(all(r["status"] == "ok" for r in submission["results"]))

    def test_atomic_checklist_rejections_become_error_records(self):
        self.checklist = load_checklist(ROOT / "src/cqa/checklists/official-v4.json")
        counts = self.batch(MockProvider())
        self.assertEqual(counts["rejected"], 10)
        submission, _ = build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        self.assertTrue(all(r["status"] == "error" and r["criteria"] == [] and r["score"] is None
                            and "no score produced" in r["error"] for r in submission["results"]))

    def test_missing_outcome_refused_or_explicitly_marked(self):
        self.batch(ScriptedProvider(), only=["SIM-PROD-001", "SIM-PROD-002"])
        with self.assertRaisesRegex(ExportError, "No outcome for conversation #3"):
            build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        submission, report = build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True,
                                              unattempted_reason="Not evaluated before code stop")
        self.assertEqual(report["unattempted"], 8)
        self.assertEqual(submission["results"][5]["error"], "Not evaluated before code stop")

    def test_resume_uses_latest_attempt(self):
        self.batch(ScriptedProvider(fail_ids={"SIM-PROD-002"}))
        counts = self.batch(ScriptedProvider(), resume=True)
        self.assertEqual((counts["attempted"], counts["skipped"]), (1, 9))
        submission, report = build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        self.assertEqual(report["attempts"], 11)
        self.assertEqual(submission["results"][1]["status"], "ok")

    def test_resume_refuses_changed_configuration_and_reuse(self):
        self.batch(ScriptedProvider())
        with self.assertRaisesRegex(ValueError, "already used"):
            self.batch(ScriptedProvider())
        with self.assertRaisesRegex(ValueError, "Resume refused"):
            self.batch(MockProvider(), resume=True)

    def test_run_dir_must_stay_under_outputs(self):
        with self.assertRaisesRegex(ValueError, "outputs/"):
            run_batch(self.data, ROOT / "results" / "prod-run", ScriptedProvider(), checklist=self.checklist)

    def test_dataset_mismatch_refused(self):
        self.batch(ScriptedProvider())
        other = prod10_dryrun_dataset()
        other["data"]["records"][0]["transcript"][0]["text"] += " (changed)"
        other_path = write_json(self.tmp / "other.json", other)
        with self.assertRaisesRegex(ExportError, "different dataset"):
            build_submission(other_path, self.tmp / "run", "Team", "prod", allow_mock=True)

    def tamper(self, fn):
        self.batch(ScriptedProvider())
        path = sorted((self.tmp / "run").glob("000-*.result.json"))[0]
        value = json.loads(path.read_text("utf-8"))
        fn(value)
        path.write_text(json.dumps(value, ensure_ascii=False), "utf-8")

    def test_tampered_score_refused(self):
        def fn(v):
            v["score"]["total_score"] = "99.99"
        self.tamper(fn)
        with self.assertRaisesRegex(ExportError, "deterministic rescoring"):
            build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)

    def test_result_for_other_content_refused(self):
        def fn(v):
            v["conversation"]["source_record_sha256"] = "0" * 64
        self.tamper(fn)
        with self.assertRaisesRegex(ExportError, "different source content"):
            build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)

    def test_malformed_result_refused(self):
        self.tamper(lambda v: v.pop("score"))
        with self.assertRaisesRegex(ExportError, "engine result contract"):
            build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)

    def test_unexpected_file_and_foreign_outcome_refused(self):
        self.batch(ScriptedProvider())
        (self.tmp / "run" / "notes.txt").write_text("x")
        with self.assertRaisesRegex(ValueError, "Unexpected file"):
            build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        (self.tmp / "run" / "notes.txt").unlink()
        source = sorted((self.tmp / "run").glob("000-*.result.json"))[0]
        shutil.copy(source, self.tmp / "run" / ("011-%s.a01.result.json" % ("a" * 12)))
        with self.assertRaisesRegex(ExportError, "outside the dataset"):
            build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)

    def test_dryrun_export_never_written_to_results(self):
        self.batch(ScriptedProvider())
        submission, _ = build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        with self.assertRaisesRegex(ExportError, "never results/"):
            write_submission(submission, ROOT / "results/prod/results.json", self.data, "prod", allow_mock=True)
        target = self.tmp / "out.json"
        write_submission(submission, target, self.data, "prod", allow_mock=True)
        with self.assertRaisesRegex(ExportError, "Output exists"):
            write_submission(submission, target, self.data, "prod", allow_mock=True)
        self.assertFalse((ROOT / "results").exists())

    def test_invalid_submission_is_never_written(self):
        self.batch(ScriptedProvider())
        submission, _ = build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        submission["results"].pop()
        with self.assertRaisesRegex(ExportError, "failed validation"):
            write_submission(submission, self.tmp / "out.json", self.data, "prod", allow_mock=True)
        self.assertFalse((self.tmp / "out.json").exists())

    def test_bot_only_conversation_still_accounted_for(self):
        record = simulated_control_record(5)
        self.assertFalse(any(t["speaker"] == "operator" for t in record["transcript"]))
        self.batch(ScriptedProvider())
        submission, _ = build_submission(self.data, self.tmp / "run", "Team", "prod", allow_mock=True)
        self.assertEqual(submission["results"][4]["conversation_id"], "SIM-PROD-005")

    def test_offline_openai_batch_keeps_policy_gate_and_real_model_identity(self):
        from cqa.access import ExportPolicy, InputPolicy
        from cqa.loader import SHARED
        from cqa.providers import OpenAIProvider
        from cqa.schemas import EvaluationConfig
        from cqa_results.dryrun import synthetic_voice_record
        shared = json.loads(Path(SHARED).read_text("utf-8"))["data"]["records"][:2]
        data = write_json(self.tmp / "mixed.json", envelope(shared + [synthetic_voice_record(1)], "UNIT-MIXED"))
        sent = []

        class OfflineOpenAI(OpenAIProvider):
            def evaluate(self, conversation, checklist, request, config):
                raw = ScriptedProvider().evaluate(conversation, checklist, request, config).evaluation

                def transport(payload, timeout):
                    sent.append(conversation.conversation_id)
                    return {"id": "offline", "model": "offline-model-2026", "status": "completed", "usage": {},
                            "output": [{"type": "message", "content": [{"type": "output_text",
                                                                        "text": json.dumps(raw)}]}]}
                self._transport = transport
                return super().evaluate(conversation, checklist, request, config)

        provider = OfflineOpenAI("offline-model-2026", api_key="unit-test-placeholder",
                                 input_policy=ExportPolicy(InputPolicy(), allow_dev=True))
        counts = run_batch(data, self.tmp / "run", provider, checklist=self.checklist, log=lambda *_: None,
                           config=EvaluationConfig(external_synthetic_allowed=True))
        self.assertEqual((counts["result"], counts["error"]), (2, 1))
        self.assertEqual(sent, [r["conversation_id"] for r in shared])  # Voice stand-in never transmitted.
        submission, _ = build_submission(data, self.tmp / "run", "Team", "dev")
        self.assertEqual(submission["model"], {"mode": "external_api", "name": "offline-model-2026"})
        self.assertIn("AccessDenied", submission["results"][2]["error"])

    def test_owner_grants_bind_batch_normalized_content(self):
        from cqa.access import AccessDenied, InputPolicy
        from cqa.loader import normalize_record, read_dataset
        from cqa_results.grants import build_manifest
        manifest = build_manifest(self.data, "organizer_control", "test-only reference",
                                  "2099-01-01T00:00:00Z", ["openai"])
        policy = InputPolicy(manifest, allow_external=True)
        data, file_hash = read_dataset(self.data)
        for record in data["records"]:
            receipt = policy.authorize(normalize_record(record, data["dataset_group_id"], file_hash), "openai")
            self.assertEqual(receipt.permission, "external_openai")
        changed = dict(data["records"][0], transcript=data["records"][0]["transcript"][:-1])
        with self.assertRaises(AccessDenied):
            policy.authorize(normalize_record(changed, data["dataset_group_id"], file_hash), "openai")

    def test_attempt_files_are_scanned_strictly(self):
        self.batch(ScriptedProvider())
        self.assertEqual(len(scan_attempts(self.tmp / "run")), 10)


if __name__ == "__main__":
    unittest.main()
