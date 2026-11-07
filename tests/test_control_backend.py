"""Internal control contract tests. Fictional fixtures, offline transports only."""

from contextlib import redirect_stdout
from copy import deepcopy
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from cqa.access import (AccessDenied, AuthorizationManifest, ConversationInput,
                        InputPolicy, conversation_fingerprint)
from cqa.checklists import ChecklistConflict, ChecklistRegistry
from cqa.io import digest, load_checklist
from cqa.loader import ROOT, read_dataset
from cqa.prompt import build_request
from cqa.providers import MockProvider, OpenAIProvider, ProviderError, ProviderReply
from cqa.schemas import Checklist, EvaluationConfig, EvaluationResult
from cqa.scoring import score_evaluation
from cqa.web import Application, create_server
from tests.helpers import evaluation_data, set_response


def supplied(language="EN", voice=False):
    question, answer = {
        "RU": ("Где инструкция?", "Здравствуйте, я Сэм. Откройте раздел Помощь. До свидания."),
        "KZ": ("Нұсқаулық қайда?", "Сәлеметсіз бе, мен Сэммін. Көмек бөлімін ашыңыз. Сау болыңыз."),
        "EN": ("Where is the guide?", "Hello, I am Sam. Open Help. Goodbye."),
    }[language]
    return {"dataset_group_id": "INTERNAL_OFFLINE_TEST",
            "record": {"conversation_id": "unseen-" + language + ("-voice" if voice else ""),
                       "channel": "voice call" if voice else "agent chat", "language": language,
                       "audio_url": "https://audio.invalid/never-fetch-or-export" if voice else None,
                       "transcript": [
                           {"message_id": "source-a", "speaker": "client", "timestamp": "00:00", "text": question},
                           {"message_id": "source-b", "speaker": "operator", "timestamp": "00:02", "text": answer}]}}


def grant(value, data_class="synthetic_test", external=()):
    return {"conversation_sha256": conversation_fingerprint(ConversationInput.model_validate(value).normalize()),
            "data_class": data_class, "authorization_reference": "offline-test-owner-approval",
            "external_providers": list(external), "expires_at": "2100-01-01T00:00:00Z"}


class ControlBackendTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "outputs").mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=ROOT / "outputs")
        self.manifest = Path(self.folder.name) / "approvals.json"
        self.values = [supplied(lang) for lang in ("RU", "KZ", "EN")] + [supplied("RU", True)]
        self.grants = [grant(v, "organizer_control" if v["record"]["channel"] == "voice call" else "synthetic_test",
                             ["openai"]) for v in self.values]
        self.manifest.write_text(json.dumps({"schema_version": "1.0", "grants": self.grants}))
        self.app = Application(api_key="", authorization_manifest=self.manifest,
                               output_dir=Path(self.folder.name) / "app", live_call_limit=0)
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
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        request_headers = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.server.server_port}"}
        request_headers.update(headers or {})
        conn.request("GET" if body is None else "POST", path, json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
                     headers=request_headers)
        r = conn.getresponse()
        status, raw = r.status, r.read()
        conn.close()
        return status, json.loads(raw)

    def test_unseen_ru_kz_en_and_voice_preserve_source_and_evidence(self):
        for value in self.values:
            with self.subTest(language=value["record"]["language"], channel=value["record"]["channel"]):
                status, body = self.request("/api/evaluations", {"conversation": value})
                self.assertEqual(status, 200, body.get("error"))
                result = EvaluationResult.model_validate(body)
                self.assertEqual(result.status, "mock_only")
                self.assertEqual(len(result.model_evaluation.decisions), 8)
                messages = result.conversation.messages
                self.assertEqual([m.text for m in messages], [m["text"] for m in value["record"]["transcript"]])
                self.assertEqual([m.timestamp for m in messages], ["00:00", "00:02"])
                self.assertEqual([m.source_message_id for m in messages], ["source-a", "source-b"])
                self.assertEqual([m.message_id for m in messages], ["m0000", "m0001"])
                self.assertEqual([m.role for m in messages], ["customer", "agent"])
                self.assertEqual(result.score, score_evaluation(result.model_evaluation, result.conversation, result.checklist))
                self.assertEqual(result.run.input_authorization.conversation_sha256,
                                 conversation_fingerprint(result.conversation))
                self.assertEqual(result.audit[0].stage, "input_authorization")
                self.assertNotIn("audio.invalid", result.model_dump_json())
                for decision in result.model_evaluation.decisions:
                    self.assertEqual(decision.evidence[0].end_message_id, "m0001")
                self.assertEqual((self.app.output_dir / (result.evaluation_id + ".json")).stat().st_mode & 0o777, 0o600)

    def test_no_self_authorization_or_content_substitution(self):
        self.app.provider_factory = lambda *args: self.fail("Provider must not be constructed")
        mutations = []
        for field in ("conversation_id", "language", "audio_url"):
            v = deepcopy(self.values[0]); v["record"][field] = "changed"; mutations.append(v)
        for field in ("text", "message_id", "timestamp", "speaker"):
            v = deepcopy(self.values[0]); v["record"]["transcript"][0][field] = "operator" if field == "speaker" else "changed"
            mutations.append(v)
        v = deepcopy(self.values[0]); v["dataset_group_id"] = "CHANGED"; mutations.append(v)
        for value in mutations:
            self.assertEqual(self.request("/api/evaluations", {"conversation": value})[0], 403)
        for label in ("synthetic_test", "organizer_control", "unapproved_private"):
            self.assertEqual(self.request("/api/evaluations", {"conversation": self.values[0], "data_class": label})[0], 422)
        self.assertFalse(self.app.output_dir.exists())

    def test_expired_missing_and_private_grants_deny(self):
        conv = ConversationInput.model_validate(self.values[0]).normalize()
        with self.assertRaises(AccessDenied):
            InputPolicy().authorize(conv)
        expired = deepcopy(self.grants[0]); expired["expires_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaises(AccessDenied):
            InputPolicy(AuthorizationManifest(grants=[expired])).authorize(conv)
        for changed in ({"data_class": "unapproved_private"}, {"expires_at": "2100-01-01"}, {"external_providers": ["unknown"]}):
            g = dict(self.grants[0], **changed)
            with self.assertRaises(ValueError):
                AuthorizationManifest(grants=[g])

    def test_external_requires_grant_opt_in_and_budget_before_provider(self):
        self.app.api_key = "offline-test-placeholder"
        self.app.provider_factory = lambda *args: self.fail("No provider or network allowed")
        body = {"conversation": self.values[0], "provider": "openai", "model": "offline-only"}
        self.assertEqual(self.request("/api/evaluations", body)[0], 403)
        self.app.input_policy.allow_external = True
        self.assertEqual(self.request("/api/evaluations", body)[0], 422)  # live limit zero
        self.assertEqual(self.app.live_calls, 0)
        local_only = dict(self.grants[0], external_providers=[])
        self.app.input_policy = InputPolicy(AuthorizationManifest(grants=[local_only]), allow_external=True)
        self.assertEqual(self.request("/api/evaluations", body)[0], 403)

    def test_real_adapter_authorized_control_contract_with_offline_transport(self):
        value = self.values[-1]  # Voice transcript, synthetic offline content; no audio export.
        self.app.api_key, self.app.live_call_limit = "offline-test-placeholder", 1
        self.app.input_policy.allow_external = True
        calls = []
        def factory(name, model):
            def transport(payload, timeout):
                calls.append(payload)
                context = json.loads(payload["input"])
                from cqa.schemas import Conversation
                conv = Conversation.model_validate(context["conversation"])
                checklist = Checklist.model_validate(context["checklist"])
                raw = MockProvider().evaluate(conv, checklist, {}, EvaluationConfig()).evaluation
                return {"status": "completed", "model": model, "id": "offline-fixture-not-live",
                        "output": [{"content": [{"type": "output_text", "text": json.dumps(raw)}]}]}
            return OpenAIProvider(model, api_key="offline-test-placeholder", transport=transport,
                                  input_policy=self.app.input_policy)
        self.app.provider_factory = factory
        status, body = self.request("/api/evaluations", {"conversation": value, "provider": "openai", "model": "offline-model"})
        self.assertEqual(status, 200, body.get("error"))
        self.assertEqual(body["run"]["input_authorization"]["data_class"], "organizer_control")
        self.assertEqual(body["run"]["input_authorization"]["permission"], "external_openai")
        self.assertEqual(body["run"]["response_id"], "offline-fixture-not-live")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("audio.invalid", json.dumps(calls))
        self.assertFalse(calls[0]["store"])

    def test_provider_gate_rechecks_content_and_request(self):
        conv = ConversationInput.model_validate(self.values[0]).normalize()
        policy = InputPolicy(AuthorizationManifest(grants=self.grants), allow_external=True)
        provider = OpenAIProvider("offline", api_key="offline-test-placeholder", input_policy=policy,
                                  transport=lambda *args: self.fail("Unexpected transport"))
        changed = conv.model_copy(deep=True)
        changed.messages[0] = changed.messages[0].model_copy(update={"text": "changed"})
        with self.assertRaises(AccessDenied):
            provider.evaluate(changed, load_checklist(), {}, EvaluationConfig())
        request, _ = build_request(conv, load_checklist())
        request["input"] = "Substituted input"
        with self.assertRaises(ProviderError):
            provider.evaluate(conv, load_checklist(), request, EvaluationConfig())

    def test_checklist_save_select_new_criterion_weight_and_version(self):
        original = load_checklist().model_dump(mode="json")
        changed = deepcopy(original); changed["version"] = "offline-v-next"
        changed["criteria"][0]["weight"] = 30
        added = deepcopy(changed["criteria"][0]); added.update(criterion_id="NEW", weight=5)
        changed["criteria"].append(added)
        status, ref = self.request("/api/checklists", changed)
        self.assertEqual(status, 201)
        self.assertEqual(ref["sha256"], digest(changed))
        self.assertEqual(self.request("/api/checklists/" + ref["sha256"]), (200, changed))
        self.assertEqual(len(self.request("/api/checklists")[1]), 6)  # Built-ins v2-v6 plus the saved version.
        body = {"conversation": self.values[2]}
        first_status, first = self.request("/api/evaluations", body)
        body["checklist"] = {"checklist_id": ref["checklist_id"], "version": ref["version"]}
        next_status, second = self.request("/api/evaluations", body)
        self.assertEqual((first_status, next_status), (200, 200))
        self.assertEqual(len(second["model_evaluation"]["decisions"]), 9)
        self.assertEqual(second["score"]["applicable_weight"], 125)
        self.assertNotEqual(first["run"]["checklist_sha256"], second["run"]["checklist_sha256"])
        self.assertNotEqual(first["evaluation_id"], second["evaluation_id"])
        self.assertEqual(json.loads((self.app.output_dir / (first["evaluation_id"] + ".json")).read_text()), first)
        reopened = Application(api_key="", output_dir=self.app.output_dir)
        self.assertEqual(len(reopened.checklists.list()), 4)
        self.assertEqual(reopened.checklists.by_hash(ref["sha256"]).model_dump(mode="json"), changed)
        # ID-based DEV compatibility also supports the explicitly saved version.
        status, result = self.request("/api/evaluations", {"conversation_id": "p1-ru-001", "checklist": body["checklist"]})
        self.assertEqual(status, 200)
        self.assertEqual(result["checklist"]["version"], "offline-v-next")

    def test_weight_change_changes_deterministic_score_without_overwriting(self):
        def factory(*args):
            class Scripted(MockProvider):
                def evaluate(self, conv, checklist, request, config):
                    raw = evaluation_data(conv, checklist)
                    decision = set_response(raw, checklist, "01", "no")
                    for atomic in decision["atomic_checks"]:
                        atomic["answer"] = "no"
                    return ProviderReply(raw, model="scripted-offline-scoring-test")
            return Scripted()
        self.app.provider_factory = factory
        first = self.request("/api/evaluations", {"conversation": self.values[2]})[1]
        changed = load_checklist().model_dump(mode="json"); changed["version"] = "weight-test"
        changed["criteria"][0]["weight"] = 30
        self.assertEqual(self.request("/api/checklists", changed)[0], 201)
        status, second = self.request("/api/evaluations", {"conversation": self.values[2], "checklist": {
            "checklist_id": changed["checklist_id"], "version": changed["version"]}})
        self.assertEqual(status, 200, second.get("error"))
        self.assertEqual((first["score"]["total_score"], second["score"]["total_score"]), ("90.00", "75.00"))

    def test_version_conflicts_unknown_versions_and_unsupported_config(self):
        checklist = load_checklist().model_dump(mode="json")
        changed = deepcopy(checklist); changed["criteria"][0]["weight"] = 30
        self.assertEqual(self.request("/api/checklists", changed)[0], 409)
        self.assertEqual(self.request("/api/checklists", checklist)[0], 201)
        body = {"conversation": self.values[0], "checklist": {"checklist_id": "unknown", "version": "x"}}
        self.assertEqual(self.request("/api/evaluations", body)[0], 404)
        for levels in ([1, 2, 3], [0, .5, 1]):
            v = deepcopy(checklist); v["criteria"][3]["levels"] = levels
            self.assertEqual(self.request("/api/checklists", v)[0], 422)
        v = deepcopy(checklist); v["criteria"][-1]["questions"][0]["violation_category"] = "new-category"
        self.assertEqual(self.request("/api/checklists", v)[0], 422)
        self.assertEqual(self.request("/api/checklists", checklist, {"Origin": "https://foreign.invalid"})[0], 403)

    def test_saved_versions_detect_tampering_and_cross_instance_conflicts(self):
        original = load_checklist()
        directory = Path(self.folder.name) / "registry-test"
        first = ChecklistRegistry(original, directory)
        second = ChecklistRegistry(original, directory)
        v = original.model_dump(mode="json"); v["version"] = "shared-version"
        snapshot = Checklist.model_validate(v)
        first.save(snapshot)
        v["criteria"][0]["weight"] = 30
        with self.assertRaises(ChecklistConflict):
            second.save(Checklist.model_validate(v))
        # Registry reads return independent copies; a caller cannot edit history.
        from cqa.web import ChecklistReference
        ref = ChecklistReference(checklist_id=snapshot.checklist_id, version=snapshot.version)
        returned = first.get(ref)
        returned.criteria.clear()
        self.assertEqual(len(first.get(ref).criteria), 8)
        path = next(directory.glob("*.json"))
        saved = json.loads(path.read_text()); saved["checklist"]["criteria"][0]["weight"] = 30
        path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "content/hash"):
            ChecklistRegistry(original, directory)

    def test_new_input_without_server_manifest_and_fake_approval_route(self):
        self.app.input_policy = InputPolicy()
        self.app.provider_factory = lambda *args: self.fail("Must deny before provider")
        status, error = self.request("/api/evaluations", {"conversation": self.values[0]})
        self.assertEqual(status, 403)
        self.assertEqual(set(error), {"error"})
        self.assertFalse(self.app.output_dir.exists())
        self.assertEqual(self.request("/api/authorizations", {"grants": self.grants})[0], 404)

    def test_invalid_evidence_remains_rejected_and_diagnostic_is_accessible(self):
        class InvalidEvidence(MockProvider):
            def evaluate(self, conv, checklist, request, config):
                raw = evaluation_data(conv, checklist)
                raw["decisions"][0]["evidence"][0]["quote"] = "Invented quote"
                return ProviderReply(raw, model="offline-invalid-evidence")
        self.app.provider_factory = lambda *args: InvalidEvidence()
        status, body = self.request("/api/evaluations", {"conversation": self.values[2]})
        self.assertEqual(status, 422)
        self.assertNotIn("score", body)
        status, diagnostic = self.request("/api/diagnostics/" + body["diagnostic_id"])
        self.assertEqual(status, 200)
        self.assertNotIn("score", diagnostic)
        self.assertEqual(diagnostic["run"]["input_authorization"]["source"], "local_manifest")
        self.app.input_policy = InputPolicy()  # revoked for subsequent reads
        self.assertEqual(self.request("/api/diagnostics/" + body["diagnostic_id"])[0], 404)

    def test_exclusive_input_normalization_and_bounded_requests(self):
        for body in ({}, {"conversation_id": "p1-ru-001", "conversation": self.values[0]}):
            self.assertEqual(self.request("/api/evaluations", body)[0], 422)
        value = deepcopy(self.values[0]); value["record"]["transcript"][0]["speaker"] = "unknown"
        self.assertEqual(self.request("/api/evaluations", {"conversation": value})[0], 422)
        self.assertEqual(self.request("/api/evaluations", {"conversation": self.values[0]}, {"Content-Length": "private-header"})[0], 413)
        # Reject the declared oversize before reading/uploading its body.
        self.assertEqual(self.request("/api/evaluations", {}, {"Content-Length": str(1024 * 1024 + 1)})[0], 413)


    def test_atomic_version_selected_over_http_and_re_evaluated_without_overwrite(self):
        from tests.test_atomic_path import atomic_checklist, raw_fixture, fact
        class OfflineAtomic(MockProvider):
            def evaluate(self, conv, checklist, request, config):
                raw=raw_fixture(conv,checklist)
                for qid in ("01.q1","01.q2"):fact(raw,qid)["answer"]="no"
                return ProviderReply(raw,model="offline-http-atomic")
        self.app.provider_factory=lambda *args:OfflineAtomic()
        checklist=atomic_checklist()
        body={"conversation":self.values[2],"checklist":{"checklist_id":checklist.checklist_id,"version":checklist.version}}
        status,first=self.request("/api/evaluations",body)
        self.assertEqual(status,200,first.get("error"))
        self.assertEqual(first["decision_path"],"atomic_first")
        self.assertEqual(first["original_provider_output"]["schema_version"],"1.2")
        self.assertEqual(first["score"]["total_score"],"84.62")
        changed=checklist.model_dump(mode="json");changed["version"]="atomic-http-next";changed["criteria"][0]["weight"]=30
        self.assertEqual(self.request("/api/checklists",changed)[0],201)
        body["checklist"]["version"]=changed["version"]
        status,second=self.request("/api/evaluations",body)
        self.assertEqual(status,200,second.get("error"))
        self.assertEqual(second["score"]["total_score"],"64.71")
        self.assertNotEqual(first["evaluation_id"],second["evaluation_id"])
        self.assertEqual(json.loads((self.app.output_dir/(first["evaluation_id"]+".json")).read_text()),first)


class LocalVoiceIngressTests(unittest.TestCase):
    def test_provided_five_voice_transcripts_locally_only(self):
        path = Path(os.environ.get("CQA_TEST_FULL_DEV", str(ROOT / "data/raw/DEV_conversations.json")))
        if not path.exists():
            self.skipTest("Provide CQA_TEST_FULL_DEV for local-only original voice records")
        data, _ = read_dataset(path)
        voices = [r for r in data["records"] if r["channel"] == "voice call"]
        self.assertEqual(len(voices), 5)
        with tempfile.TemporaryDirectory(dir=ROOT / "outputs") as folder:
            manifest = Path(folder) / "voice-approvals.json"
            inputs = [{"dataset_group_id": data["dataset_group_id"], "record": r} for r in voices]
            approvals = [dict(grant(v, "organizer_dev"),
                              authorization_reference="owner-request-provided-dev-voice-local-only") for v in inputs]
            manifest.write_text(json.dumps({"schema_version": "1.0", "grants": approvals}))
            app = Application(api_key="", authorization_manifest=manifest, output_dir=Path(folder) / "app", live_call_limit=0)
            from cqa.web import EvaluationRequest
            for value in inputs:
                result = app.run(EvaluationRequest(conversation=ConversationInput.model_validate(value)))
                self.assertEqual(result.conversation.channel, "voice")
                self.assertEqual(result.run.input_authorization.data_class, "organizer_dev")
                self.assertEqual([m.text for m in result.conversation.messages], [m["text"] for m in value["record"]["transcript"]])
                self.assertEqual([m.timestamp for m in result.conversation.messages], [m["timestamp"] for m in value["record"]["transcript"]])
                self.assertNotIn(value["record"]["audio_url"], result.model_dump_json())
                self.assertEqual(len(result.model_evaluation.decisions), 8)
                with self.assertRaises(AccessDenied):
                    app.input_policy.authorize(result.conversation, "openai")
            self.assertEqual(app.live_calls, 0)
