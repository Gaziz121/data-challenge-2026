"""Exporter + atomic-v5 candidate integration, offline only (scripted fixtures, never labels)."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from cqa.io import load_checklist
from cqa.loader import ROOT, SHARED
from cqa.providers import MockProvider, ProviderReply
from cqa.schemas import EvaluationConfig
from cqa_results.batch import main as batch_main, run_batch
from cqa_results.export import build_submission, check_checklist, serialize
from cqa_results.validate import load_dataset_index, strict_load, validate_submission
from tests.test_atomic_path import raw_fixture, scope
from tests.test_schema_reliability import full_scope_normalized

V5 = ROOT / "src/cqa/checklists/official-v5.json"
OUTPUTS = ROOT / "outputs"


class AtomicFixtureProvider(MockProvider):
    """Per-conversation hand-authored atomic fixture; mock-flagged so it can never be submitted."""
    model = "offline-atomic-v5-fixture"

    def __init__(self):
        self.prompt_versions = []

    def evaluate(self, conversation, checklist, request, config):
        self.prompt_versions.append(json.loads(request["input"])["prompt_version"])
        raw = raw_fixture(conversation, checklist)
        for entry in raw["criteria"]:
            criterion = next(c for c in checklist.criteria if c.criterion_id == entry["criterion_id"])
            for a in entry["atomic_checks"]:
                if a["question_id"] == "06.q4":
                    a.update(answer="no", evidence=[scope(conversation)])
            entry.update(full_scope_normalized(entry, criterion))
        return ProviderReply(deepcopy(raw), model=self.model)


class SubmissionIntegrationTests(unittest.TestCase):
    def setUp(self):
        OUTPUTS.mkdir(exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=OUTPUTS, prefix="test-integration-"))
        envelope = json.loads(Path(SHARED).read_text())
        envelope["data"]["records"] = [r for r in envelope["data"]["records"]
                                       if r["conversation_id"] in ("p1-ru-014", "p1-kz-010", "p1-en-011")]
        envelope["data"]["total_records"] = 3
        self.data = self.tmp / "dataset.json"
        self.data.write_text(json.dumps(envelope, ensure_ascii=False))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_v5_checklist_passes_exporter_guard(self):
        check_checklist(load_checklist(V5))

    def test_batch_uses_requested_atomic_prompt_and_exports_valid_json(self):
        provider = AtomicFixtureProvider()
        counts = run_batch(self.data, self.tmp / "run", provider, checklist=load_checklist(V5),
                           config=EvaluationConfig(prompt_version="atomic-v5", quote_policy="normalize_formatting"),
                           log=lambda *_: None)
        self.assertEqual((counts["attempted"], counts["result"]), (3, 3))
        self.assertEqual(provider.prompt_versions, ["atomic-v5"] * 3)
        manifest = json.loads((self.tmp / "run/run.json").read_text())
        self.assertEqual(manifest["configuration"]["prompt_version"], "atomic-v5")
        submission, report = build_submission(self.data, self.tmp / "run", "Offline Team", "dev", allow_mock=True)
        self.assertEqual(report["ok"], 3)
        self.assertTrue(all(len(r["criteria"]) == 8 for r in submission["results"]))
        index, _ = load_dataset_index(self.data)
        errors = validate_submission(strict_load(serialize(submission)), index, "dev")["errors"]
        self.assertTrue(errors and all("65" in e for e in errors), errors)  # Only the DEV-65 size rule fails.

    def test_resume_refuses_prompt_change_and_atomic_prompt_needs_atomic_checklist(self):
        run_batch(self.data, self.tmp / "run", AtomicFixtureProvider(), checklist=load_checklist(V5),
                  config=EvaluationConfig(prompt_version="atomic-v5"), log=lambda *_: None)
        with self.assertRaises(ValueError):
            run_batch(self.data, self.tmp / "run", AtomicFixtureProvider(), checklist=load_checklist(V5),
                      config=EvaluationConfig(prompt_version="atomic-v2"), resume=True, log=lambda *_: None)
        with self.assertRaises(ValueError):
            run_batch(self.data, self.tmp / "legacy", AtomicFixtureProvider(), checklist=load_checklist(),
                      config=EvaluationConfig(prompt_version="atomic-v5"), log=lambda *_: None)
        self.assertFalse((self.tmp / "legacy/run.json").exists())

    def test_cli_flag_reaches_run_manifest(self):
        code = batch_main(["--data", str(self.data), "--run-dir", str(self.tmp / "cli"), "--provider", "mock",
                           "--checklist", str(V5), "--prompt-version", "atomic-v5"])
        manifest = json.loads((self.tmp / "cli/run.json").read_text())
        self.assertEqual(manifest["configuration"]["prompt_version"], "atomic-v5")
        self.assertIn(code, (0, 1))  # Mock atomic output is review-only: honest error records, no score.


if __name__ == "__main__":
    unittest.main()
