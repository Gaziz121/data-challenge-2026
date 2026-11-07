"""A call-recording link never leaves the client-side record. Fictional URL and transcript; offline only.

The UI may render a plain "Open recording" link from an https audio_url that the user already has (a pasted
voice record). This test pins the backend side of that design: the URL is not sent to the evaluation provider,
not stored in results or appeals, not listed in history, not exported, and the DEV conversation route (which
serves synthetic chats only) does not add one.
"""

from contextlib import redirect_stdout
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

from cqa.access import ConversationInput, conversation_fingerprint
from cqa.loader import ROOT
from cqa.providers import MockProvider
from cqa.schemas import EvaluationResult
from cqa.web import Application, create_server
from cqa_results.export import ok_record

FAKE_URL = "https://example.invalid/rec"


def voice_record():
    return {"dataset_group_id": "INTERNAL_OFFLINE_TEST",
            "record": {"conversation_id": "fictional-voice-audio", "channel": "voice call", "language": "RU",
                       "audio_url": FAKE_URL,
                       "transcript": [
                           {"message_id": "v1", "speaker": "client", "timestamp": "2026-11-08T10:00:00+05:00",
                            "text": "Где посмотреть тариф?"},
                           {"message_id": "v2", "speaker": "operator", "timestamp": "2026-11-08T10:00:05+05:00",
                            "text": "Здравствуйте, я Сэм. Тариф указан в разделе Помощь. До свидания."}]}}


class CapturingMock(MockProvider):
    """The real mock fixture, recording exactly what the engine hands to a provider."""
    def __init__(self, seen):
        self.seen = seen

    def evaluate(self, conversation, checklist, request, config):
        self.seen.append(json.dumps([conversation.model_dump(mode="json"), request], default=str, ensure_ascii=False))
        return super().evaluate(conversation, checklist, request, config)


class AudioUrlIsolationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "outputs").mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=ROOT / "outputs")
        self.value = voice_record()
        manifest = Path(self.folder.name) / "approvals.json"
        manifest.write_text(json.dumps({"schema_version": "1.0", "grants": [{
            "conversation_sha256": conversation_fingerprint(ConversationInput.model_validate(self.value).normalize()),
            "data_class": "organizer_control", "authorization_reference": "offline-test-owner-approval",
            "external_providers": [], "expires_at": "2100-01-01T00:00:00Z"}]}))
        self.seen = []
        self.app = Application(api_key="", authorization_manifest=manifest, output_dir=Path(self.folder.name) / "app",
                               live_call_limit=0, provider_factory=lambda name, model: CapturingMock(self.seen))
        with redirect_stdout(io.StringIO()):
            self.server = create_server(0, self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.folder.cleanup()

    def request(self, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        headers = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.server.server_port}"}
        conn.request("GET" if body is None else "POST", path,
                     json.dumps(body, ensure_ascii=False).encode() if body is not None else None, headers=headers)
        response = conn.getresponse()
        status, raw = response.status, response.read().decode("utf-8")
        conn.close()
        return status, raw

    def test_audio_url_absent_from_provider_storage_history_and_export(self):
        status, raw = self.request("/api/evaluations", {"conversation": self.value, "provider": "mock",
                                                         "checklist": {"checklist_id": "freedom-cqa-initial",
                                                                       "version": "2026-11-07.v3"}})
        self.assertEqual(status, 200, raw)
        self.assertNotIn("example.invalid", raw)
        result = EvaluationResult.model_validate(json.loads(raw))
        self.assertEqual(result.conversation.channel, "voice")
        # Provider request: conversation and the full prompt payload handed to the provider.
        self.assertEqual(len(self.seen), 1)
        self.assertNotIn("example.invalid", self.seen[0])
        self.assertNotIn("audio_url", self.seen[0])
        # Stored files (result, appeals, anything else under this app's outputs).
        self.assertEqual(self.request(f"/api/evaluations/{result.evaluation_id}/appeals", {
            "criterion_id": "07", "explanation": "fixture", "submitted_by": "tester"})[0], 201)
        stored = [p for p in (Path(self.folder.name) / "app").rglob("*") if p.is_file()]
        self.assertTrue(stored)
        for path in stored:
            self.assertNotIn(b"example.invalid", path.read_bytes(), path.name)
        # History, saved result and appeals views.
        for path in ("/api/evaluations", f"/api/evaluations/{result.evaluation_id}",
                     f"/api/evaluations/{result.evaluation_id}/appeals"):
            status, raw = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertNotIn("example.invalid", raw, path)
        # Official export record built from the stored result and the original record.
        exported = ok_record(result, self.value["record"], self.value["dataset_group_id"],
                             result.conversation.dataset_sha256, allow_mock=True)
        self.assertNotIn("example.invalid", json.dumps(exported))
        self.assertNotIn("audio_url", json.dumps(exported))

    def test_dev_conversation_route_serves_synthetic_chats_without_audio_url(self):
        status, raw = self.request("/api/conversations/p1-ru-001")
        self.assertEqual(status, 200)
        body = json.loads(raw)
        self.assertEqual(body["channel"], "chat")
        self.assertNotIn("audio_url", body)


if __name__ == "__main__":
    unittest.main()
