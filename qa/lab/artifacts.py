"""Read saved engine artifacts and verify them against their source records.

Accepted inputs are the engine's own saved files, unchanged:
* `EvaluationResult` JSON (status mock_only / needs_review / structurally_valid);
* rejected diagnostic JSON (status validation_failed, `original_model_output`).
A run is a directory of such files plus `run.json` (run_id, engine_commit, description).
"""

from fractions import Fraction
import hashlib
from pathlib import Path

from cqa.io import digest, parse_json
from cqa.loader import read_dataset

from qa.harness import _record, apply_edits

TEST_DOUBLE_PREFIXES = ("qa-",)  # qa-scripted, qa-replay-*: QA fixtures, never semantic evidence
MANIFEST = "run.json"


def origin_of(run):
    if run.get("is_mock"):
        return "mock"
    if str(run.get("provider", "")).startswith(TEST_DOUBLE_PREFIXES):
        return "test_double"
    return "model"


def load_artifact(path):
    data = parse_json(Path(path).read_bytes())
    if "evaluation_id" in data and "model_evaluation" in data:
        kind, raw, score = "accepted", data["model_evaluation"], data.get("score")
    elif data.get("status") == "validation_failed" and "original_model_output" in data:
        kind, raw, score = "rejected", data["original_model_output"], None
        if isinstance(raw, str):
            try:
                raw = parse_json(raw)
            except ValueError:
                raw = None
    else:
        raise ValueError(f"{Path(path).name}: not an engine EvaluationResult or rejected diagnostic")
    run = data.get("run") or {}
    configuration = run.get("configuration") or {}
    recorded = None
    if score and score.get("total_exact_numerator") is not None:
        recorded = Fraction(score["total_exact_numerator"], score["total_exact_denominator"])
    return {"file": Path(path).name, "file_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "kind": kind, "status": data["status"], "raw": raw if isinstance(raw, dict) else None,
            "conversation": data["conversation"], "checklist": data["checklist"],
            "recorded_total": recorded, "recorded_total_display": (score or {}).get("total_score"),
            "engine_issues": data.get("issues", []), "origin": origin_of(run),
            "run": {"provider": run.get("provider"), "model": run.get("model_returned"),
                    "engine_version": run.get("engine_version"),
                    "prompt_version": configuration.get("prompt_version"),
                    "quote_policy": configuration.get("quote_policy"),
                    "checklist_version": data["checklist"].get("version")}}


def load_run(directory):
    directory = Path(directory)
    manifest = parse_json((directory / MANIFEST).read_bytes())
    for key in ("run_id", "engine_commit", "description"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise ValueError(f"run.json needs a nonempty {key}")
    cases = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == MANIFEST:
            continue
        artifact = load_artifact(path)
        cid = artifact["conversation"]["conversation_id"]
        if cid in cases:
            raise ValueError(f"Run {manifest['run_id']} has two artifacts for {cid}")
        cases[cid] = artifact
    if not cases:
        raise ValueError(f"Run {manifest['run_id']} contains no artifacts")
    origins = sorted({a["origin"] for a in cases.values()})
    return {"manifest": manifest, "cases": cases, "origins": origins}


def source_catalogue(spec, dataset_path):
    """{conversation_id: source record} for the dataset, scenarios and counterfactual variants."""
    data, dataset_sha = read_dataset(dataset_path)
    records = {r["conversation_id"]: r for r in data["records"]}
    catalogue = dict(records)
    for s in spec["scenarios"]:
        catalogue[s["id"]] = _record(s["id"], s["language"], s["turns"])
    for cf in spec.get("counterfactuals", []):
        source = records.get(cf["conversation_id"])
        if source is None or digest(source) != cf["source_record_sha256"]:
            raise ValueError(f"Counterfactual source changed or missing: {cf['id']}")
        variant = apply_edits(source, cf["edits"])
        variant["conversation_id"] = cf["id"]
        catalogue[cf["id"]] = variant
    return catalogue, records, dataset_sha


def verify_source(conversation, record):
    """INV-SRC: exact index, speaker, timestamp and text preservation. Returns issues."""
    if record is None:
        return ["No source record for this conversation ID"]
    issues = []
    if conversation.get("source_record_sha256") != digest(record):
        issues.append("source_record_sha256 differs from the source record")
    if conversation.get("language") != record.get("language"):
        issues.append("Language differs from the source record")
    messages, transcript = conversation.get("messages") or [], record["transcript"]
    if len(messages) != len(transcript):
        issues.append(f"Message count {len(messages)} != source {len(transcript)}")
    for i, (m, turn) in enumerate(zip(messages, transcript)):
        if (m.get("source_index"), m.get("source_speaker"), m.get("timestamp"), m.get("text")) != (
                i, turn["speaker"], turn.get("timestamp"), turn["text"]):
            issues.append(f"Message {i} index/speaker/timestamp/text differs from source")
    return issues
