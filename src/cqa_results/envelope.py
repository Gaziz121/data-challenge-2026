"""Control-set intake: fetch exact bytes, check the envelope, bounded re-wrapping.

    # Fetch with the organizer-provided URL kept in an environment variable (never logged):
    PYTHONPATH=src python3 -B -m cqa_results.envelope fetch --url-env CONTROL_URL \
        --out data/raw/PROD_control.json [--header-env CONTROL_AUTH_HEADER]
    # Structure-only report (no transcript text is printed):
    PYTHONPATH=src python3 -B -m cqa_results.envelope check data/raw/PROD_control.json --expect-count 10
    # Only if the organizer shape differs in its OUTER wrapper (records themselves unchanged):
    PYTHONPATH=src python3 -B -m cqa_results.envelope wrap data/raw/PROD_control.json \
        --out data/raw/PROD_control_envelope.json --group-id <organizer group id or PROD_CONTROL>

No endpoint, credential or payload shape is assumed. `wrap` only moves an existing record
array into the DEV envelope {isSuccess, error, data:{dataset_group_id,total_records,records}};
it never edits, drops, merges or reorders records or turns. Anything else is refused so a
human writes an explicit, reviewed conversion.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

from cqa.io import parse_json

KNOWN_SPEAKERS = {"client", "operator", "bot", "system"}
KNOWN_TURN_KEYS = {"timestamp", "speaker", "text", "message_id"}
KNOWN_RECORD_KEYS = {"conversation_id", "channel", "language", "transcript", "audio_url"}


def records_of(value):
    """Return (records, wrapper) for the DEV envelope or a bounded set of outer wrappers."""
    if isinstance(value, dict) and isinstance(value.get("data"), dict) and isinstance(value["data"].get("records"), list):
        return value["data"]["records"], "dev_envelope"
    if isinstance(value, list):
        return value, "bare_list"
    if isinstance(value, dict) and isinstance(value.get("records"), list):
        return value["records"], "records_key"
    if isinstance(value, dict) and isinstance(value.get("data"), list):
        return value["data"], "data_list"
    raise ValueError("Unrecognized envelope: write an explicit reviewed conversion")


def inspect(value, expect_count=None):
    """Structure-only report. Never includes transcript text or URLs."""
    problems = []
    records, wrapper = records_of(value)
    if wrapper == "dev_envelope":
        if value.get("isSuccess") is not True:
            problems.append("isSuccess is not true")
        if value.get("error") not in ("", None):
            problems.append("envelope error field is not empty")
        if value["data"].get("total_records") != len(records):
            problems.append("total_records does not equal the number of records")
        if not value["data"].get("dataset_group_id"):
            problems.append("dataset_group_id missing")
    else:
        problems.append("outer wrapper is %s, not the DEV envelope; use `wrap`" % wrapper)
    ids = [r.get("conversation_id") if isinstance(r, dict) else None for r in records]
    if any(not isinstance(i, str) or not i for i in ids):
        problems.append("a record has no string conversation_id")
    duplicates = sorted(i for i, n in Counter(ids).items() if n > 1 and isinstance(i, str))
    if duplicates:
        problems.append("duplicate conversation_id values: %d" % len(duplicates))
    if expect_count is not None and len(records) != expect_count:
        problems.append("expected %d records, found %d" % (expect_count, len(records)))
    record_keys, speakers, turn_keys, channels, languages = Counter(), Counter(), Counter(), Counter(), Counter()
    turns = []
    for r in records:
        if not isinstance(r, dict):
            problems.append("a record is not an object")
            continue
        record_keys.update(list(r))
        channels[r.get("channel")] += 1
        languages[r.get("language")] += 1
        transcript = r.get("transcript")
        if not isinstance(transcript, list) or not transcript:
            problems.append("record %s has no transcript array" % r.get("conversation_id"))
            continue
        turns.append(len(transcript))
        for t in transcript:
            if isinstance(t, dict):
                speakers[t.get("speaker")] += 1
                turn_keys.update(list(t))
    unknown_speakers = sorted(str(s) for s in speakers if s not in KNOWN_SPEAKERS)
    unknown_turn_keys = sorted(k for k in turn_keys if k not in KNOWN_TURN_KEYS)
    unknown_record_keys = sorted(k for k in record_keys if k not in KNOWN_RECORD_KEYS)
    if unknown_speakers:
        problems.append("unknown speakers %s: the engine fails closed; map them explicitly" % unknown_speakers)
    if unknown_turn_keys or unknown_record_keys:
        problems.append("unknown fields record=%s turn=%s: the engine fails closed; review before mapping"
                        % (unknown_record_keys, unknown_turn_keys))
    return {"wrapper": wrapper, "records": len(records), "conversation_ids": ids,
            "channels": dict(Counter(str(k) for k in channels.elements())),
            "languages": dict(Counter(str(k) for k in languages.elements())),
            "speakers": {str(k): v for k, v in speakers.items()}, "turn_keys": sorted(turn_keys),
            "record_keys": sorted(record_keys), "turns_min_max": [min(turns), max(turns)] if turns else None,
            "problems": problems, "ok": not problems}


def wrap(value, group_id):
    records, wrapper = records_of(value)
    if wrapper == "dev_envelope":
        return value
    if not group_id:
        raise ValueError("--group-id is required to wrap a non-envelope payload")
    return {"isSuccess": True, "error": "",
            "data": {"dataset_group_id": group_id, "total_records": len(records), "records": records}}


def _write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
        handle.write(data)


def fetch(url, out, header=None, timeout=60):
    """GET the organizer URL once and save the exact response bytes. Prints no URL or token."""
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "cqa-results-intake"})
    if header:
        name, _, value = header.partition(":")
        if not name.strip() or not value.strip():
            raise ValueError("Header must look like 'Name: value'")
        request.add_header(name.strip(), value.strip())
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL supplied by the operator
        body = response.read()
        status = response.status
    _write_new(out, body)
    return {"status": status, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "saved": str(out)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--url-env", required=True, help="Name of the environment variable holding the URL")
    f.add_argument("--header-env", help="Name of an environment variable holding one 'Name: value' header")
    f.add_argument("--out", required=True, type=Path)
    c = sub.add_parser("check")
    c.add_argument("path", type=Path)
    c.add_argument("--expect-count", type=int)
    c.add_argument("--show-ids", action="store_true")
    w = sub.add_parser("wrap")
    w.add_argument("path", type=Path)
    w.add_argument("--out", required=True, type=Path)
    w.add_argument("--group-id")
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            url = os.environ.get(args.url_env, "")
            if not url.startswith("https://"):
                raise ValueError("Environment variable %s must hold an https:// URL" % args.url_env)
            header = os.environ.get(args.header_env, "") if args.header_env else None
            print(json.dumps(fetch(url, args.out, header)))
            return 0
        value = parse_json(args.path.read_bytes())
        if args.command == "check":
            report = inspect(value, args.expect_count)
            if not args.show_ids:
                report["conversation_ids"] = len(report["conversation_ids"])
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ok"] else 1
        wrapped = wrap(value, args.group_id)
        _write_new(args.out, (json.dumps(wrapped, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        report = inspect(wrapped)
        print(json.dumps({"saved": str(args.out), "records": report["records"], "problems": report["problems"]}))
        return 0 if report["ok"] else 1
    except (OSError, ValueError) as error:
        print("Envelope step failed: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
