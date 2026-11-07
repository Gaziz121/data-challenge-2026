"""Labeled scenario harness for FUTURE real-model accuracy runs.

It feeds QA scenarios and in-memory counterfactual variants through the existing
`cqa.engine.evaluate` and compares each locked criterion with the proposed
expected responses. It is not an evaluator and never changes a decision.

Semantic credit is given only to a provider that is neither the mock nor a
declared test double. A mock run therefore reports every locked row as
`not_assessed`, never as a pass. Engine rejections (invalid output, failed
evidence gates) are reported as `engine_error` and count against a real run.

This module performs no network I/O itself. A real provider must be passed in by
code and must satisfy its own data-export rules; the current OpenAI adapter's
gate rejects these fixtures by design (see qa/REPORT.md, QA-C08).
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

from cqa.engine import evaluate
from cqa.io import digest, load_checklist, parse_json
from cqa.loader import ROOT, SHARED, normalize_record, read_dataset
from cqa.providers import MockProvider, ProviderError

HARNESS_VERSION = "qa-harness-v1"
DEFAULT_SCENARIOS = Path(__file__).parent / "scenarios/semantic_v1.json"
GROUP = "QA_SYNTHETIC"


def load_scenarios(path=DEFAULT_SCENARIOS):
    return parse_json(Path(path).read_bytes())


def _record(conversation_id, language, turns):
    return {"conversation_id": conversation_id, "channel": "agent chat", "language": language,
            "transcript": [{"speaker": s, "timestamp": f"00:{i:02d}", "text": t}
                           for i, (s, t) in enumerate(turns)],
            "audio_url": None}


def apply_edits(record, edits):
    """Return an edited deep copy. Each `find` must occur exactly once."""
    variant = deepcopy(record)
    for edit in edits:
        turn = variant["transcript"][edit["index"]]
        if turn["text"].count(edit["find"]) != 1:
            raise ValueError(f"Counterfactual edit must match exactly once at index {edit['index']}")
        turn["text"] = turn["text"].replace(edit["find"], edit["replace"])
    return variant


def build_cases(spec, shared_path=SHARED):
    """Yield (case_id, kind, Conversation, expect). Source data is only read."""
    cases = []
    for s in spec["scenarios"]:
        record = _record(s["id"], s["language"], s["turns"])
        cases.append((s["id"], "scenario", normalize_record(record, GROUP, digest(record)), s["expect"]))
    if spec.get("counterfactuals"):
        data, file_hash = read_dataset(shared_path)
        records = {r["conversation_id"]: r for r in data["records"]}
        for cf in spec["counterfactuals"]:
            source = records.get(cf["conversation_id"])
            if source is None or digest(source) != cf["source_record_sha256"]:
                raise ValueError(f"Counterfactual source changed or missing: {cf['id']}")
            base = normalize_record(source, data["dataset_group_id"], file_hash)
            variant_record = apply_edits(source, cf["edits"])
            variant_record["conversation_id"] = cf["id"]
            variant = normalize_record(variant_record, GROUP, digest(variant_record))
            cases.append((cf["id"] + ":base", "counterfactual_base", base, cf["base_expect"]))
            cases.append((cf["id"] + ":variant", "counterfactual_variant", variant, cf["expect"]))
    return cases


def compare(expect, responses, semantic_credit):
    """Pure comparison of expected rows against {criterion_id: response}."""
    rows = []
    for criterion_id, row in sorted(expect.items()):
        actual = responses.get(criterion_id)
        if not row["lock"]:
            verdict = "recorded"
        elif not semantic_credit:
            verdict = "not_assessed"
        else:
            verdict = "pass" if actual in row["accept"] else "fail"
        rows.append({"criterion_id": criterion_id, "accept": row["accept"], "lock": row["lock"],
                     "actual": actual, "verdict": verdict})
    return rows


def _error_summary(error):
    if hasattr(error, "errors"):  # pydantic: field locations only, never input values
        return "ValidationError at " + ", ".join(".".join(map(str, e["loc"]))
                                                for e in error.errors(include_input=False))
    return f"{type(error).__name__}: {str(error)[:200]}"


def run(provider, checklist=None, spec=None, shared_path=SHARED):
    checklist = checklist or load_checklist()
    spec = spec or load_scenarios()
    semantic_credit = not provider.is_mock and not getattr(provider, "is_test_double", False)
    report = {"harness_version": HARNESS_VERSION, "scenario_set": spec["scenario_set"],
              "scenario_version": spec["version"], "label_origin": spec["label_origin"],
              "review_state": spec["review_state"], "provider": provider.name, "model": provider.model,
              "is_mock": provider.is_mock, "semantic_credit": semantic_credit,
              "checklist_version": checklist.version, "cases": []}
    for case_id, kind, conversation, expect in build_cases(spec, shared_path):
        case = {"case_id": case_id, "kind": kind, "conversation_id": conversation.conversation_id}
        try:
            result = evaluate(conversation, checklist, provider)
        except (ValueError, ProviderError) as error:
            case.update(outcome="engine_error", error=_error_summary(error),
                        rows=compare(expect, {}, semantic_credit))
            if semantic_credit:
                for row in case["rows"]:
                    if row["lock"]:
                        row["verdict"] = "fail"
        else:
            responses = {d.criterion_id: d.response for d in result.model_evaluation.decisions}
            case.update(outcome="evaluated", status=result.status, total_score=result.score.total_score,
                        rows=compare(expect, responses, semantic_credit))
        report["cases"].append(case)
    verdicts = [r["verdict"] for c in report["cases"] for r in c["rows"]]
    report["summary"] = {"cases": len(report["cases"]),
                         "engine_errors": sum(c["outcome"] == "engine_error" for c in report["cases"]),
                         "locked_rows": sum(r["lock"] for c in report["cases"] for r in c["rows"]),
                         **{v: verdicts.count(v) for v in ("pass", "fail", "not_assessed", "recorded")}}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", choices=["mock"], default="mock",
                        help="Only the mock is wired here; real providers are passed in code after approval")
    parser.add_argument("--output", type=Path, help="New JSON file under outputs/ (optional)")
    args = parser.parse_args(argv)
    report = run(MockProvider())
    print(json.dumps(report["summary"]))
    if args.output:
        if args.output.exists() or (ROOT / "outputs").resolve() not in args.output.resolve().parents:
            print("Output must be a new file under outputs/", file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
