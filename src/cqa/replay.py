"""Replay of RECORDED genuine provider replies. No network call, never a new evaluation.

A recording is usable only for the exact conversation, checklist version and prompt bytes it
was produced with (the prompt SHA-256 must match), so a replay can never be presented as a
judgment under a different rubric. Replays are mock-flagged: the exporter refuses them for
official submissions unless explicitly running a dry run.
"""

import json
from pathlib import Path

from .loader import ROOT
from .prompt import build_request
from .providers import ProviderReply

RECORDINGS = (ROOT / "tests/fixtures/live_atomic_v5_f20d00d.json",)


class ReplayUnavailable(ValueError):
    pass


def _recordings():
    found = []
    for path in RECORDINGS:
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            if "p1-ru-001" in value.get("provenance", ""):
                value["conversation_id"] = "p1-ru-001"
                value["path"] = str(path.relative_to(ROOT))
                found.append(value)
    return found


def available():
    return [{"conversation_id": r["conversation_id"], "checklist_version": r["checklist_version"],
             "prompt_version": r["prompt_version"], "model_returned": r["model_returned"],
             "engine_commit": r["engine_commit"]} for r in _recordings()]


class ReplayProvider:
    name = "replay"
    is_mock = True  # Not a fresh evaluation; never exportable as a genuine result.

    def __init__(self):
        self.model = "recorded-reply"

    def match(self, conversation, checklist, prompt_version):
        for recording in _recordings():
            if (recording["conversation_id"] == conversation.conversation_id
                    and recording["checklist_version"] == checklist.version
                    and recording["prompt_version"] == prompt_version):
                _, sha = build_request(conversation, checklist, prompt_version=prompt_version)
                if sha == recording["prompt_sha256"]:
                    return recording
        raise ReplayUnavailable("No recorded genuine reply for this exact conversation, checklist version and "
                                "prompt; available: %s" % ", ".join(
                                    "%s with checklist %s + %s" % (r["conversation_id"], r["checklist_version"],
                                                                  r["prompt_version"]) for r in _recordings()))

    def evaluate(self, conversation, checklist, request, config):
        recording = self.match(conversation, checklist, config.prompt_version)
        self.model = recording["model_returned"]
        return ProviderReply(json.loads(json.dumps(recording["original_model_output"])),
                             model=recording["model_returned"], usage=dict(recording.get("usage") or {}),
                             latency_ms=0)
