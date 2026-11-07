"""Local CLI. Outputs are private artifacts, never a source of benchmark labels."""

import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from .engine import evaluate
from .io import load_checklist
from .loader import ROOT, SHARED, load_conversation, read_dataset
from .providers import MockProvider, OpenAIProvider, ProviderError
from .schemas import (Checklist, Conversation, EvaluationResult, ModelEvaluation)
from .schemas import EvaluationConfig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="Show conversation IDs and metadata, never transcript text")
    listing.add_argument("--data", type=Path, default=SHARED)
    schema = sub.add_parser("schema", help="Print a versioned JSON Schema for teammate integrations")
    schema.add_argument("contract", choices=["conversation", "checklist", "model", "result"])
    run = sub.add_parser("evaluate")
    run.add_argument("--data", type=Path, default=SHARED)
    run.add_argument("--id", required=True)
    run.add_argument("--checklist", type=Path)
    run.add_argument("--provider", choices=["mock", "openai"], default="mock")
    run.add_argument("--model", help="Required for real evaluation; no implicit model substitution")
    run.add_argument("--allow-external-synthetic", action="store_true")
    run.add_argument("--output", type=Path, required=True, help="New local JSON file; existing files are preserved")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            data, _ = read_dataset(args.data)
            for record in data["records"]:
                print(json.dumps({k: record[k] for k in ("conversation_id", "channel", "language")}, ensure_ascii=False))
        elif args.command == "schema":
            contract = {"conversation": Conversation, "checklist": Checklist,
                        "model": ModelEvaluation, "result": EvaluationResult}[args.contract]
            print(json.dumps(contract.model_json_schema(), ensure_ascii=False, indent=2))
        else:
            # Reject output collisions BEFORE spending tokens, including dangling symlinks.
            if args.output.exists() or args.output.is_symlink():
                raise ValueError("Output exists; choose a new path")
            # Keep transcript-bearing output under the ignored local outputs directory.
            output_root = (ROOT / "outputs").resolve()
            if output_root not in args.output.resolve().parents:
                raise ValueError("Evaluation output must be inside the local outputs directory")
            if args.provider == "openai" and not args.model:
                raise ValueError("Specify --model for a real provider")
            conversation = load_conversation(args.data, args.id)
            checklist = load_checklist(args.checklist)
            provider = MockProvider() if args.provider == "mock" else OpenAIProvider(args.model)
            result = evaluate(conversation, checklist, provider,
                              EvaluationConfig(external_synthetic_allowed=args.allow_external_synthetic))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(result.model_dump_json(indent=2) + "\n")
            print(json.dumps({"status": result.status, "provider": result.run.provider,
                              "model": result.run.model_returned, "is_mock": result.run.is_mock,
                              "total_score": result.score.total_score,
                              "critical_violation": result.score.critical_violation,
                              "latency_ms": result.run.latency_ms, "usage": result.run.usage}))
        return 0
    except ValidationError as error:
        # Pydantic's default exception string can include private input values.
        fields = [".".join(str(x) for x in e["loc"]) for e in error.errors(include_input=False)]
        print("Validation failed at fields: " + ", ".join(fields), file=sys.stderr)
    except (ProviderError, ValueError) as error:
        print(str(error), file=sys.stderr)
    except OSError:
        print("Local input/output unavailable; inspect paths and permissions", file=sys.stderr)
    return 1
