from copy import deepcopy
from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest

from cqa.cli import main
from cqa.engine import CheckBlocked, evaluate
from cqa.io import load_checklist
from cqa.preprocessing import extract_facts
from cqa.providers import MockProvider, ProviderReply
from cqa.schemas import CheckFinding, CheckOutcome, Checklist, EvaluationResult
from tests.helpers import conversation, evaluation_data


class AdvisoryCheck:
    name = "test-advisory"
    version = "test-v1"
    phase = "post_validation"
    severity = "review"

    def run(self, context):
        return CheckOutcome(check_name=self.name, check_version=self.version, phase=self.phase,
                            findings=[CheckFinding(code="test-fact", severity=self.severity,
                                                   criterion_ids=[context.checklist.criteria[0].criterion_id],
                                                   explanation="Testable advisory finding; leaves maker unchanged.")])


class OfflineMaker:
    name = "offline-test"
    model = "hand-authored-test-output"
    is_mock = False  # Exercise needs_review status; this class never performs I/O.

    def evaluate(self, conversation, checklist, request, config):
        return ProviderReply(evaluation_data(conversation, checklist), model=self.model)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.conv, self.checklist = conversation(), load_checklist()

    def test_facts_and_explicit_applicability_constraints(self):
        facts = extract_facts(self.conv, self.checklist)
        self.assertEqual(facts.role_counts, {"customer": 1, "agent": 1, "bot": 1, "system": 1})
        self.assertEqual(facts.first_agent_message_id, "m0003")
        self.assertEqual([c.criterion_id for c in facts.applicability_constraints if c.na_allowed], ["02", "03", "04", "07"])

    def test_mock_pipeline_audit_and_roundtrip(self):
        result = evaluate(self.conv, self.checklist, MockProvider())
        self.assertEqual(EvaluationResult.model_validate_json(result.model_dump_json()), result)
        stages = [a.stage for a in result.audit]
        self.assertEqual(stages, ["normalized_input", "facts_and_applicability_constraints",
                                 "pre_evaluation:agent-presence", "primary_atomic_evaluation",
                                 "schema_evidence_consistency_validation", "official_deterministic_scoring"])
        self.assertEqual(result.status, "mock_only")
        self.assertTrue(result.run.is_mock)
        self.assertEqual(len(result.run.prompt_sha256), 64)
        self.assertEqual(result.revision_history, [])

    def test_mock_decisions_and_prompt_hash_reproducible(self):
        a = evaluate(self.conv, self.checklist, MockProvider())
        b = evaluate(self.conv, self.checklist, MockProvider())
        self.assertEqual(a.model_evaluation, b.model_evaluation)
        self.assertEqual(a.run.prompt_sha256, b.run.prompt_sha256)
        self.assertEqual(a.score, b.score)

    def test_advisory_check_preserves_original_scores_and_decisions(self):
        original = evaluate(self.conv, self.checklist, OfflineMaker())
        result = evaluate(self.conv, self.checklist, OfflineMaker(), checks=[AdvisoryCheck()])
        self.assertEqual(original.model_evaluation, result.model_evaluation)
        self.assertEqual(original.score, result.score)
        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.check_outcomes[-1].check_version, "test-v1")

    def test_post_check_block_retains_maker_without_a_score(self):
        check = AdvisoryCheck()
        check.severity = "block"
        with self.assertRaises(CheckBlocked) as caught:
            evaluate(self.conv, self.checklist, OfflineMaker(), checks=[check])
        self.assertEqual(len(caught.exception.original_evaluation.decisions), 8)
        self.assertEqual(caught.exception.check_outcomes[-1].findings[0].severity, "block")

    def test_pre_check_block_prevents_provider_call(self):
        check = AdvisoryCheck()
        check.phase, check.severity = "pre_evaluation", "block"
        class NeverCalled(MockProvider):
            def evaluate(self, *args):
                raise AssertionError("Provider must not run after a pre-check block")
        with self.assertRaises(CheckBlocked) as caught:
            evaluate(self.conv, self.checklist, NeverCalled(), checks=[check])
        self.assertIsNone(caught.exception.original_evaluation)

    def test_mutating_extension_gets_private_snapshot(self):
        class MutatingCheck(AdvisoryCheck):
            def run(self, context):
                context.conversation.messages.clear()
                context.evaluation.decisions.clear()
                return super().run(context)
        result = evaluate(self.conv, self.checklist, OfflineMaker(), checks=[MutatingCheck()])
        self.assertEqual(len(result.conversation.messages), 4)
        self.assertEqual(len(result.model_evaluation.decisions), 8)
        self.assertEqual(result.score.total_score, "100.00")

    def test_no_agent_filter_flags_without_inventing_na(self):
        result = evaluate(conversation(agent=False), self.checklist, MockProvider())
        self.assertEqual(result.check_outcomes[0].findings[0].code, "no-human-agent")
        self.assertFalse(any(d.response == "N/A" for d in result.model_evaluation.decisions))
        self.assertEqual(result.score.applicable_weight, 100)

    def test_new_organizer_criterion_runs_without_application_edits(self):
        value = self.checklist.model_dump()
        criterion = deepcopy(value["criteria"][0])
        criterion.update(criterion_id="organizer-new", title="New requirement", instructions="A custom instruction",
                         weight=45, consistency_rules=[],
                         questions=[{"question_id": "custom-q", "question": "Was the custom action performed?"}])
        value["criteria"] = [criterion]
        value["version"] = "organizer-test-v2"
        checklist = Checklist.model_validate(value)
        result = evaluate(self.conv, checklist, MockProvider(), checks=[AdvisoryCheck()])
        self.assertEqual(result.model_evaluation.decisions[0].criterion_id, "organizer-new")
        self.assertEqual(result.model_evaluation.decisions[0].atomic_checks[0].question_id, "custom-q")

    def test_schema_cli_exports(self):
        for contract in ("conversation", "checklist", "model", "result"):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["schema", contract]), 0)
            self.assertIn('"$defs"', output.getvalue())

    def test_cli_refuses_existing_output_before_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "keep.json"
            output.write_text("preserved")
            with redirect_stderr(io.StringIO()):
                code = main(["evaluate", "--id", "irrelevant", "--provider", "openai", "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertEqual(output.read_text(), "preserved")

    def test_cli_rejects_transcript_output_outside_private_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "result.json"
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["evaluate", "--id", "any", "--output", str(output)]), 1)
            self.assertFalse(output.exists())
