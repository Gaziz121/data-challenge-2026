"""Evaluate every conversation of an organizer envelope with the UNCHANGED engine.

    PYTHONPATH=src python3 -m cqa_results.batch --data data/raw/DEV_conversations.json \
        --run-dir outputs/submission/dev-run1 --provider mock

One outcome file per attempt is written under the ignored outputs/ directory:
  run.json                          configuration and dataset binding
  NNN-<idhash>.aKK.result.json      accepted EvaluationResult (engine output)
  NNN-<idhash>.aKK.rejected.json    engine EvaluationRejected diagnostic
  NNN-<idhash>.aKK.error.json       any other genuine failure, with a safe reason
Nothing is retried automatically except the opt-in --repair-authorization: at most ONE
bounded criterion-repair call per rejected atomic conversation (so up to 2 calls each;
--live-call-limit counts conversations). --resume re-attempts only conversations whose
latest attempt is not an accepted result. Real (non-mock) calls run only when
--provider openai is passed explicitly together with --model.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading

from pydantic import ValidationError

from cqa import __version__ as ENGINE_VERSION
from cqa.access import AccessDenied, ExportPolicy, InputPolicy
from cqa.engine import CheckBlocked, EvaluationRejected, evaluate
from cqa.io import digest, load_checklist, parse_json
from cqa.loader import ROOT, normalize_record, read_dataset
from cqa.providers import MockProvider, OpenAIProvider, ProviderError
from cqa.schemas import EvaluationConfig, RepairPolicy

RUN_SCHEMA = "cqa-results-run/1"
ATTEMPT = re.compile(r"^(\d{3})-([0-9a-f]{12})\.a(\d{2})\.(result|rejected|error)\.json$")


def id_hash(conversation_id):
    return hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:12]


def scan_attempts(run_dir):
    """{(index, idhash): [(attempt, kind, path), ...]} sorted by attempt."""
    found = {}
    for path in Path(run_dir).iterdir():
        if path.name == "run.json" or path.name.startswith("."):
            continue
        match = ATTEMPT.match(path.name)
        if not match:
            raise ValueError("Unexpected file in run directory: %s" % path.name)
        key = (int(match.group(1)), match.group(2))
        found.setdefault(key, []).append((int(match.group(3)), match.group(4), path))
    for attempts in found.values():
        attempts.sort()
        numbers = [a for a, _, _ in attempts]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Duplicate attempt number in run directory")
    return found


def _write_new(path, text):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as handle:
        handle.write(text)


def _safe_reason(error):
    if isinstance(error, ValidationError):
        fields = sorted({".".join(str(x) for x in e["loc"]) for e in error.errors(include_input=False)})
        return "Schema validation failed at fields: " + ", ".join(fields[:8])
    if isinstance(error, CheckBlocked):
        codes = sorted({f.code for o in error.check_outcomes for f in o.findings if f.severity == "block"})
        return "Blocked by a quality check before scoring: " + ", ".join(codes or ["unspecified"])
    if isinstance(error, (ProviderError, AccessDenied)):
        return "%s: %s" % (type(error).__name__, error)  # Safe by engine contract.
    if isinstance(error, ValueError):
        return "Evaluation failed: %s" % error
    return "Unexpected %s during evaluation; details withheld" % type(error).__name__


def run_batch(data_path, run_dir, provider, *, checklist=None, config=None, resume=False,
              only=None, expect_count=None, workers=1, live_call_limit=None, log=print, repair=None):
    """Evaluate in source order. Returns {"attempted", "result", "rejected", "error", "skipped"}."""
    run_dir = Path(run_dir)
    if (ROOT / "outputs").resolve() not in run_dir.resolve().parents:
        raise ValueError("Run directory must be inside the ignored local outputs/ directory")
    data, file_hash = read_dataset(data_path)
    records = data["records"]
    if expect_count is not None and len(records) != expect_count:
        raise ValueError("Dataset has %d conversations; expected %d" % (len(records), expect_count))
    checklist = checklist or load_checklist()
    config = config or EvaluationConfig(quote_policy="normalize_formatting")
    if config.prompt_version.startswith("atomic") and checklist.decision_path != "atomic_first":
        raise ValueError("Atomic prompt version requires an atomic_first checklist (e.g. official-v5.json)")
    manifest = {"schema": RUN_SCHEMA, "dataset_sha256": file_hash, "dataset_group_id": data["dataset_group_id"],
                "conversation_ids": [r["conversation_id"] for r in records],
                "provider": provider.name, "model_requested": provider.model, "is_mock": provider.is_mock,
                "checklist_id": checklist.checklist_id, "checklist_version": checklist.version,
                "checklist_sha256": digest(checklist.model_dump(mode="json")), "engine_version": ENGINE_VERSION,
                "configuration": config.model_dump(mode="json"),
                "repair": repair.model_dump(mode="json") if repair is not None else None}
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path = run_dir / "run.json"
    if manifest_path.exists():
        previous = parse_json(manifest_path.read_bytes())
        if not resume:
            raise ValueError("Run directory already used; pass --resume or choose a new directory")
        stable = {k: v for k, v in manifest.items() if k != "started_at"}
        previous.setdefault("repair", None)  # Run directories written before the repair option existed.
        if {k: previous.get(k) for k in stable} != stable:
            raise ValueError("Resume refused: dataset, provider, model, checklist or configuration changed")
    else:
        if any(run_dir.iterdir()):
            raise ValueError("Run directory is not empty and has no run.json")
        _write_new(manifest_path, json.dumps(dict(manifest, started_at=datetime.now(timezone.utc).isoformat()),
                                             ensure_ascii=False, indent=2) + "\n")
    attempts = scan_attempts(run_dir)
    selected = set(only) if only else None
    if selected and selected - set(manifest["conversation_ids"]):
        raise ValueError("--only names an ID that is not in the dataset")
    counts = {"attempted": 0, "result": 0, "rejected": 0, "error": 0, "skipped": 0}
    lock, calls = threading.Lock(), [0]
    jobs = []
    for index, record in enumerate(records):
        key = (index, id_hash(record["conversation_id"]))
        history = attempts.get(key, [])
        if selected is not None and record["conversation_id"] not in selected:
            continue
        if history and history[-1][1] == "result":
            counts["skipped"] += 1
            continue
        jobs.append((index, record, (history[-1][0] + 1) if history else 1))

    def one(job):
        index, record, attempt = job
        cid = record["conversation_id"]
        with lock:
            if live_call_limit is not None and not provider.is_mock and calls[0] >= live_call_limit:
                return None
            calls[0] += 1
        stem = "%03d-%s.a%02d" % (index, id_hash(cid), attempt)
        try:
            conversation = normalize_record(record, data["dataset_group_id"], file_hash)
        except (ValueError, KeyError, TypeError) as error:
            kind, text = "error", _error_doc(cid, "Input normalization failed: %s" % _safe_reason(error), provider)
        else:
            try:
                result = evaluate(conversation, checklist, provider, config, repair=repair)
                kind, text = "result", result.model_dump_json(indent=2) + "\n"
            except EvaluationRejected as error:
                kind, text = "rejected", json.dumps(error.diagnostic, ensure_ascii=False, indent=2) + "\n"
            except Exception as error:  # Every other genuine failure becomes an explicit error outcome.
                kind, text = "error", _error_doc(cid, _safe_reason(error), provider)
        _write_new(run_dir / ("%s.%s.json" % (stem, kind)), text)
        with lock:
            counts["attempted"] += 1
            counts[kind] += 1
        log("[%03d/%03d] %s %s" % (index + 1, len(records), kind.upper(), cid))
        return kind

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(one, jobs))
    return counts


def _error_doc(cid, reason, provider):
    return json.dumps({"schema": "cqa-results-error/1", "conversation_id": cid, "error": reason,
                       "provider": provider.name, "model_requested": provider.model, "is_mock": provider.is_mock,
                       "recorded_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, type=Path, help="Organizer envelope {isSuccess,error,data.records}")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--provider", choices=["mock", "openai"], default="mock")
    parser.add_argument("--model", help="Required for openai; recorded exactly as requested")
    parser.add_argument("--checklist", type=Path, help="Default: engine default checklist")
    parser.add_argument("--env-file", type=Path, help="Ignored local file with OPENAI_API_KEY; never logged")
    parser.add_argument("--allow-external-synthetic", action="store_true",
                        help="Permit OpenAI only for content identical to the reviewed synthetic 60 chats")
    parser.add_argument("--authorization-manifest", type=Path, help="Owner content grants (ignored restricted/)")
    parser.add_argument("--allow-external-authorized", action="store_true")
    parser.add_argument("--expect-count", type=int)
    parser.add_argument("--only", nargs="+", help="Evaluate only these conversation IDs")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--live-call-limit", type=int, help="Hard cap on real provider attempts in this process")
    parser.add_argument("--max-output-tokens", type=int, default=8000)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--quote-policy", choices=["exact", "normalize_formatting"], default="normalize_formatting")
    parser.add_argument("--evidence-gate", choices=["strict", "review"], default="strict",
                        help="EXPERIMENTAL opt-in. review: quote-role/unused-annotation policy issues become recorded "
                             "needs_review exceptions; nonexistent quotes, unresolved facts, coverage and conflicts still "
                             "block. Default strict. Recorded in run.json")
    parser.add_argument("--repair-authorization",
                        help="Opt in to ONE bounded criterion repair call per rejected conversation (atomic only); "
                             "the value is a short nonsecret owner authorization reference recorded in every result")
    parser.add_argument("--prompt-version", choices=["atomic-v2", "atomic-v5"],
                        help="Atomic checklists only. Default: engine default (atomic-v2). "
                             "atomic-v5 = schema-constrained candidate; recorded in run.json")
    args = parser.parse_args(argv)
    try:
        config = EvaluationConfig(external_synthetic_allowed=args.allow_external_synthetic,
                                  max_output_tokens=args.max_output_tokens, timeout_seconds=args.timeout_seconds,
                                  quote_policy=args.quote_policy, evidence_gate=args.evidence_gate,
                                  **({"prompt_version": args.prompt_version} if args.prompt_version else {}))
        if args.provider == "mock":
            provider = MockProvider()
        else:
            if not args.model:
                raise ValueError("Specify --model for a real provider; no implicit model substitution")
            if args.checklist is None or args.prompt_version is None:
                # A real run must never fall back silently to the legacy default checklist/prompt.
                raise ValueError("Specify --checklist and --prompt-version explicitly for a real provider "
                                 "(frozen production configuration: tools/production.env)")
            from cqa.web import load_env_file
            key = (load_env_file(args.env_file) if args.env_file else {}).get("OPENAI_API_KEY") \
                or os.environ.get("OPENAI_API_KEY", "")
            if not key.strip():
                raise ValueError("OPENAI_API_KEY is not configured; no request sent")
            policy = ExportPolicy(InputPolicy.from_path(args.authorization_manifest,
                                                        allow_external=args.allow_external_authorized),
                                  allow_dev=args.allow_external_synthetic)
            provider = OpenAIProvider(args.model, api_key=key, input_policy=policy)
        counts = run_batch(args.data, args.run_dir, provider,
                           checklist=load_checklist(args.checklist) if args.checklist else None,
                           config=config, resume=args.resume, only=args.only, expect_count=args.expect_count,
                           workers=args.workers, live_call_limit=args.live_call_limit,
                           repair=RepairPolicy(authorization=args.repair_authorization) if args.repair_authorization else None)
    except (OSError, ValueError) as error:
        print("Batch not run: %s" % error, file=sys.stderr)
        return 1
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
