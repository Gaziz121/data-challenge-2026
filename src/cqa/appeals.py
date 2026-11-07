"""Appeals and reviewer decisions over immutable evaluation results.

The saved EvaluationResult is never modified. Each appeal is its own JSON record with an
append-only event history. A revised view re-applies reviewer changes to the original raw
responses and recalculates with the same official arithmetic (scoring.score_responses).
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
import uuid

from .scoring import score_responses

STATES = ("open", "upheld", "revised")
NAME = re.compile(r"^[^\x00-\x1f]{1,80}$")


class AppealError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def original_responses(result):
    evaluation = result.validated_evaluation or result.model_evaluation
    return {d.criterion_id: d.response for d in evaluation.decisions}


def _clean_text(value, field, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise AppealError("%s must be nonempty text of at most %d characters" % (field, maximum))
    return value.strip()


def _clean_name(value, field):
    value = _clean_text(value, field, 80)
    if not NAME.match(value):
        raise AppealError("%s contains control characters" % field)
    return value


def _check_response(checklist, criterion_id, response):
    criterion = next((c for c in checklist.criteria if c.criterion_id == criterion_id), None)
    if criterion is None:
        raise AppealError("Criterion is not part of this evaluation's checklist")
    permitted = (list(criterion.levels) if criterion.kind == "discrete" else ["yes", "no"]) + (
        ["N/A"] if criterion.na_condition is not None else [])
    if response not in permitted or isinstance(response, bool):
        raise AppealError("Response %r is outside the scale of criterion %s (permitted: %s)"
                          % (response, criterion_id, permitted))
    return response


class AppealStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self._lock = threading.RLock()

    def _path(self, appeal_id):
        if not re.fullmatch(r"[0-9a-f-]{36}", appeal_id or ""):
            raise LookupError("Appeal not found")
        return self.directory / (appeal_id + ".json")

    def _write(self, appeal, new=False):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = self._path(appeal["appeal_id"])
        text = json.dumps(appeal, ensure_ascii=False, indent=2) + "\n"
        if new:
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as h:
                h.write(text)
            return
        temporary = target.with_suffix(".tmp")
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as h:
            h.write(text)
        os.replace(temporary, target)

    def get(self, appeal_id):
        path = self._path(appeal_id)
        if not path.is_file():
            raise LookupError("Appeal not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, evaluation_id=None):
        if not self.directory.exists():
            return []
        appeals = [json.loads(p.read_text(encoding="utf-8")) for p in self.directory.glob("*.json")]
        if evaluation_id is not None:
            appeals = [a for a in appeals if a["evaluation_id"] == evaluation_id]
        return sorted(appeals, key=lambda a: (a["submitted_at"], a["appeal_id"]))

    def submit(self, result, criterion_id, explanation, submitted_by, requested_response=None):
        if not isinstance(criterion_id, str):
            raise AppealError("criterion_id must be a string")
        responses = original_responses(result)
        if criterion_id not in responses:
            raise AppealError("Criterion is not part of this evaluation")
        if requested_response is not None:
            _check_response(result.checklist, criterion_id, requested_response)
        explanation = _clean_text(explanation, "explanation", 4000)
        submitted_by = _clean_name(submitted_by, "submitted_by")
        with self._lock:
            if any(a["criterion_id"] == criterion_id and a["state"] == "open"
                   for a in self.list(result.evaluation_id)):
                raise AppealError("An open appeal already exists for this criterion")
            now = _now()
            appeal = {"schema": "cqa-appeal/1", "appeal_id": str(uuid.uuid4()),
                      "evaluation_id": result.evaluation_id,
                      "conversation_id": result.conversation.conversation_id,
                      "checklist_id": result.checklist.checklist_id, "checklist_version": result.checklist.version,
                      "criterion_id": criterion_id, "original_response": responses[criterion_id],
                      "requested_response": requested_response, "explanation": explanation,
                      "submitted_by": submitted_by, "submitted_at": now, "state": "open", "decision": None,
                      "history": [{"event": "submitted", "at": now, "actor": submitted_by,
                                   "requested_response": requested_response}]}
            self._write(appeal, new=True)
            return appeal

    def decide(self, appeal_id, result, reviewer, outcome, reason, new_response=None):
        if outcome not in ("confirm", "change"):
            raise AppealError("outcome must be 'confirm' or 'change'")
        reviewer = _clean_name(reviewer, "reviewer")
        reason = _clean_text(reason, "reason", 4000)
        with self._lock:
            appeal = self.get(appeal_id)
            if appeal["evaluation_id"] != result.evaluation_id:
                raise AppealError("Appeal does not belong to this evaluation")
            if appeal["state"] != "open":
                raise AppealError("Appeal already decided; submit a new appeal to reopen")
            if reviewer.casefold() == appeal["submitted_by"].casefold():
                raise AppealError("The reviewer must be a different person from the appellant")
            if outcome == "change":
                _check_response(result.checklist, appeal["criterion_id"], new_response)
                if new_response == appeal["original_response"]:
                    raise AppealError("A change must differ from the original response; use confirm")
            else:
                new_response = appeal["original_response"]
            now = _now()
            appeal["state"] = "revised" if outcome == "change" else "upheld"
            appeal["decision"] = {"outcome": outcome, "reviewer": reviewer, "reason": reason,
                                  "final_response": new_response, "decided_at": now}
            appeal["history"].append({"event": "decided", "at": now, "actor": reviewer, "outcome": outcome,
                                      "final_response": new_response})
            self._write(appeal)
            return appeal

    def revised_view(self, result):
        """Original versus revised score; the original result object is not changed."""
        original = original_responses(result)
        revised = dict(original)
        applied = []
        decided = [a for a in self.list(result.evaluation_id) if a["state"] == "revised"]
        for appeal in sorted(decided, key=lambda a: a["decision"]["decided_at"]):
            revised[appeal["criterion_id"]] = appeal["decision"]["final_response"]
            applied.append({"appeal_id": appeal["appeal_id"], "criterion_id": appeal["criterion_id"],
                            "from": original[appeal["criterion_id"]], "to": appeal["decision"]["final_response"],
                            "reviewer": appeal["decision"]["reviewer"]})
        critical_ids = {c.criterion_id for c in result.checklist.criteria if c.kind == "critical"}
        categories = [] if any(revised[c] == "no" for c in critical_ids) else result.score.violation_categories
        score = score_responses(revised, result.checklist, categories)
        return {"evaluation_id": result.evaluation_id, "original_score": result.score.model_dump(mode="json"),
                "revised_score": score.model_dump(mode="json") if applied else None,
                "original_responses": original, "revised_responses": revised, "applied": applied,
                "appeals": self.list(result.evaluation_id)}
