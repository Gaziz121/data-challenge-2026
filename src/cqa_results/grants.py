"""Owner tool: draft content-bound engine approvals for every record of an envelope.

    PYTHONPATH=src python3 -m cqa_results.grants --data data/raw/PROD_control.json \
        --data-class organizer_control --reference "<organizer permission reference>" \
        --external openai --expires 2026-11-09T00:00:00Z --output restricted/prod-approvals.json

Running this IS the owner's authorization decision; it does not verify organizer
permission. Grants bind each record's normalized content (cqa.access fingerprint),
so any later change to a record invalidates its grant. Output stays in ignored
restricted/. Use --external only when sending that data to the provider is allowed.
"""

import argparse
import json
import os
from pathlib import Path
import sys

from cqa.access import AuthorizationManifest, InputGrant, conversation_fingerprint
from cqa.loader import ROOT, normalize_record, read_dataset


def build_manifest(data_path, data_class, reference, expires_at, external=()):
    data, file_hash = read_dataset(data_path)
    grants = [InputGrant(conversation_sha256=conversation_fingerprint(
                  normalize_record(r, data["dataset_group_id"], file_hash)),
              data_class=data_class, authorization_reference=reference,
              external_providers=list(external), expires_at=expires_at) for r in data["records"]]
    return AuthorizationManifest(grants=grants)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--data-class", required=True, choices=["organizer_control", "organizer_dev", "synthetic_test"])
    parser.add_argument("--reference", required=True, help="Short nonsecret permission reference, never a URL/token")
    parser.add_argument("--expires", required=True, help="Timezone-aware ISO time, e.g. 2026-11-09T00:00:00Z")
    parser.add_argument("--external", choices=["openai"], action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if (ROOT / "restricted").resolve() not in args.output.resolve().parents:
            raise ValueError("Approval manifests must be written under ignored restricted/")
        manifest = build_manifest(args.data, args.data_class, args.reference, args.expires, args.external)
        args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
            handle.write(manifest.model_dump_json(indent=2) + "\n")
    except (OSError, ValueError) as error:
        print("No approvals written: %s" % error, file=sys.stderr)
        return 1
    print(json.dumps({"written": str(args.output), "grants": len(manifest.grants),
                      "data_class": args.data_class, "external_providers": args.external}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
