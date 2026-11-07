"""Prepare/verify the approved synthetic-only DEV derivative; no network or scoring."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/DEV_conversations.json"
OUTPUT = ROOT / "data/shared/DEV_synthetic_60.json"


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Nonstandard JSON numeric constant")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify existing subset without writing")
    args = parser.parse_args()
    if not SOURCE.is_file():
        print("Full original is LOCAL ONLY, not missing from Git by accident.")
        print("Inspect PROJECT_FILE_MAP.md and local data/raw; obtain it through an approved owner handoff.")
        return 1
    source_bytes = SOURCE.read_bytes()
    payload = json.loads(source_bytes.decode("utf-8-sig"), object_pairs_hook=unique_keys,
                         parse_constant=reject_constant)
    require(payload.get("isSuccess") is True and payload.get("error") == "", "Invalid source envelope")
    data = payload["data"]
    records = data["records"]
    require(data["dataset_group_id"] == "DEV" and data["total_records"] == 65 and len(records) == 65,
            "Expected full 65-record DEV input; preserve source and inspect")
    require(len({record["conversation_id"] for record in records}) == 65, "Nonunique source IDs")
    chats = [record for record in records if record["channel"] == "agent chat"]
    calls = [record for record in records if record["channel"] == "voice call"]
    require(len(chats) == 60 and len(calls) == 5, "Unexpected source channel composition")
    require(all(set(record) == {"conversation_id", "channel", "language", "transcript", "audio_url"}
                for record in chats), "Unexpected chat metadata requires a new sharing review")
    require(len({record["conversation_id"] for record in chats}) == 60, "Nonunique chat IDs")
    require(Counter(record["language"] for record in chats) == Counter(RU=30, KZ=15, EN=15),
            "Unexpected synthetic language split")
    require(all(not record.get("audio_url") for record in chats), "Chat audio content requires review")
    subset = {"error": "", "isSuccess": True, "data": {
        "dataset_group_id": "DEV_SYNTHETIC_ONLY", "source_dataset_group_id": "DEV",
        "total_records": 60, "records": chats}}
    serialized = json.dumps(subset, ensure_ascii=False, indent=2) + "\n"
    require(not re.search(r"(?i)https?://|x-amz-signature|x-goog-signature|[?&](?:sig|token|key|code)=|"
                          r"\bgh[pousr]_[A-Za-z0-9_]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}|"
                          r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}", serialized),
            "URL/credential-like material requires a new sharing review")
    require(not any(record["conversation_id"] in serialized for record in calls),
            "Call identifiers must not enter the derivative")
    if OUTPUT.exists():
        require(not OUTPUT.is_symlink() and OUTPUT.read_bytes() == serialized.encode("utf-8"),
                "Existing derivative differs; preserved without overwriting")
    elif args.check:
        raise ValueError("Shared derivative not found locally; inspect PROJECT_FILE_MAP.md and filesystem")
    else:
        require(not OUTPUT.parent.is_symlink(), "Refusing symlink destination")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    require(SOURCE.read_bytes() == source_bytes, "Original changed during verification")
    print("Verified: 60 unchanged synthetic chats; unique IDs; RU=30 KZ=15 EN=15; no calls/audio links.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError):
        # Do not echo source record contents, malformed input snippets or signed URLs.
        print("Preparation stopped: a source/derivative validation failed; inspect locally and preserve files.")
        sys.exit(1)
