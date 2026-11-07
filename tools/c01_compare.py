"""C01 (establishing contact) comparison across evaluation runs. Offline; reads saved outputs only.

    PYTHONPATH=src python3 -B tools/c01_compare.py --data docs/demo/c01_variants_fictional.json \
        --run v6=outputs/c01/v6-fict --run v7=outputs/c01/v7-fict \
        [--expectations tests/fixtures/c01_fictional_expectations.json] [--json out.json]

For every conversation it reads the model's ORIGINAL atomic answers 01.q1 (greeting) and 01.q2
(introduction) from accepted results and rejected diagnostics alike, and derives C01 = yes only if both
are yes (the unchanged official conjunction). It compares them with:
  * constructed expectations for invented test conversations (true by construction), and
  * an AUDIT HEURISTIC over the first operator turn (greeting lexicon + self-introduction pattern).
The heuristic is a review aid with known gaps, never a label, never used by the engine or export.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

GREETINGS = {
    "RU": r"\b(здравствуй\w*|добр(ый|ое|ого)\s+(день|утро|вечер|дня|утра|вечера)|привет\w*|приветствую)\b",
    "KZ": r"(сәлеметсіз|сәлем\b|қайырлы\s+(күн|таң|кеш))",
    "EN": r"\b(hello|hi|hey|good\s+(morning|afternoon|evening)|greetings)\b",
}
INTRO_PHRASES = r"(меня\s+зовут|менің\s+атым|my\s+name\s+is)"          # case-insensitive phrases
INTRO_NAMES = r"((^|[\s,.!])[Яя]\s+[А-ЯЁ][а-яё]+|(^|[\s,.!])[Мм]ен\s+[А-ЯЁӘІҢҒҮҰҚӨҺ]\w+|\b[Ii]'?m\s+[A-Z][a-z]+|\b[Ii]\s+am\s+[A-Z][a-z]+|\b[Tt]his\s+is\s+[A-Z][a-z]+)"


def heuristic(record):
    """(greeting_in_client_language, introduction) for the first operator turn, or None if no operator."""
    first = next((t["text"] for t in record["transcript"] if t["speaker"] == "operator"), None)
    if first is None:
        return None
    language = str(record.get("language", "")).upper()
    pattern = GREETINGS.get(language)
    greet = bool(pattern and re.search(pattern, first, flags=re.IGNORECASE))
    intro = bool(re.search(INTRO_PHRASES, first, flags=re.IGNORECASE) or re.search(INTRO_NAMES, first))
    return ("yes" if greet else "no", "yes" if intro else "no")


def model_answers(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = doc.get("original_provider_output") or doc.get("original_model_output")
    answers = {}
    if isinstance(raw, dict):
        for criterion in raw.get("criteria", []):
            if isinstance(criterion, dict) and criterion.get("criterion_id") == "01":
                for a in criterion.get("atomic_checks", []):
                    if isinstance(a, dict):
                        answers[a.get("question_id")] = a.get("answer")
    return doc["conversation"]["conversation_id"], answers, path.name.split(".")[-2]


def derive(q1, q2):
    if q1 == "yes" and q2 == "yes":
        return "yes"
    if "no" in (q1, q2):
        return "no"
    return "unknown"


def collect(run_dir):
    found = {}
    for path in sorted(Path(run_dir).glob("*.json")):
        if path.name == "run.json" or path.name.endswith(".error.json"):
            continue
        cid, answers, kind = model_answers(path)
        found[cid] = {"q1": answers.get("01.q1"), "q2": answers.get("01.q2"), "kind": kind,
                      "c01": derive(answers.get("01.q1"), answers.get("01.q2"))}
    return found


def compare(records, runs, expectations):
    rows, summary = [], {}
    for name, found in runs.items():
        stats = Counter()
        for record in records:
            cid = record["conversation_id"]
            if cid not in found:
                continue
            got = found[cid]
            exp = expectations.get(cid)
            heur = heuristic(record)
            ref_kind, ref = ("constructed", exp["c01"]) if exp else (
                ("heuristic", derive(*heur)) if heur else ("none", None))
            stats["evaluated"] += 1
            if ref is not None and got["c01"] in ("yes", "no"):
                stats[ref_kind + "_compared"] += 1
                if got["c01"] == ref:
                    stats[ref_kind + "_agree"] += 1
                elif got["c01"] == "no":
                    stats[ref_kind + "_false_no"] += 1
                else:
                    stats[ref_kind + "_false_yes"] += 1
            if got["c01"] == "unknown":
                stats["unknown"] += 1
            rows.append({"run": name, "conversation_id": cid, "language": record.get("language"),
                         "model_q1": got["q1"], "model_q2": got["q2"], "model_c01": got["c01"],
                         "outcome": got["kind"], "reference": ref, "reference_kind": ref_kind})
        summary[name] = dict(stats)
    names = list(runs)
    flips = []
    if len(names) == 2:
        a, b = (runs[n] for n in names)
        for cid in sorted(set(a) & set(b)):
            if a[cid]["c01"] != b[cid]["c01"]:
                flips.append({"conversation_id": cid, names[0]: a[cid]["c01"], names[1]: b[cid]["c01"]})
    return {"summary": summary, "flips": flips, "rows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, type=Path, action="append", help="Envelope(s) the runs used")
    parser.add_argument("--run", required=True, action="append", help="name=run_dir[,run_dir] (repeatable)")
    parser.add_argument("--expectations", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    records = [r for path in args.data for r in json.loads(path.read_text(encoding="utf-8"))["data"]["records"]]
    expectations = {}
    if args.expectations:
        expectations = {c["conversation_id"]: c for c in json.loads(args.expectations.read_text(encoding="utf-8"))["cases"]}
    runs = {}
    for item in args.run:
        name, _, directories = item.partition("=")
        runs[name] = {}
        for directory in directories.split(","):  # One arm may span several run directories.
            runs[name].update(collect(directory))
    report = compare(records, runs, expectations)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "flips": report["flips"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
