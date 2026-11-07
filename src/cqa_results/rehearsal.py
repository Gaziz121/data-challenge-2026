"""Complete OFFLINE final-hour rehearsal with FICTIONAL controls. No network, no paid call.

    PYTHONPATH=src python3 -B -m cqa_results.rehearsal --out outputs/rehearsal/$(date +%H%M%S)

Exercises the exact production path on 10 invented control chats (IDs SIM-PROD-0nn):
  intake/envelope check -> owner grants + authorization check -> normalize -> evaluate with
  the FROZEN production configuration (checklist official-v7 + prompt atomic-v5 + review evidence gate,
  coverage and exact scoring) -> official export -> independent strict validation ->
  commit-preparation safety checks -> printed public-URL verification procedure.

The provider is an offline, MOCK-FLAGGED atomic fixture (the same one the integration tests
use). Its answers are hand-authored wiring data, never quality judgments, so the exporter
only accepts them with --allow-mock and only under outputs/. The official
results/prod/results.json is never written; the rehearsal fails if it would be.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from cqa.access import InputPolicy
from cqa.io import load_checklist
from cqa.loader import ROOT, normalize_record, read_dataset
from cqa.schemas import EvaluationConfig

from .batch import run_batch
from .dryrun import prod10_dryrun_dataset, write_json
from .envelope import inspect
from .export import build_submission, check_checklist, write_submission
from .grants import build_manifest
from .validate import validate_file

PRODUCTION_CHECKLIST = ROOT / "src/cqa/checklists/official-v7.json"
PRODUCTION_PROMPT = "atomic-v5"
PRODUCTION_GATE = "review"  # Must equal tools/production.env (tested).
OFFICIAL = {"dev": ROOT / "results/dev/results.json", "prod": ROOT / "results/prod/results.json"}


def fixture_provider():
    # Reuse the integration-test fixture instead of inventing a second one.
    sys.path.insert(0, str(ROOT))
    from tests.test_submission_integration import AtomicFixtureProvider
    return AtomicFixtureProvider()


def git_ignored(path):
    result = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", str(path)],
                            capture_output=True)
    return result.returncode == 0


def snapshot(path):
    return path.read_bytes() if path.exists() else None


def run_rehearsal(out, log=print):
    out = Path(out).resolve()
    if (ROOT / "outputs").resolve() not in out.resolve().parents:
        raise ValueError("Rehearsal output must stay under ignored outputs/")
    if out.exists() and any(out.iterdir()):
        raise ValueError("Rehearsal directory must be new or empty")
    before = {k: snapshot(p) for k, p in OFFICIAL.items()}
    steps = {}

    # 1. Intake: fictional controls saved as the organizer bytes would be.
    data_path = write_json(out / "PROD_control.FICTIONAL.json", prod10_dryrun_dataset())
    report = inspect(json.loads(data_path.read_text(encoding="utf-8")), expect_count=10)
    steps["1_envelope"] = {k: report[k] for k in ("wrapper", "records", "channels", "speakers", "problems", "ok")}
    if not report["ok"]:
        raise ValueError("Envelope check failed: %s" % report["problems"])

    # 2. Owner grants (synthetic_test for fictional data) and the engine's authorization gate.
    manifest = build_manifest(data_path, "synthetic_test", "rehearsal-fictional-controls",
                              "2030-01-01T00:00:00Z", external=["openai"])
    grants_path = out / "restricted-approvals.FICTIONAL.json"
    grants_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    policy = InputPolicy.from_path(grants_path, allow_external=True)
    data, file_hash = read_dataset(data_path)
    authorized = 0
    for record in data["records"]:
        policy.authorize(normalize_record(record, data["dataset_group_id"], file_hash), "openai")
        authorized += 1
    steps["2_authorization"] = {"grants": len(manifest.grants), "authorized_for_openai": authorized}

    # 3. Evaluate with the explicit production checklist + prompt (no defaults).
    checklist = load_checklist(PRODUCTION_CHECKLIST)
    check_checklist(checklist)
    config = EvaluationConfig(prompt_version=PRODUCTION_PROMPT, quote_policy="normalize_formatting",
                              evidence_gate=PRODUCTION_GATE)
    counts = run_batch(data_path, out / "prod-run", fixture_provider(), checklist=checklist, config=config,
                       expect_count=10, workers=2, log=lambda *_: None)
    resumed = run_batch(data_path, out / "prod-run", fixture_provider(), checklist=checklist, config=config,
                        expect_count=10, resume=True, log=lambda *_: None)
    steps["3_batch"] = {"first_pass": counts, "resume_pass": resumed, "checklist": checklist.version,
                        "prompt_version": PRODUCTION_PROMPT}

    # 4-5. Export to the rehearsal folder and validate independently.
    submission, export_report = build_submission(data_path, out / "prod-run", "REHEARSAL TEAM (not a submission)",
                                                 "prod", allow_mock=True)
    target = out / "prod" / "results.json"
    write_submission(submission, target, data_path, "prod", allow_mock=True)
    validation = validate_file(target, data_path, "prod")
    steps["4_export"] = export_report
    steps["5_validation"] = {"valid": validation["valid"], "summary": validation["summary"],
                             "errors": validation["errors"][:10]}

    # 6. Commit preparation: what would and would not be staged.
    checks = {"official prod path is trackable": not git_ignored("results/prod/results.json"),
              "official dev path is trackable": not git_ignored("results/dev/results.json"),
              "raw control data ignored": git_ignored("data/raw/PROD_control.json"),
              "approvals ignored": git_ignored("restricted/prod-approvals.json"),
              ".env ignored": git_ignored(".env"),
              "rehearsal output ignored": git_ignored(target.relative_to(ROOT)),
              "official files untouched": {k: snapshot(p) for k, p in OFFICIAL.items()} == before}
    steps["6_commit_preparation"] = checks
    steps["7_public_url_verification"] = [
        "PYTHONPATH=src python3 -B -m cqa_results.verify_remote --repo \"$SUBMIT_REPO\" --ref \"$SUBMIT_REF\" "
        "--set prod --dataset data/raw/PROD_control.json",
        "Open https://github.com/$SUBMIT_REPO/blob/$SUBMIT_REF/results/prod/results.json in a private window"]
    ok = (validation["valid"] and all(checks.values()) and len(submission["results"]) == 10
          and resumed["attempted"] == counts["error"] + counts["rejected"])
    summary = {"fictional": True, "ok": ok, "steps": steps, "results_file": str(target)}
    write_json(out / "rehearsal-summary.json", summary)
    for name, value in steps.items():
        log("%s: %s" % (name, json.dumps(value, ensure_ascii=False)))
    log("REHEARSAL %s (fictional controls, mock-flagged fixture; not a submission)" % ("PASSED" if ok else "FAILED"))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, type=Path, help="New directory under outputs/")
    args = parser.parse_args(argv)
    try:
        summary = run_rehearsal(args.out)
    except (OSError, ValueError) as error:
        print("Rehearsal failed: %s" % error, file=sys.stderr)
        return 1
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
