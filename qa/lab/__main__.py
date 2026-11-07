"""CLI: python3 -m qa.lab {report,compare,capture,ingest,make-split,demo} (offline only)."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from cqa.loader import SHARED

from qa.harness import DEFAULT_SCENARIOS, load_scenarios
from qa.lab.artifacts import MANIFEST, load_artifact, load_run, source_catalogue
from qa.lab.compare import (assess_run, compare_runs, redact_for_holdout, render, run_summary, _fmt_metrics,
                            NOT_A_MEASUREMENT)
from qa.lab.labels import human_labels, load_human_export, load_registry, scenario_labels
from qa.lab.splits import SYNTHETIC_SPLIT, load_split, make_dataset_split

DEMO = Path(__file__).parent / "demo"


def _new_path(path):
    path = Path(path)
    if path.exists():
        raise SystemExit(f"Refusing to overwrite existing {path}")
    return path


def context(args):
    spec = load_scenarios()
    catalogue, records, dataset_sha = source_catalogue(spec, args.dataset)
    rows = scenario_labels(spec, load_registry(), DEFAULT_SCENARIOS.read_bytes())
    rows += human_labels([load_human_export(p, records, dataset_sha) for p in args.human_labels or []])
    case_split = dict(load_split(SYNTHETIC_SPLIT, rows)["case_split"])
    if args.split_manifest:
        extra = load_split(args.split_manifest, rows)["case_split"]
        clash = {k for k in extra if k in case_split and case_split[k] != extra[k]}
        if clash:
            raise SystemExit(f"Split manifests disagree on {sorted(clash)}")
        case_split.update(extra)
    if args.split == "holdout" and not args.holdout_confirm:
        raise SystemExit("Holdout is frozen: pass --holdout-confirm to run a final, aggregate-only check")
    return spec, catalogue, rows, case_split


def emit(report, text, args):
    if args.split == "holdout":
        report = redact_for_holdout(report)
    print(text(report))
    if args.json_out:
        _new_path(args.json_out).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
                                            encoding="utf-8")


def cmd_compare(args):
    spec, catalogue, rows, case_split = context(args)
    report = compare_runs(load_run(args.baseline), load_run(args.candidate), catalogue, rows, spec,
                          case_split, args.split, args.demo_mechanics)
    emit(report, render, args)


def cmd_report(args):
    spec, catalogue, rows, case_split = context(args)
    run = load_run(args.run)
    cases = assess_run(run, catalogue, case_split, args.split, args.demo_mechanics)
    summary = run_summary(run, cases, rows, spec, args.demo_mechanics)
    summary["split"] = args.split
    summary["case_issues"] = {cid: c["issues"] for cid, c in cases.items() if c["issues"]}

    def text(s):
        lines = [f"CQA Accuracy Lab - run {s['run_id']} @ engine {s['engine_commit']} ({s['split']})"]
        if s["measurement_status"] != "genuine_model_outputs":
            lines.append("!! " + (NOT_A_MEASUREMENT if s["measurement_status"] == "demonstration_only"
                                  else "Mock/test-double outputs: label cells not assessed."))
        lines.append(f"cases {s['cases']}, accepted {s['accepted']}, source preserved {s['source_preserved']}, "
                     f"evidence {s['evidence']}")
        _fmt_metrics(lines, s)
        if isinstance(s["case_issues"], dict):
            for cid, issues in s["case_issues"].items():
                for i in issues:
                    lines.append(f"  {cid} C{i['criterion_id'] or '-'} {i['invariant']}: {i['message']}")
        return "\n".join(lines) + "\n"
    if args.split == "holdout":
        summary["case_issues"] = "withheld on holdout"
    emit(summary, text, args)


def build_raw(conversation, checklist, overrides):
    """Scripted fixture output: compliant defaults (qa.fixtures.valid_raw) plus per-criterion overrides."""
    from qa.fixtures import decision, quote, valid_raw
    raw = valid_raw(conversation, checklist)
    for cid, change in overrides.items():
        d = decision(raw, cid)
        if "evidence" in change:
            refs = [quote(conversation.messages[e["index"]], e.get("quote"), "QA demo evidence.")
                    for e in change["evidence"]]
            d["evidence"] = deepcopy(refs)
            for atomic in d["atomic_checks"]:
                atomic["evidence"] = deepcopy(refs)
        for atomic in d["atomic_checks"]:
            atomic["answer"] = change.get("atomic", {}).get(atomic["question_id"], atomic["answer"])
        if "response" in change:
            d["response"] = change["response"]
            d["na_reason"] = "QA demo: the configured N/A condition is asserted." if change["response"] == "N/A" else None
    return raw


def cmd_capture(args):
    """Replay scripted fixture outputs through the engine on PYTHONPATH (offline test double)."""
    from cqa.engine import EvaluationRejected, evaluate
    from cqa.io import load_checklist
    from cqa.loader import load_conversation
    from cqa.schemas import EvaluationConfig
    from qa.fixtures import ScriptedProvider
    from qa.harness import build_cases
    plan = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    out = _new_path(args.out)
    checklist = load_checklist()
    conversations = {conv.conversation_id: conv for _, _, conv, _ in build_cases(load_scenarios(), args.dataset)}
    config = EvaluationConfig(**plan.get("config", {}))
    out.mkdir(parents=True)
    for cid, overrides in plan["cases"].items():
        conversation = conversations.get(cid) or load_conversation(args.dataset, cid)
        raw = build_raw(conversation, checklist, overrides)
        try:
            artifact = evaluate(conversation, checklist, ScriptedProvider(raw), config).model_dump(mode="json")
        except EvaluationRejected as rejected:
            artifact = rejected.diagnostic
        (out / f"{cid}.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {k: plan[k] for k in ("run_id", "description")}
    manifest.update(engine_commit=args.engine_commit, output_origin="qa_scripted_fixture")
    (out / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def cmd_ingest(args):
    """Copy saved engine artifacts (e.g. outputs/app/*.json) into a new run directory."""
    out = _new_path(args.out)
    names = [Path(p).name for p in args.artifacts]
    if MANIFEST in names or len(set(names)) != len(names):
        raise SystemExit("Duplicate or reserved artifact file name")
    ids = [load_artifact(path)["conversation"]["conversation_id"] for path in args.artifacts]  # validate first
    if len(ids) != len(set(ids)):
        raise SystemExit("A run holds one artifact per conversation; split repeated runs into separate runs")
    out.mkdir(parents=True)
    for path in args.artifacts:
        shutil.copyfile(path, out / Path(path).name)
    manifest = {"run_id": args.run_id, "engine_commit": args.engine_commit, "description": args.description}
    (out / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run = load_run(out)
    print(f"Ingested {len(run['cases'])} artifact(s) into {out}; origins {run['origins']}")


def cmd_make_split(args):
    from cqa.loader import read_dataset
    data, dataset_sha = read_dataset(args.dataset)
    manifest = make_dataset_split(data["records"], args.seed, args.calibration, args.holdout)
    manifest.update(dataset_sha256=dataset_sha, note="Proposed DEV benchmark split; labels not frozen yet.")
    _new_path(args.out).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["strata"], ensure_ascii=False))


def cmd_demo(args):
    with tempfile.TemporaryDirectory(prefix="cqa-lab-demo-") as tmp:
        for name in ("baseline", "candidate"):
            cmd_capture(argparse.Namespace(fixture=DEMO / f"{name}.json", out=Path(tmp) / name,
                                           engine_commit=args.engine_commit, dataset=args.dataset))
        args.baseline, args.candidate = Path(tmp) / "baseline", Path(tmp) / "candidate"
        args.demo_mechanics = True
        cmd_compare(args)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m qa.lab", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, demo_flag=True):
        p.add_argument("--dataset", type=Path, default=SHARED, help="Source dataset (default: shared synthetic DEV)")
        p.add_argument("--human-labels", nargs="*", type=Path, help="Viewer team_human JSON exports")
        p.add_argument("--split", choices=["calibration", "holdout", "unassigned", "all"], default="calibration")
        p.add_argument("--split-manifest", type=Path, help="Additional DEV split manifest (make-split)")
        p.add_argument("--holdout-confirm", action="store_true")
        p.add_argument("--json-out", type=Path, help="Write the full report to a NEW JSON file")
        if demo_flag:
            p.add_argument("--demo-mechanics", action="store_true",
                           help="Compute label agreement for mock/scripted outputs, stamped as not a measurement")

    p = sub.add_parser("compare", help="Paired baseline vs candidate comparison")
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    common(p)
    p.set_defaults(func=cmd_compare)
    p = sub.add_parser("report", help="Assess one run")
    p.add_argument("--run", type=Path, required=True)
    common(p)
    p.set_defaults(func=cmd_report)
    p = sub.add_parser("capture", help="Replay a scripted fixture through the engine (test double)")
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--engine-commit", required=True)
    p.add_argument("--dataset", type=Path, default=SHARED)
    p.set_defaults(func=cmd_capture)
    p = sub.add_parser("ingest", help="Build a run directory from saved engine artifacts")
    p.add_argument("artifacts", nargs="+", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--engine-commit", required=True)
    p.add_argument("--description", required=True)
    p.set_defaults(func=cmd_ingest)
    p = sub.add_parser("make-split", help="Metadata-only DEV calibration/holdout manifest")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", default="cqa-dev-benchmark-v1")
    p.add_argument("--calibration", type=int, default=3)
    p.add_argument("--holdout", type=int, default=2)
    p.add_argument("--dataset", type=Path, default=SHARED)
    p.set_defaults(func=cmd_make_split)
    p = sub.add_parser("demo", help="Scripted baseline vs candidate on calibration fixtures (not a measurement)")
    p.add_argument("--engine-commit", default="engine-on-PYTHONPATH")
    common(p, demo_flag=False)
    p.set_defaults(func=cmd_demo)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
