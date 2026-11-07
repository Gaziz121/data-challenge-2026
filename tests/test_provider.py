from copy import deepcopy
import json
import unittest

from cqa.engine import evaluate
from cqa.io import load_checklist
from cqa.loader import SHARED, load_conversation, read_dataset
from cqa.prompt import build_request
from cqa.providers import MockProvider, OpenAIProvider, ProviderError
from cqa.schemas import EvaluationConfig
from tests.helpers import conversation


class ProviderTests(unittest.TestCase):
    def setUp(self):
        data, _ = read_dataset(SHARED)
        self.conv = load_conversation(SHARED, data["records"][0]["conversation_id"])
        self.checklist, self.config = load_checklist(), EvaluationConfig(external_synthetic_allowed=True)
        self.request, _ = build_request(self.conv, self.checklist)
        raw = MockProvider().evaluate(self.conv, self.checklist, self.request, self.config).evaluation
        self.response = {"id": "offline-response", "model": "offline-model", "status": "completed",
                         "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(raw)}]}],
                         "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}

    def provider(self, response=None, transport=None):
        return OpenAIProvider("offline-model", api_key="unit-test-placeholder", transport=transport or (
            lambda payload, timeout: deepcopy(response or self.response)))

    def test_offline_responses_http_contract_and_pipeline(self):
        seen = []
        def transport(payload, timeout):
            seen.append(payload)
            self.assertFalse(payload["store"])
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertTrue(payload["text"]["format"]["strict"])
            self.assertEqual(payload["text"]["format"]["schema"], self.request["schema"])
            self.assertNotIn("api_key", payload)
            return deepcopy(self.response)
        result = evaluate(self.conv, self.checklist, self.provider(transport=transport), self.config)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result.run.usage["total_tokens"], 150)
        self.assertEqual(result.run.response_id, "offline-response")
        self.assertEqual(result.run.model_returned, "offline-model")

    def test_missing_key_fails_without_transport(self):
        provider = OpenAIProvider("offline-model", api_key="", transport=lambda *args: self.fail("Network attempted"))
        with self.assertRaisesRegex(ProviderError, "not configured"):
            provider.evaluate(self.conv, self.checklist, self.request, self.config)

    def test_data_gate_prevents_transport_for_unapproved_input(self):
        provider = self.provider(transport=lambda *args: self.fail("Network attempted"))
        with self.assertRaises(ValueError):
            provider.evaluate(conversation(), self.checklist, self.request, self.config)
        with self.assertRaises(ValueError):
            provider.evaluate(self.conv, self.checklist, self.request, EvaluationConfig())

    def test_request_cannot_substitute_unapproved_transcript(self):
        request = dict(self.request)
        request["input"] = "unreviewed private data"
        with self.assertRaisesRegex(ProviderError, "does not match"):
            self.provider(transport=lambda *args: self.fail("Network attempted")).evaluate(
                self.conv, self.checklist, request, self.config)

    def test_refusal_incomplete_malformed_and_missing_outputs(self):
        cases = []
        for status in ("incomplete", "failed", "cancelled"):
            response = deepcopy(self.response)
            response["status"] = status
            cases.append(response)
        response = deepcopy(self.response)
        response["output"][0]["content"] = [{"type": "refusal", "refusal": "No"}]
        cases.append(response)
        response = deepcopy(self.response)
        response["output"][0]["content"][0]["text"] = "{broken"
        cases.append(response)
        response = deepcopy(self.response)
        response["output"] = []
        cases.append(response)
        for response in cases:
            with self.subTest(status=response["status"]), self.assertRaises(ProviderError):
                self.provider(response).evaluate(self.conv, self.checklist, self.request, self.config)

    def test_invalid_usage_is_rejected(self):
        self.response["usage"]["total_tokens"] = -1
        with self.assertRaises(ProviderError):
            self.provider().evaluate(self.conv, self.checklist, self.request, self.config)

    def test_transport_errors_are_redacted_and_not_retried(self):
        calls = []
        def transport(*args):
            calls.append(1)
            raise RuntimeError("PRIVATE INPUT MUST NOT APPEAR")
        with self.assertRaises(ProviderError) as caught:
            self.provider(transport=transport).evaluate(self.conv, self.checklist, self.request, self.config)
        self.assertNotIn("PRIVATE INPUT", str(caught.exception))
        self.assertEqual(len(calls), 1)
