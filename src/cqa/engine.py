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
from .prompt import build_request, PROMPT_VERSION
from .evidence import normalize_evidence
from .coverage import assess_output
from .atomic import AtomicReviewRequired, process_atomic_output
from .atomic_prompt import PROMPT_VERSION as ATOMIC_PROMPT_VERSION, ATOMIC_PROMPT_VERSIONS
from .schemas import (Checklist, Conversation, EvaluationConfig, EvaluationResult,
                      ModelEvaluation, RunMetadata, CheckInput, CheckOutcome, AuditEvent, RepairPolicy)
from .scoring import score_evaluation
from .repair import REPAIR_PROMPT_VERSION, attempt_repair
from .validation import validate_evaluation, _validate_decision, diagnose_decision


class CheckBlocked(ValueError):
    """A gate stops scoring and retains maker output if already produced."""

    def __init__(self, outcomes, original_evaluation, audit):
        super().__init__("Evaluation blocked by an extension check; no score produced")
        self.check_outcomes = outcomes
        self.original_evaluation = original_evaluation
        self.audit = audit


class EvaluationRejected(ValueError):
    """Keep the original model reply and diagnostics; never calculate a partial total."""
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        super().__init__("Evaluation validation failed; original reply retained without a score")


def diagnose_output(raw, conversation, checklist):
    """Inspect each original decision for diagnostics only. Never calculate a score."""
    if not isinstance(raw, dict) or not isinstance(raw.get("decisions"), list):
        return [{"criterion_id": None, "message": "Invalid model schema or JSON"}], []
    expected = {c.criterion_id: c for c in checklist.criteria}
    messages = {m.message_id: m for m in conversation.messages}
    issues, statuses, seen = [], [], []
    try:
        ModelEvaluation.model_validate(raw)
    except pydantic.ValidationError as error:
        issues.extend({"criterion_id": None, "location": list(e["loc"]), "message": e["msg"]}
                      for e in error.errors(include_input=False, include_context=False)
                      if not e["loc"] or e["loc"][0] != "decisions")
    for item in raw["decisions"]:
        cid = item.get("criterion_id") if isinstance(item, dict) else None
        if not isinstance(cid, str):
            cid = None
        seen.append(cid)
        local = []
        if cid not in expected:
            local.append({"criterion_id": cid, "message": "Unknown or missing criterion ID"})
        else:
            local.extend(diagnose_decision(item, expected[cid], conversation, messages))
        issues.extend(local)
        statuses.append({"criterion_id": cid, "status": "invalid" if local else "validated"})
    if len(seen) != len(set(seen)) or set(seen) != set(expected):
        issues.append({"criterion_id": None, "message": "Every configured criterion is required exactly once"})
    return issues, statuses


def evaluate(conversation, checklist, provider, config=None, checks=(), repair=None):
    """`repair` is an explicit RepairPolicy; None (default) disables any extra call."""
    config = EvaluationConfig.model_validate((config or EvaluationConfig()).model_dump())
    atomic_path = checklist.decision_path == "atomic_first"
    if repair is not None:
        repair = RepairPolicy.model_validate(repair.model_dump())
        if not atomic_path:
            raise ValueError("Bounded repair applies only to the atomic_first decision path")
    repair_attempts = []
    if atomic_path:
        # atomic-v2 remains the compatibility default; atomic-v3 is explicit opt-in.
        version = config.prompt_version if config.prompt_version in ATOMIC_PROMPT_VERSIONS else ATOMIC_PROMPT_VERSION
        config = config.model_copy(update={"prompt_version": version})
    elif config.prompt_version != PROMPT_VERSION:
        raise ValueError("Requested prompt version is not the active implementation")
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
    request, prompt_hash = build_request(conversation, checklist, facts,
                                         config.prompt_version if atomic_path else None)
    reply = provider.evaluate(conversation, checklist, request, config)
    def run_metadata():
        return RunMetadata(engine_version=__version__, provider=provider.name,
                           python_version=platform.python_version(), pydantic_version=pydantic.__version__,
                           model_requested=provider.model, model_returned=reply.model, is_mock=provider.is_mock,
                           started_at=started_at, latency_ms=round((time.perf_counter() - started) * 1000),
                           provider_latency_ms=reply.latency_ms, response_id=reply.response_id,
                           usage=reply.usage or {}, prompt_sha256=prompt_hash,
                           checklist_sha256=digest(checklist.model_dump(mode="json")), configuration=config)
    raw = reply.evaluation
    rule_checks, coverage_proofs = [], []
    criterion_reviews = []
    projection = None
    try:
        raw = parse_json(reply.evaluation) if isinstance(reply.evaluation, (str, bytes)) else reply.evaluation
        record("primary_atomic_evaluation", config.prompt_version, raw)
        if atomic_path:
            try:
                projection, criterion_reviews = process_atomic_output(raw, conversation, checklist)
            except AtomicReviewRequired as first:
                if repair is None:
                    raise
                # Exactly one bounded attempt; the primary reply is never modified.
                attempt, merged = attempt_repair(repair, provider, conversation, checklist, config,
                                                 raw, first.reviews, first.issues)
                repair_attempts.append(attempt)
                record("bounded_criterion_repair", REPAIR_PROMPT_VERSION, attempt.model_dump(mode="json"), "review")
                if merged is None:
                    raise
                projection, criterion_reviews = process_atomic_output(merged, conversation, checklist)
            record("validated_facts_to_official_decisions", "atomic-v1",
                   [r.model_dump(mode="json") for r in criterion_reviews])
        if atomic_path:
            _, coverage_proofs = assess_output(projection.model_dump(), conversation, checklist)
        else:
            rule_checks, coverage_proofs = assess_output(raw, conversation, checklist)
        record("decision_rules_and_source_coverage", "rules-coverage-v1",
               {"decision_rule_checks": [c.model_dump(mode="json") for c in rule_checks],
                "coverage_proofs": [p.model_dump(mode="json") for p in coverage_proofs]},
               "blocked" if any(c.status == "disagreed" or c.issues for c in rule_checks)
               or any(not p.complete for p in coverage_proofs) else "passed")
        original = projection or ModelEvaluation.model_validate(raw)
        model_evaluation, repairs = (normalize_evidence(original, conversation)
                                     if config.quote_policy == "normalize_formatting" else (original, []))
        model_evaluation = validate_evaluation(model_evaluation, conversation, checklist)
    except ValueError as error:
        if isinstance(error, AtomicReviewRequired):
            criterion_reviews = error.reviews
            issues = error.issues
            statuses = [{"criterion_id": r.criterion_id, "status": "validated" if r.state.startswith("accepted_") else "invalid"}
                        for r in criterion_reviews]
            _, coverage_proofs = assess_output({"decisions": [d.model_dump() for d in error.accepted]}, conversation, checklist)
        else:
            issues, statuses = diagnose_output(projection.model_dump() if projection else raw, conversation, checklist)
        if not issues:
            issues = [{"criterion_id": None, "message": "Invalid model schema or evidence"}]
        raise EvaluationRejected({"schema_version": "1.0", "diagnostic_id": str(uuid4()),
                                  "status": "validation_failed", "original_model_output": reply.evaluation,
                                  "issues": issues, "criterion_validation": statuses,
                                  "run": run_metadata().model_dump(mode="json"),
                                  "conversation": conversation.model_dump(mode="json"),
                                  "checklist": checklist.model_dump(mode="json"),
                                  "decision_rule_checks": [c.model_dump(mode="json") for c in rule_checks],
                                  "coverage_proofs": [p.model_dump(mode="json") for p in coverage_proofs],
                                  "decision_path": checklist.decision_path,
                                  "criterion_reviews": [r.model_dump(mode="json") for r in criterion_reviews],
                                  "validated_criteria": [d.model_dump(mode="json") for d in error.accepted] if isinstance(error, AtomicReviewRequired) else [],
                                  "repair_attempts": [a.model_dump(mode="json") for a in repair_attempts],
                                  "audit": [a.model_dump(mode="json") for a in audit]}) from None
    if repairs:
        record("evidence_formatting_resolution", "formatting-v1", [r.model_dump(mode="json") for r in repairs])
    record("schema_evidence_consistency_validation", "gates-v2", model_evaluation.model_dump(mode="json"))
    run_checks("post_validation", model_evaluation)
    score = score_evaluation(model_evaluation, conversation, checklist)
    record("official_deterministic_scoring", "rational-v1", score.model_dump(mode="json"))
    status = "mock_only" if provider.is_mock else (
        "needs_review" if any(d.needs_review for d in model_evaluation.decisions) or repair_attempts
        or any(f.severity == "review" for o in outcomes for f in o.findings) else "structurally_valid")
    return EvaluationResult(
        evaluation_id=str(uuid4()), status=status, conversation=conversation, checklist=checklist,
        model_evaluation=original, validated_evaluation=model_evaluation,
        evidence_repairs=repairs, score=score, revision_history=[],
        decision_rule_checks=rule_checks, coverage_proofs=coverage_proofs,
        decision_path=checklist.decision_path,
        original_provider_output=raw if atomic_path else None,
        criterion_reviews=criterion_reviews, repair_attempts=repair_attempts,
        facts=facts, check_outcomes=outcomes, audit=audit,
        run=run_metadata())
