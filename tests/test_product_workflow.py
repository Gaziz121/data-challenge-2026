"""Result history, appeals/reviewer recalculation, replay, checklist v6 and PROD intake. Offline only."""

from contextlib import redirect_stdout
from copy import deepcopy
import http.client
import http.server
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

from cqa.engine import evaluate
from cqa.io import load_checklist
from cqa.loader import ROOT, SHARED, load_conversation
from cqa.providers import MockProvider
from cqa.schemas import EvaluationConfig
from cqa.scoring import score_evaluation, score_responses
from cqa.web import Application, create_server
from cqa_results import envelope
from cqa_results.batch import main as batch_main
from cqa_results.export import check_checklist
from tests.test_control_backend import grant, supplied

CHECKLISTS = ROOT / "src/cqa/checklists"
V5 = {"checklist_id": "freedom-cqa-initial", "version": "2026-11-07.v5"}
V6 = {"checklist_id": "freedom-cqa-initial", "version": "2026-11-07.v6"}
KEY = "offline-test-reviewer-key"


class ServerCase(unittest.TestCase):
    manifest_values = ()

    def setUp(self):
        (ROOT / "outputs").mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=ROOT / "outputs")
        manifest = Path(self.folder.name) / "approvals.json"
        manifest.write_text(json.dumps({"schema_version": "1.0", "grants": [grant(v) for v in self.manifest_values]}))
        self.app = Application(api_key="", output_dir=Path(self.folder.name) / "app", live_call_limit=0,
                               authorization_manifest=manifest, atomic_prompt_version="atomic-v5", reviewer_key=KEY)
        with redirect_stdout(io.StringIO()):
            self.server = create_server(0, self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.folder.cleanup()

    def request(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=20)
        h = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.server.server_port}"}
        h.update(headers or {})
        conn.request("GET" if body is None else "POST", path,
                     json.dumps(body, ensure_ascii=False).encode() if body is not None else None, headers=h)
        r = conn.getresponse()
        status, raw = r.status, r.read()
        conn.close()
        return status, json.loads(raw)

    def replay(self):
        status, body = self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "provider": "replay",
                                                         "checklist": V5})
        self.assertEqual(status, 200, body)
        return body


class AppealWorkflowTests(ServerCase):
    manifest_values = (supplied("KZ"),)

    def test_replay_is_labelled_and_bound_to_recorded_checklist(self):
        result = self.replay()
        self.assertEqual(result["run"]["provider"], "replay")
        self.assertTrue(result["run"]["is_mock"])  # Never exportable as a fresh genuine evaluation.
        self.assertEqual(result["run"]["model_returned"], "gpt-5.4-mini-2026-03-17")
        self.assertEqual(result["run"]["configuration"]["prompt_version"], "atomic-v5")
        self.assertEqual(result["score"]["total_score"], "100.00")
        status, body = self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "provider": "replay",
                                                         "checklist": V6})
        self.assertEqual(status, 422)
        self.assertIn("No recorded genuine reply", body["error"])
        status, _ = self.request("/api/evaluations", {"conversation_id": "p1-ru-002", "provider": "replay",
                                                      "checklist": V5})
        self.assertEqual(status, 422)

    def test_history_lists_results_and_rejections_and_reads_back(self):
        accepted = self.replay()
        status, rejected = self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "checklist": V6})
        self.assertEqual(status, 422)  # Atomic mock facts are unknown: an honest rejection, no score.
        self.assertEqual(self.app.list_evaluations("p1-ru-002"), [])
        status, rows = self.request("/api/evaluations?conversation_id=p1-ru-001")
        self.assertEqual(status, 200)
        kinds = {r["evaluation_id"]: r for r in rows}
        self.assertEqual(kinds[accepted["evaluation_id"]]["total_score"], "100.00")
        self.assertEqual(kinds[rejected["diagnostic_id"]]["kind"], "rejected")
        self.assertIsNone(kinds[rejected["diagnostic_id"]]["total_score"])
        status, again = self.request("/api/evaluations/" + accepted["evaluation_id"])
        self.assertEqual((status, again), (200, accepted))
        self.assertEqual(self.request("/api/evaluations/00000000-0000-0000-0000-000000000000")[0], 404)
        self.assertEqual(self.request("/api/evaluations/not-an-id")[0], 404)

    def test_appeal_review_recalculates_without_touching_original(self):
        result = self.replay()
        path = Path(self.folder.name) / "app" / (result["evaluation_id"] + ".json")
        before = path.read_bytes()
        base = "/api/evaluations/%s/appeals" % result["evaluation_id"]
        status, submitted = self.request(base, {"criterion_id": "07", "submitted_by": "Operator A",
                                                "explanation": "Farewell only; no summary or offer of help.",
                                                "requested_response": "no"})
        self.assertEqual(status, 201, submitted)
        appeal = submitted["appeal"]
        self.assertEqual((appeal["state"], appeal["original_response"]), ("open", "yes"))
        self.assertIsNone(submitted["view"]["revised_score"])
        dup = self.request(base, {"criterion_id": "07", "submitted_by": "X", "explanation": "again"})
        self.assertEqual(dup[0], 409)
        self.assertEqual(self.request(base, {"criterion_id": "99", "submitted_by": "X", "explanation": "e"})[0], 422)
        self.assertEqual(self.request(base, {"criterion_id": "07", "submitted_by": "X", "explanation": "e",
                                             "requested_response": 5})[0], 422)
        decision = "/api/appeals/%s/decision" % appeal["appeal_id"]
        body = {"reviewer": "Reviewer B", "outcome": "change", "new_response": "no",
                "reason": "Official text requires a summary or offer of help; farewell alone is not enough."}
        self.assertEqual(self.request(decision, body)[0], 403)
        self.assertEqual(self.request(decision, body, {"X-CQA-Reviewer-Key": "wrong"})[0], 403)
        same = dict(body, reviewer="operator a")
        self.assertEqual(self.request(decision, same, {"X-CQA-Reviewer-Key": KEY})[0], 422)
        status, _ = self.request(decision, dict(body, new_response=7), {"X-CQA-Reviewer-Key": KEY})
        self.assertEqual(status, 422)  # 7 is outside a binary scale.
        status, decided = self.request(decision, body, {"X-CQA-Reviewer-Key": KEY})
        self.assertEqual(status, 200, decided)
        view = decided["view"]
        self.assertEqual(view["original_score"]["total_score"], "100.00")
        self.assertEqual(view["revised_score"]["total_score"], "92.31")
        self.assertEqual(view["applied"][0]["from"], "yes")
        self.assertEqual(decided["appeal"]["decision"]["final_response"], "no")
        self.assertEqual([e["event"] for e in decided["appeal"]["history"]], ["submitted", "decided"])
        self.assertEqual(self.request(decision, body, {"X-CQA-Reviewer-Key": KEY})[0], 409)
        self.assertEqual(path.read_bytes(), before)  # The stored evaluation is immutable.
        status, view = self.request(base)
        self.assertEqual((status, view["revised_score"]["total_score"]), (200, "92.31"))
        rows = self.request("/api/evaluations?conversation_id=p1-ru-001")[1]
        self.assertEqual(rows[0]["appeals_revised"], 1)

    def test_confirm_keeps_score_and_n_a_change_redistributes(self):
        result = self.replay()
        base = "/api/evaluations/%s/appeals" % result["evaluation_id"]
        appeal = self.request(base, {"criterion_id": "04", "submitted_by": "Operator A", "explanation": "x"})[1]["appeal"]
        status, out = self.request("/api/appeals/%s/decision" % appeal["appeal_id"],
                                   {"reviewer": "Reviewer B", "outcome": "confirm", "reason": "Correct."},
                                   {"X-CQA-Reviewer-Key": KEY})
        self.assertEqual((status, out["appeal"]["state"], out["view"]["revised_score"]), (200, "upheld", None))
        appeal = self.request(base, {"criterion_id": "07", "submitted_by": "Operator A", "explanation": "x"})[1]["appeal"]
        status, out = self.request("/api/appeals/%s/decision" % appeal["appeal_id"],
                                   {"reviewer": "Reviewer B", "outcome": "change", "new_response": "N/A",
                                    "reason": "Chat broke off."}, {"X-CQA-Reviewer-Key": KEY})
        self.assertEqual(status, 200, out)
        revised = out["view"]["revised_score"]
        self.assertEqual((revised["total_score"], revised["applicable_weight"]), ("100.00", 60))

    def test_supplied_input_history_requires_current_authorization(self):
        status, result = self.request("/api/evaluations", {"conversation": supplied("KZ")})
        self.assertEqual(status, 200, result)
        self.assertEqual(len(self.app.list_evaluations("unseen-KZ")), 1)
        stranger = Application(api_key="", output_dir=self.app.output_dir, reviewer_key=KEY)
        self.assertEqual(stranger.list_evaluations("unseen-KZ"), [])
        with self.assertRaises(LookupError):
            stranger.load_result(result["evaluation_id"])


class ScoringAndChecklistTests(unittest.TestCase):
    def test_shared_arithmetic_matches_engine_and_rejects_off_scale(self):
        conv, checklist = load_conversation(SHARED, "p1-en-011"), load_checklist()
        result = evaluate(conv, checklist, MockProvider(), EvaluationConfig())
        responses = {d.criterion_id: d.response for d in result.model_evaluation.decisions}
        self.assertEqual(score_responses(responses, checklist), result.score)
        self.assertEqual(score_evaluation(result.model_evaluation, conv, checklist), result.score)
        for bad in ({**responses, "04": 3}, {**responses, "01": True}, {**responses, "05": "N/A"},
                    {k: v for k, v in responses.items() if k != "01"}):
            with self.assertRaises(ValueError):
                score_responses(bad, checklist)

    def test_v6_changes_only_c07_wording(self):
        v5 = json.loads((CHECKLISTS / "official-v5.json").read_text())
        v6 = json.loads((CHECKLISTS / "official-v6.json").read_text())
        self.assertEqual(v6["version"], "2026-11-07.v6")
        for a, b in zip(v5["criteria"], v6["criteria"]):
            if a["criterion_id"] != "07":
                self.assertEqual(a, b)
                continue
            strip = lambda c: {**c, "instructions": None,
                               "questions": [{**q, "question": None} for q in c["questions"]]}
            self.assertEqual(strip(a), strip(b))  # Weight, kind, levels, N/A rule and question IDs unchanged.
            self.assertIn("never a summary or offer", b["instructions"])
        check_checklist(load_checklist(CHECKLISTS / "official-v6.json"))

    def test_real_batch_requires_explicit_checklist_and_prompt(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as folder, redirect_stdout(io.StringIO()):
            import contextlib
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = batch_main(["--data", str(SHARED), "--run-dir", folder + "/run", "--provider", "openai",
                                   "--model", "any-model"])
            self.assertEqual(code, 1)
            self.assertIn("--checklist and --prompt-version", err.getvalue())
            self.assertFalse(Path(folder, "run").exists())


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(Path(SHARED).read_text())

    def test_dev_envelope_passes_and_report_has_no_text(self):
        report = envelope.inspect(self.value, expect_count=60)
        self.assertTrue(report["ok"], report["problems"])
        text = json.dumps(report, ensure_ascii=False)
        first = self.value["data"]["records"][0]["transcript"][0]["text"]
        self.assertNotIn(first, text)

    def test_bounded_wrapping_and_fail_closed_problems(self):
        records = deepcopy(self.value["data"]["records"][:10])
        wrapped = envelope.wrap(records, "PROD_CONTROL")
        self.assertEqual(wrapped["data"]["records"], records)
        self.assertTrue(envelope.inspect(wrapped, expect_count=10)["ok"])
        self.assertTrue(envelope.inspect({"records": records}, expect_count=10)["problems"])
        with self.assertRaises(ValueError):
            envelope.wrap(records, None)
        with self.assertRaises(ValueError):
            envelope.wrap({"items": records}, "X")
        odd = deepcopy(wrapped)
        odd["data"]["records"][1]["conversation_id"] = odd["data"]["records"][0]["conversation_id"]
        odd["data"]["records"][2]["transcript"][0]["speaker"] = "agent"
        odd["data"]["records"][3]["transcript"][0]["sentiment"] = "x"
        problems = " ".join(envelope.inspect(odd, expect_count=11)["problems"])
        for expected in ("duplicate", "unknown speakers", "unknown fields", "expected 11"):
            self.assertIn(expected, problems)

    def test_fetch_saves_exact_bytes_once(self):
        payload = json.dumps(envelope.wrap(self.value["data"]["records"][:2], "G")).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as folder:
                target = Path(folder) / "control.json"
                info = envelope.fetch("http://127.0.0.1:%d/x" % server.server_port, target, "X-Test: 1")
                self.assertEqual((target.read_bytes(), info["bytes"]), (payload, len(payload)))
                with self.assertRaises(FileExistsError):
                    envelope.fetch("http://127.0.0.1:%d/x" % server.server_port, target)
        finally:
            server.shutdown()
            server.server_close()


class RehearsalTests(unittest.TestCase):
    def test_full_offline_prod_rehearsal(self):
        from cqa_results.rehearsal import run_rehearsal
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as folder:
            summary = run_rehearsal(Path(folder) / "r", log=lambda *_: None)
        self.assertTrue(summary["ok"], json.dumps(summary["steps"], ensure_ascii=False))
        self.assertEqual(summary["steps"]["5_validation"]["summary"]["records"], 10)
        self.assertTrue(summary["steps"]["6_commit_preparation"]["official files untouched"])


if __name__ == "__main__":
    unittest.main()


class BatchRepairTests(unittest.TestCase):
    """Opt-in bounded repair in the batch runner, replaying the genuine atomic-v4 duplicate reply."""

    def test_repair_is_opt_in_recorded_and_bounded(self):
        from cqa_results.batch import run_batch
        from cqa.schemas import RepairPolicy
        from tests.test_checklist_v5 import FIXTURES, V4CONFIG, decision, v5
        from tests.test_schema_reliability import CountingRepairProvider
        raw = json.loads((FIXTURES / "live_atomic_v4_2fcd958.json").read_text())["original_model_output"]
        fixed = deepcopy(decision(raw, "04"))
        fixed["atomic_checks"] = fixed["atomic_checks"][:4]
        value = json.loads(Path(SHARED).read_text())
        value["data"]["records"] = [r for r in value["data"]["records"] if r["conversation_id"] == "p1-ru-001"]
        value["data"]["total_records"] = 1
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as folder:
            data = Path(folder) / "one.json"
            data.write_text(json.dumps(value, ensure_ascii=False))
            plain = CountingRepairProvider(raw, {"schema_version": "1.2", "criteria": [fixed]})
            counts = run_batch(data, Path(folder) / "plain", plain, checklist=v5(), config=V4CONFIG, log=lambda *_: None)
            self.assertEqual((counts["rejected"], plain.repair_calls), (1, 0))
            provider = CountingRepairProvider(raw, {"schema_version": "1.2", "criteria": [fixed]})
            policy = RepairPolicy(authorization="offline unit test; no paid call")
            counts = run_batch(data, Path(folder) / "repair", provider, checklist=v5(), config=V4CONFIG,
                               log=lambda *_: None, repair=policy)
            self.assertEqual((counts["result"], provider.repair_calls), (1, 1))
            manifest = json.loads((Path(folder) / "repair/run.json").read_text())
            self.assertEqual(manifest["repair"]["authorization"], "offline unit test; no paid call")
            saved = json.loads(next((Path(folder) / "repair").glob("*.result.json")).read_text())
            self.assertEqual(saved["repair_attempts"][0]["status"], "merged")
            self.assertEqual(saved["status"], "mock_only")
            with self.assertRaises(ValueError):  # Resume cannot silently add or drop repair.
                run_batch(data, Path(folder) / "plain", plain, checklist=v5(), config=V4CONFIG, resume=True,
                          log=lambda *_: None, repair=policy)
