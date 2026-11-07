"""Strict, engine-independent validator for results/{dev,prod}/results.json.

    PYTHONPATH=src python3 -m cqa_results.validate --set dev \
        --dataset data/raw/DEV_conversations.json results/dev/results.json [--submission]

Exit status 0 only when no error is found. Output is a JSON report that names
paths and reasons, never transcript text. Stdlib only.
"""

import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

from .contract import (BY_OFFICIAL, MODEL_MODES, OFFICIAL_IDS, PLACEHOLDERS, SCHEMA_VERSION,
                       SET_COUNTS, exact_score, is_bool, is_int, round_half_up_2dp, value_issue)

TOP_KEYS = {"schema_version", "team_name", "model", "results"}
OK_KEYS = {"conversation_id", "status", "criteria", "score"}
ERROR_KEYS = OK_KEYS | {"error"}
CRITERION_KEYS = {"criterion_id", "value", "rationale", "evidence_turns"}
SCORE_KEYS = {"final_score", "critical_flag"}
DRYRUN_MARKERS = ("mock", "fixture", "dryrun", "dry-run", "scripted", "synthetic", "simulated")
DIGIT_RUN = re.compile(r"\d[\d \-]{5,}\d")
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[A-Za-z]{2,}")


class StrictJSONError(ValueError):
    pass


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise StrictJSONError("duplicate JSON object key")
        result[key] = value
    return result


def _constant(name):
    raise StrictJSONError("nonstandard JSON constant " + name)


def strict_load(raw):
    """UTF-8 (no BOM), RFC 8259 JSON: no comments, trailing commas, NaN or duplicate keys."""
    if raw.startswith(b"\xef\xbb\xbf"):
        raise StrictJSONError("UTF-8 byte-order mark is not allowed")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise StrictJSONError("file is not valid UTF-8") from None
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=Decimal)
    except StrictJSONError:
        raise
    except ValueError as error:
        raise StrictJSONError("invalid JSON: %s" % error) from None


def load_dataset_index(path):
    """Ordered (conversation_id, transcript length) from an organizer envelope file."""
    value = strict_load(Path(path).read_bytes())
    data = value.get("data") if isinstance(value, dict) else None
    if (not isinstance(value, dict) or value.get("isSuccess") is not True or value.get("error") != ""
            or not isinstance(data, dict) or not isinstance(data.get("records"), list)):
        raise ValueError("dataset is not an organizer envelope {isSuccess, error, data.records}")
    records = data["records"]
    if type(data.get("total_records")) is not int or data["total_records"] != len(records):
        raise ValueError("dataset total_records differs from the actual record count")
    index = []
    for record in records:
        cid = record.get("conversation_id") if isinstance(record, dict) else None
        transcript = record.get("transcript") if isinstance(record, dict) else None
        if not isinstance(cid, str) or not cid.strip() or not isinstance(transcript, list) or not transcript:
            raise ValueError("dataset record lacks a conversation_id or nonempty transcript")
        index.append((cid, len(transcript)))
    if len({cid for cid, _ in index}) != len(index):
        raise ValueError("dataset contains duplicate conversation IDs")
    return index, data.get("dataset_group_id")


def validate_submission(value, dataset_index, set_name, *, submission=False, expected_team=None,
                        output_path=None):
    """Return {valid, errors, warnings, summary}. `value` is the strictly parsed JSON."""
    errors, warnings = [], []

    def err(path, message):
        errors.append("%s: %s" % (path, message))

    if set_name not in SET_COUNTS:
        raise ValueError("set must be dev or prod")
    if not isinstance(value, dict):
        err("$", "top level must be one JSON object")
        return _report(errors, warnings, {})
    if set(value) != TOP_KEYS:
        err("$", "keys must be exactly %s (missing %s, extra %s)" % (
            sorted(TOP_KEYS), sorted(TOP_KEYS - set(value)), sorted(set(value) - TOP_KEYS)))
    if value.get("schema_version") != SCHEMA_VERSION:
        err("$.schema_version", 'must be the string "1.0"')
    team = value.get("team_name")
    if not isinstance(team, str) or team.strip() in PLACEHOLDERS or team != team.strip():
        err("$.team_name", "must be the actual nonempty team name, not a placeholder")
    elif expected_team is not None and team != expected_team:
        err("$.team_name", "does not equal the expected team name")
    model = value.get("model")
    if not isinstance(model, dict) or set(model) != {"mode", "name"}:
        err("$.model", 'must be an object with exactly "mode" and "name"')
    else:
        if model.get("mode") not in MODEL_MODES:
            err("$.model.mode", "must be one of %s" % list(MODEL_MODES))
        name = model.get("name")
        if not isinstance(name, str) or name.strip() in PLACEHOLDERS:
            err("$.model.name", "must name the model(s) actually used")
        elif any(m in name.lower() for m in DRYRUN_MARKERS):
            message = "names a mock/dry-run fixture; not a genuine evaluation"
            if submission:
                err("$.model.name", message)
            else:
                warnings.append("$.model.name: " + message)
    if submission and output_path is not None:
        parts = Path(output_path).resolve().parts
        if parts[-3:] != ("results", set_name, "results.json"):
            err("$file", "submission file must be results/%s/results.json" % set_name)

    results = value.get("results")
    summary = {"records": 0, "ok": 0, "error": 0, "na_values": 0, "critical_true": 0}
    if not isinstance(results, list):
        err("$.results", "must be an array")
        return _report(errors, warnings, summary)
    expected_ids = [cid for cid, _ in dataset_index]
    lengths = dict(dataset_index)
    summary["records"] = len(results)
    if len(results) != SET_COUNTS[set_name]:
        err("$.results", "%s requires exactly %d records, found %d" % (set_name, SET_COUNTS[set_name], len(results)))
    if len(expected_ids) != SET_COUNTS[set_name]:
        err("$dataset", "source dataset has %d conversations; %s requires %d" % (
            len(expected_ids), set_name, SET_COUNTS[set_name]))
    seen = []
    for i, record in enumerate(results):
        path = "$.results[%d]" % i
        if not isinstance(record, dict):
            err(path, "must be an object")
            continue
        cid = record.get("conversation_id")
        if not isinstance(cid, str) or not cid:
            err(path + ".conversation_id", "must be a nonempty string")
            continue
        seen.append(cid)
        if cid not in lengths:
            err(path + ".conversation_id", "is not a conversation ID in the source dataset")
        status = record.get("status")
        if status == "ok":
            _validate_ok(record, path, lengths.get(cid), err, warnings, summary)
        elif status == "error":
            summary["error"] += 1
            if set(record) != ERROR_KEYS:
                err(path, "error record keys must be exactly %s" % sorted(ERROR_KEYS))
            if record.get("criteria") != []:
                err(path + ".criteria", "must be [] for status error")
            if "score" not in record or record.get("score") is not None:
                err(path + ".score", "must be null for status error")
            reason = record.get("error")
            if not isinstance(reason, str) or not reason.strip():
                err(path + ".error", "must state the actual reason")
        else:
            err(path + ".status", 'must be "ok" or "error"')
    duplicates = sorted({c for c in seen if seen.count(c) > 1})
    if duplicates:
        err("$.results", "duplicate conversation IDs: %s" % duplicates)
    missing = [c for c in expected_ids if c not in set(seen)]
    if missing:
        err("$.results", "source conversations missing from results: %s" % missing)
    if not duplicates and not missing and seen != expected_ids and set(seen) == set(expected_ids):
        err("$.results", "records must follow the original source dataset order")
    if summary["error"]:
        warnings.append("%d record(s) have status error; they are reported, not scored" % summary["error"])
    return _report(errors, warnings, summary)


def _validate_ok(record, path, length, err, warnings, summary):
    summary["ok"] += 1
    if set(record) != OK_KEYS:
        err(path, "ok record keys must be exactly %s" % sorted(OK_KEYS))
    criteria = record.get("criteria")
    if not isinstance(criteria, list):
        err(path + ".criteria", "must be an array")
        return
    ids = [c.get("criterion_id") if isinstance(c, dict) else None for c in criteria]
    if ids != list(OFFICIAL_IDS):
        err(path + ".criteria", "must contain all eight criteria exactly once in order %s" % list(OFFICIAL_IDS))
    values = {}
    for j, item in enumerate(criteria):
        cpath = "%s.criteria[%d]" % (path, j)
        if not isinstance(item, dict):
            err(cpath, "must be an object")
            continue
        if set(item) != CRITERION_KEYS:
            err(cpath, "keys must be exactly %s" % sorted(CRITERION_KEYS))
        cid = item.get("criterion_id")
        if cid not in BY_OFFICIAL:
            err(cpath + ".criterion_id", "unknown official criterion ID")
            continue
        issue = value_issue(cid, item.get("value"))
        if issue:
            err(cpath + ".value", issue)
        elif cid not in values:
            values[cid] = item.get("value")
            summary["na_values"] += item.get("value") is None
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            err(cpath + ".rationale", "must be a nonempty explanation")
        else:
            if len(rationale) > 600:
                warnings.append("%s.rationale: longer than 600 characters; appendix asks for a short explanation" % cpath)
            if DIGIT_RUN.search(rationale) or EMAIL.search(rationale):
                warnings.append("%s.rationale: contains a long digit run or e-mail; review for personal data before a public push" % cpath)
        turns = item.get("evidence_turns")
        if not isinstance(turns, list) or not turns:
            err(cpath + ".evidence_turns", "must be a nonempty array of 1-based transcript indexes")
        else:
            if any(not is_int(t) for t in turns):
                err(cpath + ".evidence_turns", "indexes must be JSON integers")
            elif length is not None and any(t < 1 or t > length for t in turns):
                err(cpath + ".evidence_turns", "index outside original transcript range 1..%d" % length)
            elif any(t < 1 for t in turns):
                err(cpath + ".evidence_turns", "indexes start at 1")
            if len(set(map(repr, turns))) != len(turns):
                err(cpath + ".evidence_turns", "duplicate indexes")
    score = record.get("score")
    if not isinstance(score, dict) or set(score) != SCORE_KEYS:
        err(path + ".score", "must be an object with exactly final_score and critical_flag")
        return
    final, flag = score.get("final_score"), score.get("critical_flag")
    if is_bool(final) or not isinstance(final, (int, Decimal)):
        err(path + ".score.final_score", "must be a JSON number")
    elif not Decimal(0) <= Decimal(final) <= Decimal(100):
        err(path + ".score.final_score", "must be between 0 and 100")
    elif (Decimal(final) * 100) % 1 != 0:
        err(path + ".score.final_score", "must be rounded to two decimals")
    elif len(values) == len(OFFICIAL_IDS):
        expected = exact_score(values)
        if expected is None:
            err(path + ".score.final_score", "no applicable weighted criterion; score undefined")
        elif round_half_up_2dp(expected) != Decimal(final):
            err(path + ".score.final_score", "is %s; official weighting with N/A redistribution gives %s" % (
                final, round_half_up_2dp(expected)))
    if not is_bool(flag):
        err(path + ".score.critical_flag", "must be a JSON boolean")
    elif "critical" in values and flag != values["critical"]:
        err(path + ".score.critical_flag", "must equal the critical criterion value")
    if values.get("critical") is True:
        summary["critical_true"] += 1


def _report(errors, warnings, summary):
    return {"valid": not errors, "errors": errors, "warnings": warnings, "summary": summary}


def validate_file(path, dataset_path, set_name, **options):
    try:
        value = strict_load(Path(path).read_bytes())
    except (StrictJSONError, OSError) as error:
        return _report(["$file: %s" % error], [], {})
    index, _ = load_dataset_index(dataset_path)
    return validate_submission(value, index, set_name, output_path=path, **options)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", type=Path)
    parser.add_argument("--set", required=True, choices=sorted(SET_COUNTS))
    parser.add_argument("--dataset", required=True, type=Path, help="The exact source envelope that was evaluated")
    parser.add_argument("--team-name", help="Fail unless team_name equals this value")
    parser.add_argument("--submission", action="store_true",
                        help="Final check: also reject mock/dry-run model names and a non-official file path")
    args = parser.parse_args(argv)
    try:
        report = validate_file(args.results, args.dataset, args.set, submission=args.submission,
                               expected_team=args.team_name)
    except (OSError, ValueError) as error:
        report = _report(["$dataset: %s" % error], [], {})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
