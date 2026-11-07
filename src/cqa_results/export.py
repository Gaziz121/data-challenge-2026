"""Map engine outcomes of one batch run to the official results.json (JSON 1.0).

    PYTHONPATH=src python3 -m cqa_results.export --set dev \
        --data data/raw/DEV_conversations.json --run-dir outputs/submission/dev-run1 \
        --team-name "<team>" --output results/dev/results.json

Accepted EvaluationResults become status "ok"; engine rejections and every other
recorded failure become status "error" with criteria [] and score null. Nothing is
invented: a missing, duplicated, mismatched or malformed outcome aborts the export.
The written file is re-read and checked by the independent validator first.
"""

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import tempfile

from pydantic import ValidationError

from cqa.io import digest, parse_json
from cqa.loader import ROOT, normalize_record, read_dataset
from cqa.schemas import EvaluationResult
from cqa.scoring import score_evaluation

from .batch import RUN_SCHEMA, id_hash, scan_attempts
from .contract import CRITERIA, INTERNAL_TO_OFFICIAL, SCHEMA_VERSION, SET_COUNTS
from .validate import strict_load, validate_submission

MODES = {"openai": "external_api", "mock": "local", "scripted-dryrun": "local"}


class ExportError(ValueError):
    pass


def official_value(kind, response):
    if response == "N/A":
        return None
    if kind == "discrete":
        if type(response) is not int:
            raise ExportError("Discrete response is not an integer")
        return response
    if response not in ("yes", "no"):
        raise ExportError("Binary/critical response is not yes/no")
    return response == "yes"


def evidence_turns(evidence, conversation, transcript):
    """1-based ORIGINAL transcript indexes. Quotes map to their message; scopes and
    omission ranges map to every message they span (inclusive). Each quote is
    re-checked against the original transcript text at the mapped index."""
    position = {m.message_id: m.source_index for m in conversation.messages}
    turns = set()
    for item in evidence:
        if item.kind == "quote":
            if item.message_id not in position:
                raise ExportError("Evidence cites an unknown message ID")
            index = position[item.message_id]
            if item.quote not in transcript[index]["text"]:
                raise ExportError("Evidence quote is not in the original transcript turn it maps to")
            turns.add(index + 1)
        else:
            if item.start_message_id not in position or item.end_message_id not in position:
                raise ExportError("Evidence scope cites an unknown message ID")
            start, end = position[item.start_message_id], position[item.end_message_id]
            if start > end:
                raise ExportError("Evidence scope is reversed")
            turns.update(range(start + 1, end + 2))
    if not turns or min(turns) < 1 or max(turns) > len(transcript):
        raise ExportError("Evidence indexes fall outside the original transcript")
    return sorted(turns)


def check_checklist(checklist):
    configured = [(c.criterion_id, c.kind, c.weight, tuple(c.levels) or None, c.na_condition is not None)
                  for c in checklist.criteria]
    official = [(internal, kind, weight, levels, nullable)
                for _, internal, kind, weight, levels, nullable in CRITERIA]
    if configured != official:
        raise ExportError("Checklist %s %s does not match the official eight-criterion table" % (
            checklist.checklist_id, checklist.version))


def ok_record(result, record, group, file_hash, allow_mock):
    cid = record["conversation_id"]
    if result.conversation.conversation_id != cid:
        raise ExportError("Result conversation ID differs from the source record")
    if result.conversation.source_record_sha256 != digest(record):
        raise ExportError("Result was produced from different source content")
    expected = normalize_record(record, group, file_hash)
    if [m.model_dump() for m in result.conversation.messages] != [m.model_dump() for m in expected.messages]:
        raise ExportError("Result messages do not map one-to-one onto the original transcript")
    if result.status == "mock_only" or result.run.is_mock:
        if not allow_mock:
            raise ExportError("Mock/fixture output is not a genuine evaluation (dry runs need --allow-mock)")
    check_checklist(result.checklist)
    validated = result.validated_evaluation
    if validated is None:
        raise ExportError("Accepted result lacks a validated evaluation")
    rescored = score_evaluation(validated, result.conversation, result.checklist)
    if (rescored.total_score, rescored.critical_violation) != (result.score.total_score, result.score.critical_violation):
        raise ExportError("Stored score differs from the engine's deterministic rescoring")
    if rescored.total_score is None:
        raise ExportError("No applicable weighted criterion; engine produced no total")
    decisions = {d.criterion_id: d for d in validated.decisions}
    if sorted(decisions) != sorted(INTERNAL_TO_OFFICIAL) or len(decisions) != len(validated.decisions):
        raise ExportError("Validated evaluation does not contain each criterion exactly once")
    criteria = []
    for official, internal, kind, _, _, _ in CRITERIA:
        decision = decisions[internal]
        rationale = decision.rationale.strip()
        if not rationale:
            raise ExportError("Empty rationale")
        criteria.append({"criterion_id": official, "value": official_value(kind, decision.response),
                         "rationale": rationale,
                         "evidence_turns": evidence_turns(decision.evidence, result.conversation, record["transcript"])})
    critical = criteria[-1]["value"]
    if critical != rescored.critical_violation:
        raise ExportError("Critical value differs from the engine critical flag")
    final = float(Decimal(rescored.total_score))
    return {"conversation_id": cid, "status": "ok", "criteria": criteria,
            "score": {"final_score": final, "critical_flag": critical}}


def rejected_reason(diagnostic):
    issues = diagnostic.get("issues") or []
    names = sorted({INTERNAL_TO_OFFICIAL.get(i.get("criterion_id"), "general") for i in issues if isinstance(i, dict)})
    messages = []
    for issue in issues:
        message = issue.get("message") if isinstance(issue, dict) else None
        if isinstance(message, str) and message not in messages:
            messages.append(message)
    reason = "Evaluation rejected by engine validation gates; no score produced (%d issue(s); criteria: %s): %s" % (
        len(issues), ", ".join(names) or "general", "; ".join(messages[:3]) or "unspecified")
    return reason[:400]


def build_submission(data_path, run_dir, team_name, set_name, *, allow_mock=False, unattempted_reason=None):
    """Return (submission dict, export report). Raises ExportError on any inconsistency."""
    if set_name not in SET_COUNTS:
        raise ExportError("set must be dev or prod")
    if not isinstance(team_name, str) or not team_name.strip():
        raise ExportError("Actual team name is required")
    data, file_hash = read_dataset(data_path)
    records, group = data["records"], data["dataset_group_id"]
    run_dir = Path(run_dir)
    manifest_path = run_dir / "run.json"
    if not manifest_path.is_file():
        raise ExportError("Run directory has no run.json")
    manifest = parse_json(manifest_path.read_bytes())
    if manifest.get("schema") != RUN_SCHEMA:
        raise ExportError("Unknown run manifest schema")
    if manifest.get("dataset_sha256") != file_hash:
        raise ExportError("Run was produced from a different dataset file")
    if manifest.get("conversation_ids") != [r["conversation_id"] for r in records]:
        raise ExportError("Run conversation order differs from the dataset")
    attempts = scan_attempts(run_dir)
    keys = {(i, id_hash(r["conversation_id"])): r for i, r in enumerate(records)}
    if set(attempts) - set(keys):
        raise ExportError("Run directory has outcomes for conversations outside the dataset")
    results, models, report = [], {}, {"ok": 0, "rejected": 0, "error": 0, "unattempted": 0, "attempts": 0,
                                       "needs_review": 0}
    for index, record in enumerate(records):
        cid = record["conversation_id"]
        history = attempts.get((index, id_hash(cid)), [])
        report["attempts"] += len(history)
        if not history:
            if unattempted_reason is None:
                raise ExportError("No outcome for conversation #%d (%s); run it or pass --unattempted-reason" % (
                    index + 1, cid))
            results.append({"conversation_id": cid, "status": "error", "criteria": [], "score": None,
                            "error": unattempted_reason})
            report["unattempted"] += 1
            continue
        _, kind, path = history[-1]
        try:
            payload = parse_json(path.read_bytes())
        except ValueError:
            raise ExportError("Outcome file is not valid JSON: %s" % path.name) from None
        if kind == "result":
            try:
                result = EvaluationResult.model_validate(payload)
            except ValidationError:
                raise ExportError("Result file failed the engine result contract: %s" % path.name) from None
            results.append(ok_record(result, record, group, file_hash, allow_mock))
            models[result.run.model_returned] = result.run.provider
            report["ok"] += 1
            report["needs_review"] += result.status == "needs_review"
        elif kind == "rejected":
            conversation = payload.get("conversation") if isinstance(payload, dict) else None
            if (payload.get("status") != "validation_failed" or not isinstance(conversation, dict)
                    or conversation.get("conversation_id") != cid
                    or conversation.get("source_record_sha256") != digest(record)):
                raise ExportError("Rejected diagnostic does not belong to this source conversation: %s" % path.name)
            run = payload.get("run") or {}
            if run.get("is_mock") and not allow_mock:
                raise ExportError("Mock/fixture diagnostic in a non-dry-run export")
            models[run.get("model_returned") or run.get("model_requested")] = run.get("provider")
            results.append({"conversation_id": cid, "status": "error", "criteria": [], "score": None,
                            "error": rejected_reason(payload)})
            report["rejected"] += 1
        else:
            if payload.get("conversation_id") != cid or not str(payload.get("error", "")).strip():
                raise ExportError("Error outcome does not belong to this conversation: %s" % path.name)
            if payload.get("is_mock") and not allow_mock:
                raise ExportError("Mock/fixture error outcome in a non-dry-run export")
            results.append({"conversation_id": cid, "status": "error", "criteria": [], "score": None,
                            "error": payload["error"].strip()[:400]})
            report["error"] += 1
    if not models:  # Nothing reached a provider; report the configured model honestly.
        models[manifest.get("model_requested")] = manifest.get("provider")
    if None in models or any(p not in MODES for p in models.values()):
        raise ExportError("Cannot determine the provider/model actually used")
    modes = {MODES[p] for p in models.values()}
    submission = {"schema_version": SCHEMA_VERSION, "team_name": team_name.strip(),
                  "model": {"mode": modes.pop() if len(modes) == 1 else "hybrid", "name": ", ".join(sorted(models))},
                  "results": results}
    return submission, report


def serialize(submission):
    return (json.dumps(submission, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write_submission(submission, output, data_path, set_name, *, allow_mock=False, overwrite=False):
    """Validate the exact bytes, then atomically place them. Dry runs stay under outputs/."""
    output = Path(output)
    if allow_mock and (ROOT / "outputs").resolve() not in output.resolve().parents:
        raise ExportError("Dry-run/mock exports may only be written under outputs/, never results/")
    if output.exists() and not overwrite:
        raise ExportError("Output exists; pass --overwrite to replace it deliberately")
    raw = serialize(submission)
    from .validate import load_dataset_index
    index, _ = load_dataset_index(data_path)
    report = validate_submission(strict_load(raw), index, set_name)
    if not report["valid"]:
        raise ExportError("Generated submission failed validation: %s" % report["errors"][:5])
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=output.parent, prefix=".results-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        os.replace(temporary, output)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", required=True, choices=sorted(SET_COUNTS))
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--team-name", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--allow-mock", action="store_true", help="Dry runs only; output must stay under outputs/")
    parser.add_argument("--unattempted-reason",
                        help="Last resort: record never-attempted conversations as errors with this exact reason")
    args = parser.parse_args(argv)
    try:
        submission, report = build_submission(args.data, args.run_dir, args.team_name, args.set,
                                              allow_mock=args.allow_mock, unattempted_reason=args.unattempted_reason)
        validation = write_submission(submission, args.output, args.data, args.set,
                                      allow_mock=args.allow_mock, overwrite=args.overwrite)
    except (OSError, ValueError) as error:
        print("Export refused: %s" % error, file=sys.stderr)
        return 1
    print(json.dumps({"written": str(args.output), "model": submission["model"], "export": report,
                      "validation": validation["summary"], "warnings": validation["warnings"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
