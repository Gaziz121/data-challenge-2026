"""Reference labels for the lab, kept separate by origin and review tier.

Two sources only:
* `scenario_labels`: QA-proposed rows from qa/scenarios/semantic_v1.json,
  classified by qa/lab/label_registry.json. Origin `team_qa_synthetic`.
* `human_labels`: the Viewer's actual `dev-team-human-1` export
  (tools/dev_review/viewer.js, `bundle`). Origin `team_human`. Never official.

Labels are never given to the engine; the lab only compares saved outputs with them.
"""

from collections import defaultdict
import hashlib
import json
from pathlib import Path

from cqa.io import parse_json

REGISTRY_PATH = Path(__file__).parent / "label_registry.json"
SCORED_TIERS = ("proposed_unreviewed", "team_human")
HUMAN_SCHEMA = "dev-team-human-1"


def load_registry(path=REGISTRY_PATH):
    return parse_json(Path(path).read_bytes())


def scenario_labels(spec, registry, scenario_bytes=None):
    """One row per (conversation_id, criterion_id); raises if the registry is stale."""
    if scenario_bytes is not None and hashlib.sha256(scenario_bytes).hexdigest() != registry["scenario_file_sha256"]:
        raise ValueError("semantic_v1.json changed: re-classify it in label_registry.json")
    rows, seen = [], {}

    def add(conversation_id, item_id, part, criterion_id, expected, language):
        key = f"{part}:{criterion_id}" if part else criterion_id
        entry = registry["rows"].get(item_id, {}).get(key)
        if entry is None:
            raise ValueError(f"Unclassified scenario row {item_id} {key}")
        row = {"conversation_id": conversation_id, "criterion_id": criterion_id,
               "accept": expected["accept"], "tier": entry["tier"], "origin": "team_qa_synthetic",
               "item_id": item_id, "part": part or "scenario", "language": language,
               "open_items": entry["open_items"], "reviewers": []}
        previous = seen.get((conversation_id, criterion_id))
        if previous is not None:
            if (previous["accept"], previous["tier"]) != (row["accept"], row["tier"]):
                raise ValueError(f"Conflicting labels for {conversation_id} {criterion_id}")
            return
        seen[(conversation_id, criterion_id)] = row
        rows.append(row)

    for s in spec["scenarios"]:
        for cid, expected in s["expect"].items():
            add(s["id"], s["id"], None, cid, expected, s["language"])
    for cf in spec.get("counterfactuals", []):
        language = None  # taken from the evaluated source record at comparison time
        for cid, expected in cf["base_expect"].items():
            add(cf["conversation_id"], cf["id"], "base", cid, expected, language)
        for cid, expected in cf["expect"].items():
            add(cf["id"], cf["id"], "variant", cid, expected, language)
    expected_keys = {(r["item_id"], (r["part"] + ":" if r["part"] != "scenario" else "") + r["criterion_id"])
                     for r in rows}
    registered = {(item, key) for item, entries in registry["rows"].items() for key in entries}
    if registered - expected_keys:
        raise ValueError(f"Registry rows without a scenario expectation: {sorted(registered - expected_keys)}")
    return rows


def _check_evidence(reference, record):
    index = reference.get("transcript_index")
    transcript = record["transcript"]
    if type(index) is not int or not 0 <= index < len(transcript):
        raise ValueError("Human evidence index outside the source transcript")
    turn = transcript[index]
    expected = {"transcript_index": index, "original_message_id": turn.get("message_id"),
                "timestamp": turn.get("timestamp"), "speaker": turn["speaker"], "text": turn["text"]}
    if any(reference.get(k) != v for k, v in expected.items()):
        raise ValueError("Human evidence differs from the source transcript")


def load_human_export(path, records, dataset_sha256):
    """Validate one Viewer JSON export against the source dataset; return its cells."""
    saved = parse_json(Path(path).read_bytes())
    if (saved.get("schema_version") != HUMAN_SCHEMA or saved.get("label_source") != "team_human"
            or saved.get("official_ground_truth") is not False):
        raise ValueError("Not a Viewer team_human export (schema dev-team-human-1)")
    if (saved.get("dataset") or {}).get("sha256") != dataset_sha256:
        raise ValueError("Human export was made on a different dataset file")
    reviewer = saved.get("reviewer_id")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Human export needs a reviewer ID")
    cells, conversations = [], set()
    for assessment in saved.get("assessments") or []:
        cid = assessment.get("conversation_id")
        record = records.get(cid)
        if record is None or cid in conversations:
            raise ValueError(f"Unknown or duplicate conversation in human export: {cid}")
        conversations.add(cid)
        if (assessment.get("language"), assessment.get("channel")) != (record["language"], record["channel"]):
            raise ValueError(f"Language/channel differs from source for {cid}")
        ids = [c.get("criterion_id") for c in assessment.get("criteria") or []]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate criterion in human export for {cid}")
        for criterion in assessment["criteria"]:
            for reference in criterion.get("evidence") or []:
                _check_evidence(reference, record)
            response = criterion.get("response")
            if response is None:
                continue  # unscored: never treated as zero or N/A
            if not (response in ("yes", "no", "N/A") or type(response) is int):
                raise ValueError(f"Invalid human response for {cid} {criterion['criterion_id']}")
            cells.append({"conversation_id": cid, "criterion_id": criterion["criterion_id"],
                          "response": response, "reviewer_id": reviewer.strip(),
                          "assessment_status": assessment.get("status"), "language": record["language"]})
    return {"reviewer_id": reviewer.strip(), "rubric_version": saved.get("rubric_version"),
            "file_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(), "cells": cells}


def human_labels(exports):
    """Combine independent reviewers without consensus merging.

    One reviewer, or several who agree exactly: tier `team_human`. Any
    disagreement: tier `disputed`, excluded from scored denominators.
    """
    by_cell, seen_reviewers = defaultdict(list), set()
    for export in exports:
        for cell in export["cells"]:
            key = (cell["conversation_id"], cell["reviewer_id"], cell["criterion_id"])
            if key in seen_reviewers:
                raise ValueError(f"Reviewer {cell['reviewer_id']} labelled {cell['conversation_id']} twice")
            seen_reviewers.add(key)
            by_cell[(cell["conversation_id"], cell["criterion_id"])].append(cell)
    rows = []
    for (cid, criterion), cells in sorted(by_cell.items()):
        responses = {json.dumps(c["response"]) for c in cells}
        rows.append({"conversation_id": cid, "criterion_id": criterion,
                     "accept": [cells[0]["response"]] if len(responses) == 1 else sorted(
                         {c["response"] for c in cells}, key=str),
                     "tier": "team_human" if len(responses) == 1 else "disputed",
                     "origin": "team_human", "item_id": cid, "part": "human", "language": cells[0]["language"],
                     "open_items": [], "reviewers": sorted(c["reviewer_id"] for c in cells)})
    return rows
