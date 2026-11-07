"""Calibration / frozen-holdout split, chosen from metadata only and pinned by hash.

Method: groups are ranked inside each stratum by SHA256(seed + ":" + group_id);
the first floor(0.4 * n + 0.5) groups go to holdout (the 8-of-20 ratio proposed
in case/CQA_REQUIREMENTS.md section 4A). No model output or error is consulted.
Counterfactuals are grouped by their source conversation, so a base chat and its
edited variants never straddle the split.

Freezing: the split file stores a SHA256 of every holdout label row. If a holdout
label changes after freezing, loading the split fails; editing labels to suit a
candidate engine is therefore visible, never silent.
"""

from collections import defaultdict
import hashlib
from pathlib import Path

from cqa.io import canonical, parse_json

SYNTHETIC_SPLIT = Path(__file__).parent / "splits/synthetic_v1.json"
HOLDOUT_NUMERATOR, HOLDOUT_DENOMINATOR = 2, 5


class FrozenHoldoutChanged(ValueError):
    pass


def _rank(seed, group_id):
    return hashlib.sha256(f"{seed}:{group_id}".encode("utf-8")).hexdigest()


def assign(groups, seed):
    """groups: {group_id: stratum} -> {group_id: 'calibration' | 'holdout'}."""
    by_stratum = defaultdict(list)
    for group_id, stratum in groups.items():
        by_stratum[stratum].append(group_id)
    result = {}
    for stratum, members in by_stratum.items():
        ordered = sorted(members, key=lambda g: _rank(seed, g))
        holdout = (2 * HOLDOUT_NUMERATOR * len(ordered) + HOLDOUT_DENOMINATOR) // (2 * HOLDOUT_DENOMINATOR)
        for i, group_id in enumerate(ordered):
            result[group_id] = "holdout" if i < holdout else "calibration"
    return result


def scenario_groups(spec):
    """Return ({group_id: stratum}, {conversation_id: group_id})."""
    groups, members = {}, {}
    for s in spec["scenarios"]:
        groups[s["id"]] = s["language"]
        members[s["id"]] = s["id"]
    for cf in spec.get("counterfactuals", []):
        group_id = "source:" + cf["conversation_id"]
        groups[group_id] = "counterfactual"
        members[cf["conversation_id"]] = group_id
        members[cf["id"]] = group_id
    return groups, members


def holdout_fingerprint(rows, case_split):
    selected = sorted((r for r in rows if case_split.get(r["conversation_id"]) == "holdout"),
                      key=lambda r: (r["conversation_id"], r["criterion_id"], r["origin"]))
    keep = ("conversation_id", "criterion_id", "accept", "tier", "origin")
    return hashlib.sha256(canonical([{k: r[k] for k in keep} for r in selected]).encode("utf-8")).hexdigest()


def build_synthetic_split(spec, rows, seed="cqa-lab-split-v1"):
    groups, members = scenario_groups(spec)
    assignment = assign(groups, seed)
    case_split = {cid: assignment[g] for cid, g in members.items()}
    strata = defaultdict(lambda: {"calibration": 0, "holdout": 0})
    for group_id, stratum in groups.items():
        strata[stratum][assignment[group_id]] += 1
    return {"split_id": "qa-synthetic-v1", "seed": seed,
            "method": "per-stratum SHA256(seed:group_id) ranking; holdout = floor(0.4n + 0.5) groups; "
                      "counterfactuals grouped by source conversation; metadata only",
            "strata": dict(sorted(strata.items())), "groups": dict(sorted(assignment.items())),
            "case_split": dict(sorted(case_split.items())),
            "holdout_label_sha256": holdout_fingerprint(rows, case_split)}


def load_split(path, rows=None):
    split = parse_json(Path(path).read_bytes())
    frozen = split.get("holdout_label_sha256")
    if rows is not None and frozen is not None:
        relevant = [r for r in rows if r["conversation_id"] in split["case_split"]]
        if holdout_fingerprint(relevant, split["case_split"]) != frozen:
            raise FrozenHoldoutChanged("Holdout labels changed after the split was frozen; "
                                       "declare the exposure and freeze a new holdout")
    return split


def make_dataset_split(records, seed, calibration_per_stratum=3, holdout_per_stratum=2):
    """Metadata-only DEV split (language x channel), as proposed in CQA_REQUIREMENTS 4A.

    Picks at most calibration+holdout records per stratum by seeded hash rank.
    Returns a manifest without labels; freeze it once human labels exist.
    """
    by_stratum = defaultdict(list)
    for record in records:
        by_stratum[f"{record['language']}|{record['channel']}"].append(record["conversation_id"])
    case_split, strata = {}, {}
    for stratum, ids in sorted(by_stratum.items()):
        ordered = sorted(ids, key=lambda i: _rank(seed, i))
        holdout = ordered[:holdout_per_stratum]
        calibration = ordered[holdout_per_stratum:holdout_per_stratum + calibration_per_stratum]
        case_split.update({i: "holdout" for i in holdout})
        case_split.update({i: "calibration" for i in calibration})
        strata[stratum] = {"available": len(ids), "calibration": len(calibration), "holdout": len(holdout)}
    return {"split_id": "dev-benchmark-proposed", "seed": seed,
            "method": "per language|channel stratum SHA256(seed:conversation_id) ranking; metadata only",
            "strata": strata, "case_split": dict(sorted(case_split.items())), "holdout_label_sha256": None}
