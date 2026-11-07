"""DEV ingestion; never fetch audio or copy signed audio fields into contracts."""

import hashlib
from pathlib import Path

from .io import digest, parse_json
from .schemas import Conversation, Message

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "data/shared/DEV_synthetic_60.json"
SHARED_SHA256 = "836b1cd80a70f4fb901f3d7a8aacfc227ecc523a8a4d29631ff91bf88a399c17"
ROLES = {"client": "customer", "operator": "agent", "bot": "bot", "system": "system"}
CHANNELS = {"agent chat": "chat", "voice call": "voice"}


def read_dataset(path):
    raw = Path(path).read_bytes()
    value = parse_json(raw)
    if not isinstance(value, dict) or value.get("isSuccess") is not True or value.get("error") != "":
        raise ValueError("Invalid organizer dataset envelope")
    data = value.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ValueError("Dataset requires data.records")
    records = data["records"]
    if type(data.get("total_records")) is not int or data["total_records"] != len(records):
        raise ValueError("Declared record count differs from actual count")
    group = data.get("dataset_group_id")
    if not isinstance(group, str) or not group.strip():
        raise ValueError("Missing dataset group ID")
    ids = [r.get("conversation_id") if isinstance(r, dict) else None for r in records]
    if any(not isinstance(i, str) or not i.strip() or i != i.strip() for i in ids):
        raise ValueError("Invalid conversation IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate conversation IDs")
    return data, hashlib.sha256(raw).hexdigest()


def normalize_record(record, group, dataset_hash):
    if record.get("channel") not in CHANNELS:
        raise ValueError("Unsupported conversation channel")
    transcript = record.get("transcript")
    if not isinstance(transcript, list) or not transcript:
        raise ValueError("Nonempty transcript required")
    messages = []
    for i, turn in enumerate(transcript):
        if not isinstance(turn, dict) or turn.get("speaker") not in ROLES:
            raise ValueError("Unknown source speaker; roles must not be guessed")
        if set(turn) - {"timestamp", "speaker", "text", "message_id"}:
            raise ValueError("Unmapped transcript fields require explicit normalization")
        messages.append(Message(
            message_id=f"m{i:04d}", source_message_id=turn.get("message_id"),
            source_index=i, timestamp=turn.get("timestamp"), source_speaker=turn["speaker"],
            role=ROLES[turn["speaker"]], text=turn.get("text")))
    if len({m.source_message_id for m in messages if m.source_message_id is not None}) != sum(
            m.source_message_id is not None for m in messages):
        raise ValueError("Duplicate source message IDs")
    if set(record) - {"conversation_id", "channel", "language", "transcript", "audio_url"}:
        raise ValueError("Unmapped conversation metadata requires explicit normalization")
    return Conversation(conversation_id=record["conversation_id"],
                        channel=CHANNELS[record["channel"]], language=record.get("language"),
                        dataset_group_id=group, dataset_sha256=dataset_hash,
                        source_record_sha256=digest(record), messages=messages)


def load_conversation(path, conversation_id):
    data, file_hash = read_dataset(path)
    record = next((r for r in data["records"] if r["conversation_id"] == conversation_id), None)
    if record is None:
        raise ValueError("Conversation ID not found")
    return normalize_record(record, data["dataset_group_id"], file_hash)


def require_approved_synthetic(conversation, allowed):
    """Compare full content against the reviewed derivative, not a caller-set label."""
    if not allowed:
        raise ValueError("External synthetic evaluation is not enabled in this run")
    if conversation.channel != "chat":
        raise ValueError("Real call records must never be sent to external providers")
    data, file_hash = read_dataset(SHARED)
    if file_hash != SHARED_SHA256:
        raise ValueError("Approved synthetic derivative is absent or changed")
    original = next((r for r in data["records"]
                     if r["conversation_id"] == conversation.conversation_id), None)
    if original is None or original.get("audio_url"):
        raise ValueError("Conversation is outside the reviewed synthetic subset")
    expected = normalize_record(original, data["dataset_group_id"], file_hash)
    # A source may be the full DEV file; its dataset-level provenance can differ.
    fields = {"dataset_group_id", "dataset_sha256"}
    if conversation.model_dump(exclude=fields) != expected.model_dump(exclude=fields):
        raise ValueError("Conversation content differs from the approved synthetic record")
