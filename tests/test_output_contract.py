"""R1/R3/R4 regression checks. All providers are offline test doubles."""

from copy import deepcopy
import hashlib
import json
import unittest

from pydantic import ValidationError

from cqa.engine import diagnose_output, evaluate, EvaluationRejected
from cqa.io import digest, load_checklist
from cqa.loader import SHARED, load_conversation, read_dataset
from cqa.prompt import build_request, PROMPT_VERSION
from cqa.providers import MockProvider, OpenAIProvider, ProviderReply
from cqa.schemas import Checklist, Decision, EvaluationConfig, ModelEvaluation, MODEL_OUTPUT_SCHEMA_VERSION
from tests.helpers import conversation, evaluation_data


class OutputContractTests(unittest.TestCase):
    def setUp(self):
        self.conv, self.checklist = conversation(), load_checklist()
        self.raw = evaluation_data(self.conv, self.checklist)

    def test_actual_serialized_provider_schema_orders_checks_before_response(self):
        data, _ = read_dataset(SHARED)
        conv = load_conversation(SHARED, data["records"][0]["conversation_id"])
        config = EvaluationConfig(external_synthetic_allowed=True)
        request, _ = build_request(conv, self.checklist)
        def transport(payload, timeout):
            serialized = json.dumps(payload, ensure_ascii=False)
            schema = json.loads(serialized)["text"]["format"]["schema"]
            decision = schema["$defs"]["Decision"]
            for keys in (list(decision["properties"]), decision["required"]):
                self.assertLess(keys.index("atomic_checks"), keys.index("response"))
            self.assertEqual(schema["properties"]["schema_version"]["const"], "1.1")
            self.assertEqual(payload["text"]["format"]["name"], "cqa_evaluation_v1_1")
            raw = MockProvider().evaluate(conv, self.checklist, request, config).evaluation
            return {"status": "completed", "id": "offline-contract", "model": "offline-model",
                    "output": [{"content": [{"type": "output_text", "text": json.dumps(raw)}]}]}
        reply = OpenAIProvider("offline-model", api_key="unit-test-placeholder", transport=transport).evaluate(
            conv, self.checklist, request, config)
        self.assertEqual(reply.evaluation["schema_version"], MODEL_OUTPUT_SCHEMA_VERSION)

    def test_new_prompt_and_output_versions_preserve_legacy_reading(self):
        request, _ = build_request(self.conv, self.checklist)
        payload = json.loads(request["input"])
        self.assertEqual(PROMPT_VERSION, "baseline-v3")
        self.assertEqual(payload["output_schema_version"], "1.1")
        for version in ("1.0", "1.1"):
            raw = deepcopy(self.raw); raw["schema_version"] = version
            self.assertEqual(ModelEvaluation.model_validate(raw).schema_version, version)
        self.assertIn('na_reason MUST be JSON null unless response is exactly "N/A"', request["instructions"])
        self.assertIn("null", request["schema"]["$defs"]["Decision"]["properties"]["na_reason"]["description"])

    def test_custom_applicability_question_is_serialized_first_without_mutation(self):
        value = self.checklist.model_dump()
        definition = value["criteria"][1]
        definition["questions"].reverse()
        checklist = Checklist.model_validate(value)
        before = digest(checklist.model_dump())
        request, _ = build_request(self.conv, checklist)
        emitted = json.loads(request["input"])["checklist"]["criteria"][1]
        self.assertEqual(emitted["questions"][0]["question_id"], emitted["applicability_rule"]["question_id"])
        self.assertEqual(before, digest(checklist.model_dump()))

    def test_prompt_hash_preserves_schema_order(self):
        request, recorded = build_request(self.conv, self.checklist)
        def ordered_hash(value):
            wire = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            return hashlib.sha256(wire.encode()).hexdigest()
        self.assertEqual(recorded, ordered_hash(request))
        changed = deepcopy(request)
        props = changed["schema"]["$defs"]["Decision"]["properties"]
        changed["schema"]["$defs"]["Decision"]["properties"] = dict(reversed(list(props.items())))
        self.assertNotEqual(recorded, ordered_hash(changed))

    def test_metadata_does_not_mask_applicability_consistency_or_citation_errors(self):
        d = self.raw["decisions"][1]
        d["na_reason"] = "Invalid reason on an applicable response"
        d["atomic_checks"][0]["answer"] = "yes"
        d["atomic_checks"][1]["answer"] = "no"
        d["evidence"][0]["quote"] = "Not present in the source"
        before = deepcopy(self.raw)
        issues, statuses = diagnose_output(self.raw, self.conv, self.checklist)
        messages = [i["message"] for i in issues if i["criterion_id"] == "02"]
        for expected in ("null for na_reason", "Applicable response conflicts", "consistency rule", "exact source substring"):
            self.assertTrue(any(expected in message for message in messages), messages)
        self.assertEqual(statuses[1]["status"], "invalid")
        self.assertEqual(self.raw, before)
        with self.assertRaises(ValidationError):
            Decision.model_validate(d)

    def test_bad_nested_evidence_does_not_hide_valid_atomic_applicability_answer(self):
        d = self.raw["decisions"][1]
        d["atomic_checks"][0]["answer"] = "yes"
        d["atomic_checks"][0]["evidence"][0]["kind"] = "invalid-evidence-kind"
        issues, _ = diagnose_output(self.raw, self.conv, self.checklist)
        messages = [i["message"] for i in issues if i["criterion_id"] == "02"]
        self.assertTrue(any("Applicable response conflicts" in message for message in messages))
        self.assertTrue(any(i.get("location", [])[:1] == ["atomic_checks"] for i in issues))

    def test_all_independent_metadata_errors_are_reported(self):
        d = self.raw["decisions"][0]
        d.update(rationale=" ", na_reason="not allowed", review_reason="not allowed")
        issues, _ = diagnose_output(self.raw, self.conv, self.checklist)
        messages = [i["message"] for i in issues if i["criterion_id"] == "01"]
        self.assertIn("Rationale cannot be whitespace", messages)
        self.assertIn("Applicable decisions must use null for na_reason", messages)
        self.assertIn("Unflagged decisions must use null for review_reason", messages)

    def test_diagnostic_projection_can_never_be_scored(self):
        raw = deepcopy(self.raw)
        raw["decisions"][1]["na_reason"] = "Invalid applicable reason"
        raw["decisions"][1]["atomic_checks"][0]["answer"] = "yes"
        class Replayed(MockProvider):
            def evaluate(self, *args):
                return ProviderReply(raw, model="offline-replay")
        with self.assertRaises(EvaluationRejected) as caught:
            evaluate(self.conv, self.checklist, Replayed())
        self.assertNotIn("score", caught.exception.diagnostic)
        self.assertEqual(caught.exception.diagnostic["original_model_output"], raw)


if __name__ == "__main__":
    unittest.main()
