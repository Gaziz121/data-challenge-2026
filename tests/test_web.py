"""Real loopback HTTP tests. OpenAI transport is injected; no live API calls."""

from contextlib import redirect_stdout
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

from cqa.io import load_checklist
from cqa.loader import ROOT, SHARED, read_dataset
from cqa.providers import MockProvider, OpenAIProvider, ProviderReply
from cqa.schemas import EvaluationResult
from cqa.scoring import score_evaluation
from cqa.web import Application, create_server, load_env_file


class WebTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "outputs").mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=ROOT / "outputs")
        self.app = Application(api_key="", output_dir=Path(self.folder.name) / "app")
        with redirect_stdout(io.StringIO()):
            self.server = create_server(0, self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port
        self.origin = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.folder.cleanup()

    def request(self, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        request_headers = {"Origin": self.origin, "Content-Type": "application/json"}
        request_headers.update(headers or {})
        connection.request("POST" if body is not None else "GET", path,
                           body=json.dumps(body) if body is not None else None, headers=request_headers)
        response = connection.getresponse()
        status, mime, raw = response.status, response.getheader("Content-Type"), response.read()
        connection.close()
        return status, json.loads(raw) if "application/json" in mime else raw.decode()

    def test_startup_assets_and_independent_human_page(self):
        status, html = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn('href="/human-review/" target="_blank" rel="noopener noreferrer"', html)
        self.assertIn("MOCK mode", html)
        for path in ("/app.js", "/app.css", "/transcript.js"):
            self.assertEqual(self.request(path)[0], 200)
        status, human = self.request("/human-review/")
        self.assertEqual(status, 200)
        self.assertIn('"team_human"', human)
        self.assertIn("CqaTranscript", human)
        self.assertNotIn("/api/evaluations", human)
        self.assertNotIn("cqa.engine", human)

    def test_metadata_and_config_never_expose_key_or_full_raw_data(self):
        self.app.api_key = "private-test-value"
        status, config = self.request("/api/config")
        self.assertEqual(status, 200)
        self.assertTrue(config["openai_key_present"])
        self.assertNotIn("private-test-value", json.dumps(config))
        self.assertEqual(config["default_provider"], "mock")
        status, records = self.request("/api/conversations")
        self.assertEqual(status, 200)
        self.assertEqual(len(records), 60)
        self.assertEqual({r["language"] for r in records}, {"RU", "KZ", "EN"})
        self.assertTrue(all(set(r) == {"conversation_id", "language", "channel"} for r in records))

    def test_ru_kz_en_transcripts_and_mock_endpoint(self):
        data, _ = read_dataset(SHARED)
        for language in ("RU", "KZ", "EN"):
            original = next(r for r in data["records"] if r["language"] == language)
            cid = original["conversation_id"]
            status, conversation = self.request("/api/conversations/" + cid)
            self.assertEqual(status, 200)
            self.assertEqual([m["text"] for m in conversation["messages"]], [m["text"] for m in original["transcript"]])
            self.assertEqual([m["source_speaker"] for m in conversation["messages"]], [m["speaker"] for m in original["transcript"]])
            status, result = self.request("/api/evaluations", {"conversation_id": cid, "provider": "mock"})
            self.assertEqual(status, 200)
            saved = EvaluationResult.model_validate_json(json.dumps(result))
            self.assertTrue(saved.run.is_mock)
            self.assertEqual(saved.status, "mock_only")
            self.assertEqual(len(saved.model_evaluation.decisions), 8)
            self.assertEqual(saved.score, score_evaluation(saved.model_evaluation, saved.conversation, saved.checklist))
            self.assertEqual(len(list(self.app.output_dir.glob("*.json"))), ("RU", "KZ", "EN").index(language) + 1)
            for decision in saved.model_evaluation.decisions:
                for evidence in decision.evidence:
                    ids = {m.message_id for m in saved.conversation.messages}
                    self.assertIn(evidence.start_message_id, ids)
                    self.assertIn(evidence.end_message_id, ids)

    def test_unconfigured_real_provider_fails_without_fallback_or_call(self):
        self.app.provider_factory = lambda *args: self.fail("Must reject before provider construction")
        for allow in (False, True):
            self.app.allow_external = allow
            status, error = self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "provider": "openai", "model": "test-model"})
            self.assertEqual(status, 422)
            self.assertIn("error", error)
            self.assertFalse(self.app.output_dir.exists())

    def test_switch_to_real_adapter_with_offline_transport_and_na(self):
        # This is an HTTP integration fixture, not a live LLM evaluation or a DEV label.
        self.app.api_key, self.app.allow_external = "unit-test-placeholder", True
        calls = []
        def factory(name, selected_model):
            calls.append((name, selected_model))
            if name == "mock":
                return MockProvider()
            def transport(payload, timeout):
                context = json.loads(payload["input"])
                from cqa.schemas import Conversation, Checklist, EvaluationConfig
                conversation = Conversation.model_validate(context["conversation"])
                checklist = Checklist.model_validate(context["checklist"])
                raw = MockProvider().evaluate(conversation, checklist, {}, EvaluationConfig()).evaluation
                decision = raw["decisions"][1]
                decision.update(response="N/A", na_reason="HTTP test fixture: applicability assertion only.")
                decision["atomic_checks"][0]["answer"] = "yes"
                return {"id": "offline-transport-only", "status": "completed", "model": selected_model,
                        "output": [{"content": [{"type": "output_text", "text": json.dumps(raw)}]}]}
            return OpenAIProvider(selected_model, api_key=self.app.api_key, transport=transport)
        self.app.provider_factory = factory
        self.assertEqual(self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "provider": "mock"})[0], 200)
        status, result = self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "provider": "openai", "model": "offline-model-v2"})
        self.assertEqual(status, 200)
        self.assertEqual(result["run"]["model_returned"], "offline-model-v2")
        self.assertEqual(result["run"]["response_id"], "offline-transport-only")
        self.assertEqual(result["model_evaluation"]["decisions"][1]["response"], "N/A")
        self.assertEqual(result["score"]["applicable_weight"], 85)
        self.assertEqual(calls, [("mock", ""), ("openai", "offline-model-v2")])

    def test_invalid_model_output_retained_without_scored_result(self):
        class BadMaker(MockProvider):
            def evaluate(self, *args):
                return ProviderReply({"schema_version": "1.0", "decisions": []}, model="invalid-fixture")
        self.app.provider_factory = lambda *args: BadMaker()
        status, error = self.request("/api/evaluations", {"conversation_id": "p1-ru-001"})
        self.assertEqual(status, 422)
        self.assertNotIn("score", error)
        self.assertIn("diagnostic_id", error)
        diagnostics = list(self.app.output_dir.glob("rejected-*.json"))
        self.assertEqual(len(diagnostics), 1)
        saved = json.loads(diagnostics[0].read_text())
        self.assertEqual(saved["original_model_output"]["decisions"], [])
        self.assertNotIn("score", saved)
        status, retrieved = self.request("/api/diagnostics/" + error["diagnostic_id"])
        self.assertEqual(status, 200)
        self.assertEqual(retrieved["original_model_output"], saved["original_model_output"])
        self.assertNotIn("score", retrieved)
        self.assertEqual(self.request("/api/diagnostics/../../.env")[0], 404)

    def test_unknown_ids_bad_requests_and_no_private_file_serving(self):
        for path in ("/api/conversations/no-such-id", "/data/raw/DEV_conversations.json", "/.env.local", "/outputs/app/test.json", "/../STATUS.md"):
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/api/evaluations", {"conversation_id": "missing"})[0], 404)
        self.assertEqual(self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "total_score": 100})[0], 422)
        self.assertEqual(self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "provider": "other"})[0], 422)
        self.assertEqual(self.request("/api/evaluations", {"conversation_id": "p1-ru-001"}, {"Content-Type": "text/plain"})[0], 415)

    def test_cross_origin_and_rebinding_host_rejected(self):
        self.assertEqual(self.request("/api/config", headers={"Host": "untrusted.example"})[0], 403)
        self.assertEqual(self.request("/api/evaluations", {"conversation_id": "p1-ru-001"}, {"Origin": "https://untrusted.example"})[0], 403)

    def test_busy_evaluation_is_explicit_conflict(self):
        self.app.lock.acquire()
        try:
            self.assertEqual(self.request("/api/evaluations", {"conversation_id": "p1-ru-001"})[0], 409)
        finally:
            self.app.lock.release()

    def test_live_call_cap_blocks_second_attempt_before_provider(self):
        self.app.api_key, self.app.allow_external, self.app.live_call_limit = "unit-test-placeholder", True, 1
        calls = []
        def fixture(name, model):
            calls.append(name)
            return MockProvider()  # No network: test only the admission counter.
        self.app.provider_factory = fixture
        body = {"conversation_id": "p1-ru-001", "provider": "openai", "model": "offline-model"}
        self.assertEqual(self.request("/api/evaluations", body)[0], 200)
        status, error = self.request("/api/evaluations", body)
        self.assertEqual(status, 422)
        self.assertIn("limit reached", error["error"])
        self.assertEqual(calls, ["openai"])
        self.assertEqual(self.app.live_calls, 1)

    def test_env_file_reads_supported_values_without_expanding_shell(self):
        path = Path(self.folder.name) / ".env.local"
        path.write_text('# local\nOPENAI_API_KEY="unit-test-placeholder"\nCQA_MODEL=chosen-model\nOTHER=$(do-not-execute)\n')
        self.assertEqual(load_env_file(path), {"OPENAI_API_KEY": "unit-test-placeholder", "CQA_MODEL": "chosen-model"})


if __name__ == "__main__":
    unittest.main()
