from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from cqa.engine import evaluate
from cqa.io import load_checklist
from cqa.loader import ROOT, SHARED, load_conversation, normalize_record, read_dataset, require_approved_synthetic
from cqa.providers import MockProvider
from tests.helpers import conversation


class LoaderTests(unittest.TestCase):
    def test_role_separation_and_timestamps(self):
        conv = conversation()
        self.assertEqual([m.role for m in conv.messages], ["customer", "bot", "system", "agent"])
        self.assertEqual([m.timestamp for m in conv.messages], ["00:00", "00:01", "00:01", "00:02"])
        self.assertEqual([m.source_index for m in conv.messages], [0, 1, 2, 3])

    def test_source_message_ids_preserved(self):
        record = {"conversation_id": "unit", "channel": "agent chat", "language": "EN", "audio_url": None,
                  "transcript": [{"message_id": "source-42", "speaker": "operator", "text": "Hello", "timestamp": "00:01"}]}
        conv = normalize_record(record, "TEST", "0" * 64)
        self.assertEqual(conv.messages[0].source_message_id, "source-42")
        self.assertEqual(conv.messages[0].message_id, "m0000")

    def test_unknown_role_and_unmapped_context_rejected(self):
        record = {"conversation_id": "unit", "channel": "agent chat", "language": "EN", "audio_url": None,
                  "transcript": [{"speaker": "unknown", "text": "Hello", "timestamp": "00:01"}]}
        with self.assertRaises(ValueError):
            normalize_record(record, "TEST", "0" * 64)
        record["transcript"][0]["speaker"] = "operator"
        record["transcript"][0]["extra_context"] = "must not disappear"
        with self.assertRaises(ValueError):
            normalize_record(record, "TEST", "0" * 64)

    def test_all_shared_chats_normalize_and_mock_evaluate(self):
        data, _ = read_dataset(SHARED)
        languages = set()
        checklist = load_checklist()
        for record in data["records"]:
            conv = load_conversation(SHARED, record["conversation_id"])
            result = evaluate(conv, checklist, MockProvider())
            self.assertEqual(result.status, "mock_only")
            self.assertEqual(len(result.model_evaluation.decisions), 8)
            self.assertEqual([m.text for m in conv.messages], [t["text"] for t in record["transcript"]])
            languages.add(conv.language)
        self.assertEqual(len(data["records"]), 60)
        self.assertEqual(languages, {"RU", "KZ", "EN"})

    def test_full_local_dev_including_voice_without_export(self):
        source = ROOT / "data/raw/DEV_conversations.json"
        if not source.exists():
            self.skipTest("Full DEV is intentionally local-only")
        data, _ = read_dataset(source)
        voices = [r for r in data["records"] if r["channel"] == "voice call"]
        self.assertEqual(len(data["records"]), 65)
        self.assertEqual(len(voices), 5)
        for record in voices:
            conv = load_conversation(source, record["conversation_id"])
            self.assertEqual(conv.channel, "voice")
            self.assertEqual([m.timestamp for m in conv.messages], [m["timestamp"] for m in record["transcript"]])
            result = evaluate(conv, load_checklist(), MockProvider())
            self.assertNotIn("audio_url", result.model_dump_json())
            self.assertNotIn(record["audio_url"], result.model_dump_json())
            with self.assertRaises(ValueError):
                require_approved_synthetic(conv, True)

    def test_external_gate_requires_explicit_flag_and_exact_approved_content(self):
        data, _ = read_dataset(SHARED)
        conv = load_conversation(SHARED, data["records"][0]["conversation_id"])
        with self.assertRaises(ValueError):
            require_approved_synthetic(conv, False)
        require_approved_synthetic(conv, True)
        changed = conv.model_copy(deep=True)
        changed.messages[0] = changed.messages[0].model_copy(update={"text": "Tampered content"})
        with self.assertRaises(ValueError):
            require_approved_synthetic(changed, True)
        with self.assertRaises(ValueError):
            require_approved_synthetic(conversation(), True)

    def test_duplicate_ids_and_count_mismatch_rejected(self):
        envelope = {"error": "", "isSuccess": True, "data": {"dataset_group_id": "TEST", "total_records": 1,
                     "records": [{"conversation_id": "a"}]}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "dataset.json"
            for mode in ("count", "duplicates"):
                value = deepcopy(envelope)
                value["data"]["records"].append({"conversation_id": "a"})
                if mode == "duplicates":
                    value["data"]["total_records"] = 2
                path.write_text(json.dumps(value))
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    read_dataset(path)

    def test_missing_id_is_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            load_conversation(SHARED, "not-an-id")
