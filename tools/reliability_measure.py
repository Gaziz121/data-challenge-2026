"""Offline baseline-vs-candidate reliability measurement. No network, no paid calls.

Run once per engine source tree (PYTHONPATH selects the engine), e.g.:
  PYTHONPATH=../data-challenge-2026-integration/src:. python3 -B tools/reliability_measure.py --label baseline
  PYTHONPATH=src:. python3 -B tools/reliability_measure.py --label candidate
Outputs go to ignored outputs/reliability/<label>.json. Genuine replies are the
four saved OpenAI outputs (all on synthetic p1-ru-001); every other output is a
hand-authored or enumerated fixture. Nothing here is model accuracy.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cqa import __version__  # noqa: E402
from cqa.engine import EvaluationRejected, evaluate  # noqa: E402
from cqa.io import load_checklist  # noqa: E402
from cqa.loader import SHARED, load_conversation  # noqa: E402
from cqa.prompt import build_request  # noqa: E402
from cqa.schemas import EvaluationConfig  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
CHECKLISTS = Path(sys.modules["cqa"].__file__).parent / "checklists"
GENUINE = [("live_first.json", "v2"), ("live_c379231.json", "v2"), ("live_f4599f0.json", "v3"),
           ("live_atomic_5d256ac.json", "v4")]


class Scripted:
    name, model, is_mock = "offline-replay", "saved-genuine-output", True

    def __init__(self, raw, repair_output=None):
        self.raw, self.repair_output, self.repair_calls = raw, repair_output, 0

    def evaluate(self, *args):
        from cqa.providers import ProviderReply
        return ProviderReply(deepcopy(self.raw), model=self.model)


def replay(raw, checklist, config=None, **kwargs):
    conv = load_conversation(SHARED, "p1-ru-001")
    try:
        result = evaluate(conv, checklist, kwargs.pop("provider", None) or Scripted(raw), config, **kwargs)
        return {"accepted": True, "total": result.score.total_score, "status": result.status,
                "states": {r.criterion_id: r.state for r in result.criterion_reviews}}
    except EvaluationRejected as error:
        d = error.diagnostic
        return {"accepted": False, "issue_count": len(d["issues"]),
                "issues": sorted({(i.get("criterion_id"), i["message"]) for i in d["issues"]}),
                "states": {r["criterion_id"]: r["state"] for r in d.get("criterion_reviews", [])}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    v4 = load_checklist(CHECKLISTS / "official-v4.json")
    conv = load_conversation(SHARED, "p1-ru-001")
    report = {"label": args.label, "engine_version": __version__, "engine_src": str(CHECKLISTS.parent),
              "note": "Offline only. Genuine = 4 saved OpenAI replies on synthetic p1-ru-001; others are fixtures."}
    report["genuine_replay"] = {}
    for name, version in GENUINE:
        raw = json.loads((FIXTURES / name).read_text())["original_model_output"]
        report["genuine_replay"][name] = replay(raw, load_checklist(CHECKLISTS / f"official-{version}.json"))
    report["genuine_accepted"] = sum(r["accepted"] for r in report["genuine_replay"].values())

    try:
        from cqa.strict_schema import conforms, strict_issues
        from tests.test_schema_reliability import (BoundedRepairTests, CountingRepairProvider, enumerate_entries,
                                                   entry_conforms, genuine, scripted_repair_of_genuine, STRUCTURAL,
                                                   RESIDUAL, criterion_review)
        from tests.test_atomic_path import raw_fixture
        from cqa.atomic_prompt import compile_atomic_schema
        from cqa.schemas import RepairPolicy
    except ImportError:
        report["candidate_features"] = "absent in this engine"
        return write(args.label, report)

    schemas = {v: build_request(conv, v4, prompt_version=v) for v in ("atomic-v2", "atomic-v3", "atomic-v4")}
    report["schemas"] = {v: {"sha256": sha, "schema_bytes": len(json.dumps(r["schema"])),
                             "input_bytes": len(r["input"]), "instructions_bytes": len(r["instructions"]),
                             "criterion_branches": len(r["schema"]["properties"]["criteria"]["items"]["anyOf"]),
                             "strict_issues": strict_issues(r["schema"])}
                         for v, (r, sha) in schemas.items()}
    report["genuine_atomic_reply_representable"] = {
        v: {c["criterion_id"]: entry_conforms(c, r["schema"]) for c in genuine()["criteria"]}
        for v, (r, _) in schemas.items()}

    # Enumerated fixtures: which validator outcomes each schema can still produce.
    base, counts = raw_fixture(conv, v4), {}
    started = time.perf_counter()
    for version, (request, _) in schemas.items():
        c = counts[version] = {"entries": 0, "validator_accepted": 0,
                               "structural_failures_total": 0, "structural_failures_representable": 0,
                               "residual_verified_no_scope_representable": 0, "representable": 0,
                               "representable_but_rejected_other_reason": 0}
        for criterion in v4.criteria:
            for entry in enumerate_entries(conv, criterion):
                raw = deepcopy(base)
                raw["criteria"] = [entry if x["criterion_id"] == criterion.criterion_id else x for x in raw["criteria"]]
                review = criterion_review(raw, conv, v4, criterion.criterion_id)
                ok = entry_conforms(entry, request["schema"])
                structural = [i for i in review.issues if any(s in i for s in STRUCTURAL) and i != RESIDUAL]
                c["entries"] += 1
                c["representable"] += ok
                c["validator_accepted"] += review.state.startswith("accepted_")
                c["structural_failures_total"] += bool(structural)
                c["structural_failures_representable"] += bool(structural) and ok
                c["residual_verified_no_scope_representable"] += (RESIDUAL in review.issues) and ok
                other = ok and not review.state.startswith("accepted_") and not structural \
                    and review.state != "needs_review"
                c["representable_but_rejected_other_reason"] += other
                for issue in review.issues if other else []:
                    c.setdefault("other_reasons", {}).setdefault(issue, 0)
                    c["other_reasons"][issue] += 1
    report["enumeration"] = counts
    report["enumeration_seconds"] = round(time.perf_counter() - started, 2)

    provider = CountingRepairProvider(genuine(), scripted_repair_of_genuine(conv))
    report["controlled_repair_fixture"] = {
        "label": "Genuine 5d256ac facts + HAND-AUTHORED repair (scope added, C07 judgment written by hand). Not model output.",
        "result": replay(None, v4, EvaluationConfig(prompt_version="atomic-v4"), provider=provider,
                         repair=RepairPolicy(authorization="offline measurement")),
        "repair_calls": provider.repair_calls}
    from cqa.repair import build_repair_request
    from cqa.atomic import AtomicReviewRequired, process_atomic_output
    try:
        process_atomic_output(genuine(), conv, v4)
    except AtomicReviewRequired as error:
        request, sha, targets, pins, _ = build_repair_request(conv, v4, genuine(), error.reviews, "atomic-v4")
        report["repair_request_for_genuine"] = {"sha256": sha, "targets": targets, "pinned_answers": pins,
                                                "schema_bytes": len(json.dumps(request["schema"])),
                                                "input_bytes": len(request["input"]),
                                                "strict_issues": strict_issues(request["schema"])}
    return write(args.label, report)


def write(label, report):
    out = ROOT / "outputs" / "reliability"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{label}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=list))
    print(json.dumps({k: v for k, v in report.items() if k in ("label", "engine_version", "genuine_accepted",
                                                                "enumeration", "schemas")}, indent=1, default=list))


if __name__ == "__main__":
    main()
