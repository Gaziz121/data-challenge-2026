"""Normalize -> provider -> validate -> deterministic scoring -> versioned result."""

from datetime import datetime, timezone
import platform
import time
from uuid import uuid4

import pydantic

from . import __version__
from .io import digest, parse_json
from .checks import AgentPresenceCheck
from .preprocessing import extract_facts
from .prompt import build_request
from .schemas import (Checklist, Conversation, EvaluationConfig, EvaluationResult,
                      ModelEvaluation, RunMetadata, CheckInput, CheckOutcome, AuditEvent)
from .scoring import score_evaluation
from .validation import validate_evaluation


class CheckBlocked(ValueError):
    """A gate stops scoring and retains maker output if already produced."""

    def __init__(self, outcomes, original_evaluation, audit):
        super().__init__("Evaluation blocked by an extension check; no score produced")
        self.check_outcomes = outcomes
        self.original_evaluation = original_evaluation
        self.audit = audit


def evaluate(conversation, checklist, provider, config=None, checks=()):
    config = EvaluationConfig.model_validate((config or EvaluationConfig()).model_dump())
    conversation = Conversation.model_validate(conversation.model_dump())
    checklist = Checklist.model_validate(checklist.model_dump())
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    audit, outcomes = [], []

    def record(stage, version, artifact, outcome="passed"):
        audit.append(AuditEvent(stage=stage, component_version=version, outcome=outcome,
                                artifact_sha256=digest(artifact)))

    record("normalized_input", "normalization-v1", conversation.model_dump(mode="json"))
    facts = extract_facts(conversation, checklist)
    record("facts_and_applicability_constraints", facts.extractor_version, facts.model_dump(mode="json"))
    all_checks = (AgentPresenceCheck(),) + tuple(checks)
    if len({c.name for c in all_checks}) != len(all_checks):
        raise ValueError("Check names must be unique within a run")
    if any(c.phase not in ("pre_evaluation", "post_validation") for c in all_checks):
        raise ValueError("Unknown extension check phase")

    def run_checks(phase, evaluation):
        for check in all_checks:
            if check.phase != phase:
                continue
            # Each extension receives a private snapshot, not mutable pipeline state.
            context = CheckInput(conversation=conversation, checklist=checklist,
                                 facts=facts, evaluation=evaluation).model_copy(deep=True)
            outcome = check.run(context)
            outcome = CheckOutcome.model_validate(outcome.model_dump())
            if (outcome.check_name, outcome.check_version, outcome.phase) != (
                    check.name, check.version, check.phase):
                raise ValueError("Check outcome identity does not match registered component")
            if any(set(f.criterion_ids) - {c.criterion_id for c in checklist.criteria}
                   for f in outcome.findings):
                raise ValueError("Check finding cites unknown checklist criteria")
            outcomes.append(outcome)
            state = "blocked" if any(f.severity == "block" for f in outcome.findings) else (
                "review" if any(f.severity == "review" for f in outcome.findings) else "passed")
            record(phase + ":" + check.name, check.version, outcome.model_dump(mode="json"), state)
            if state == "blocked":
                raise CheckBlocked(outcomes.copy(), evaluation, audit.copy())

    run_checks("pre_evaluation", None)
    request, prompt_hash = build_request(conversation, checklist, facts)
    reply = provider.evaluate(conversation, checklist, request, config)
    raw = parse_json(reply.evaluation) if isinstance(reply.evaluation, (str, bytes)) else reply.evaluation
    record("primary_atomic_evaluation", config.prompt_version, raw)
    model_evaluation = validate_evaluation(ModelEvaluation.model_validate(raw), conversation, checklist)
    record("schema_evidence_consistency_validation", "gates-v1", model_evaluation.model_dump(mode="json"))
    run_checks("post_validation", model_evaluation)
    score = score_evaluation(model_evaluation, conversation, checklist)
    record("official_deterministic_scoring", "rational-v1", score.model_dump(mode="json"))
    status = "mock_only" if provider.is_mock else (
        "needs_review" if any(d.needs_review for d in model_evaluation.decisions)
        or any(f.severity == "review" for o in outcomes for f in o.findings) else "structurally_valid")
    return EvaluationResult(
        evaluation_id=str(uuid4()), status=status, conversation=conversation, checklist=checklist,
        model_evaluation=model_evaluation, score=score, revision_history=[],
        facts=facts, check_outcomes=outcomes, audit=audit,
        run=RunMetadata(engine_version=__version__, provider=provider.name,
                        python_version=platform.python_version(), pydantic_version=pydantic.__version__,
                        model_requested=provider.model, model_returned=reply.model, is_mock=provider.is_mock,
                        started_at=started_at, latency_ms=round((time.perf_counter() - started) * 1000),
                        provider_latency_ms=reply.latency_ms, response_id=reply.response_id,
                        usage=reply.usage or {}, prompt_sha256=prompt_hash,
                        checklist_sha256=digest(checklist.model_dump(mode="json")), configuration=config))
