"""Prove the pushed files are publicly visible and byte-identical to the local files.

    PYTHONPATH=src python3 -m cqa_results.verify_remote --repo OWNER/REPO --ref BRANCH \
        --set dev --dataset data/raw/DEV_conversations.json

Fetches results/<set>/results.json WITHOUT credentials through the public GitHub
contents API (an anonymous read proves public visibility), compares SHA-256 with
the local file and re-runs the strict validator on the fetched bytes.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.request

from .validate import validate_file

REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF = re.compile(r"^[A-Za-z0-9_./-]{1,200}$")


def fetch_public(repo, ref, path, timeout=30):
    if not REPO.match(repo) or not REF.match(ref) or ".." in ref:
        raise ValueError("Invalid repository or ref")
    url = "https://api.github.com/repos/%s/contents/%s?ref=%s" % (repo, path, ref)
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github.raw",
                                                   "User-Agent": "cqa-results-verify"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise ValueError("Anonymous fetch failed with HTTP %d (private repo, wrong ref/path, or not pushed)"
                         % error.code) from None


def verify(set_name, local, dataset, fetched):
    local_bytes = Path(local).read_bytes()
    result = {"set": set_name, "local_sha256": hashlib.sha256(local_bytes).hexdigest(),
              "remote_sha256": hashlib.sha256(fetched).hexdigest()}
    result["identical"] = result["local_sha256"] == result["remote_sha256"]
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "results" / set_name / "results.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(fetched)
        report = validate_file(target, dataset, set_name, submission=True)
    result["remote_valid"], result["remote_errors"] = report["valid"], report["errors"][:10]
    result["ok"] = result["identical"] and result["remote_valid"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ref", required=True, help="Branch named in the URL given to organizers")
    parser.add_argument("--set", required=True, choices=["dev", "prod"])
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--local", type=Path, help="Default: results/<set>/results.json")
    args = parser.parse_args(argv)
    local = args.local or Path("results") / args.set / "results.json"
    try:
        fetched = fetch_public(args.repo, args.ref, "results/%s/results.json" % args.set)
        result = verify(args.set, local, args.dataset, fetched)
    except (OSError, ValueError) as error:
        print("Remote verification failed: %s" % error, file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
