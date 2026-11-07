"""Hand-authored test inputs, not DEV answers or human benchmark labels."""

from copy import deepcopy

from cqa.io import digest, load_checklist
from cqa.loader import normalize_record
from cqa.prompt import build_request
from cqa.providers import MockProvider
from cqa.schemas import EvaluationConfig, ModelEvaluation


def conversation(language="EN", agent=True):
    turns = [
        {"speaker": "client", "timestamp": "00:00", "text": "Where can I read the guide?"},
        {"speaker": "bot", "timestamp": "00:01", "text": "Hello, I am a bot."},
        {"speaker": "system", "timestamp": "00:01", "text": "Operator connected."},
    ]
    if agent:
        turns.append({"speaker": "operator", "timestamp": "00:02", "text": "Hello, I am Sam. Open Help. Goodbye."})
    record = {"conversation_id": "unit-example", "channel": "agent chat", "language": language,
              "transcript": turns, "audio_url": None}
    return normalize_record(record, "UNIT_TEST", digest(record))


def evaluation_data(conv=None, checklist=None):
    conv, checklist = conv or conversation(), checklist or load_checklist()
    request, _ = build_request(conv, checklist)
    raw = MockProvider().evaluate(conv, checklist, request, EvaluationConfig()).evaluation
    agent = next((m for m in conv.messages if m.role == "agent"), None)
    for decision, criterion in zip(raw["decisions"], checklist.criteria):
        decision.update(needs_review=False, review_reason=None,
                        response="no" if criterion.kind == "critical" else (
                            max(criterion.levels) if criterion.kind == "discrete" else "yes"))
        if criterion.kind != "critical" and agent:
            decision["evidence"] = [{"kind": "quote", "message_id": agent.message_id, "quote": agent.text,
                                     "start_message_id": None, "end_message_id": None,
                                     "explanation": "Hand-authored test fixture supporting the selected anchor."}]
        for atomic in decision["atomic_checks"]:
            atomic["answer"] = "no" if criterion.kind == "critical" else "yes"
        if criterion.applicability_rule:
            rule = criterion.applicability_rule
            next(a for a in decision["atomic_checks"] if a["question_id"] == rule.question_id)["answer"] = (
                "no" if rule.na_when == "yes" else "yes")
    return raw


def set_response(raw, checklist, criterion_id, response):
    decision = next(d for d in raw["decisions"] if d["criterion_id"] == criterion_id)
    criterion = next(c for c in checklist.criteria if c.criterion_id == criterion_id)
    decision["response"] = response
    decision["na_reason"] = criterion.na_condition if response == "N/A" else None
    if criterion.applicability_rule:
        rule = criterion.applicability_rule
        next(a for a in decision["atomic_checks"] if a["question_id"] == rule.question_id)["answer"] = (
            rule.na_when if response == "N/A" else ("no" if rule.na_when == "yes" else "yes"))
    return decision


def model(raw):
    return ModelEvaluation.model_validate(deepcopy(raw))
