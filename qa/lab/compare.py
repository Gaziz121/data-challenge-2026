"""Single-run assessment and paired baseline-versus-candidate comparison.

Definitions (case/CQA_REQUIREMENTS.md section 4C, internal diagnostics only):
* A label cell is scored only for tiers `proposed_unreviewed` and `team_human`.
  `ambiguous` and `disputed` cells are counted as excluded, never scored.
* Verdicts: `match` (response is the label), `mismatch`, `invalid` (the engine
  rejected the output or its conversation differs from the source; no valid
  decision exists), `not_assessed` (mock or test-double output), `missing`.
* Exact raw-response match: N/A is its own response; discrete levels must match.
* Paired transitions use identical cells: fixed = (mismatch|invalid) -> match,
  regressed = match -> (mismatch|invalid).
* Total difference: only when both runs have a valid total that reconciles with
  an independent exact recomputation (INV-TOTAL).
"""

from collections import Counter, defaultdict

from qa.lab.artifacts import verify_source
from qa.lab.checks import check_decision, exact_total, favorability, round_half_up
from qa.lab.labels import SCORED_TIERS

ASSESSABLE = ("match", "mismatch", "invalid")
NOT_A_MEASUREMENT = ("DEMONSTRATION ONLY: these outputs come from a mock or scripted test double. "
                     "Label agreement below shows the lab's mechanics; it is NOT a semantic accuracy measurement.")


def assess_case(artifact, record):
    source_issues = verify_source(artifact["conversation"], record)
    checklist = artifact["checklist"]
    criteria = {c["criterion_id"]: c for c in checklist["criteria"]}
    messages = artifact["conversation"]["messages"]
    raw, decisions, issues = artifact["raw"], {}, []
    if raw is None or not isinstance(raw.get("decisions"), list):
        issues.append({"criterion_id": None, "invariant": "INV-RESP", "message": "No parseable model output"})
    else:
        ids = [d.get("criterion_id") for d in raw["decisions"] if isinstance(d, dict)]
        if len(ids) != len(raw["decisions"]) or len(ids) != len(set(ids)) or set(ids) != set(criteria):
            issues.append({"criterion_id": None, "invariant": "INV-RESP",
                           "message": "Every configured criterion is required exactly once"})
        for d in raw["decisions"]:
            if isinstance(d, dict) and d.get("criterion_id") in criteria:
                decisions.setdefault(d["criterion_id"], d)
    cells = {cid: check_decision(d, criteria[cid], messages) for cid, d in decisions.items()}
    issues += [{"criterion_id": cid, **i} for cid, cell in sorted(cells.items()) for i in cell["issues"]]
    issues += [{"criterion_id": None, "invariant": "INV-SRC", "message": m} for m in source_issues]
    valid = artifact["kind"] == "accepted" and not source_issues
    total = None
    if valid and not any(i["invariant"] == "INV-RESP" for i in issues):
        lab_total = exact_total({cid: c["response"] for cid, c in cells.items()}, checklist)
        recorded = artifact["recorded_total"]
        if recorded is not None and lab_total != recorded:
            issues.append({"criterion_id": None, "invariant": "INV-TOTAL",
                           "message": "Recorded total differs from the exact recomputation"})
        elif recorded is None and lab_total is not None and artifact["recorded_total_display"] != round_half_up(lab_total):
            issues.append({"criterion_id": None, "invariant": "INV-TOTAL",
                           "message": "Recorded display total differs from the recomputation"})
        else:
            total = lab_total
    return {"conversation_id": artifact["conversation"]["conversation_id"],
            "language": artifact["conversation"].get("language"), "source_record_sha256":
            artifact["conversation"].get("source_record_sha256"), "kind": artifact["kind"],
            "status": artifact["status"], "origin": artifact["origin"], "valid_output": valid,
            "criteria": criteria, "cells": cells, "issues": issues, "total": total}


def verdict(row, case, demo):
    if row["tier"] not in SCORED_TIERS:
        return row["tier"]
    if case is None:
        return "missing"
    if case["origin"] != "model" and not demo:
        return "not_assessed"
    if not case["valid_output"]:
        return "invalid"
    cell = case["cells"].get(row["criterion_id"])
    return "match" if cell is not None and cell["response"] in row["accept"] else "mismatch"


def assess_run(run, catalogue, case_split, split, demo=False):
    cases = {}
    for cid, artifact in sorted(run["cases"].items()):
        if split == "all" or case_split.get(cid, "unassigned") == split:
            cases[cid] = assess_case(artifact, catalogue.get(cid))
    return cases


def measurement_status(cases, demo):
    origins = {c["origin"] for c in cases.values()}
    if origins == {"model"}:
        return "genuine_model_outputs"
    if "model" in origins:
        return "partial: only model-origin cases are assessed"
    return "demonstration_only" if demo else "not_assessed"


def label_metrics(rows, cases, demo):
    """Per scored tier: exact match by criterion and language, N/A and 08 confusion, total error."""
    result, excluded = {}, Counter()
    for row in rows:
        if row["conversation_id"] in cases:
            v = verdict(row, cases[row["conversation_id"]], demo)
            if v not in ASSESSABLE:
                excluded[v] += 1
    for tier in SCORED_TIERS:
        selected = [(r, verdict(r, cases[r["conversation_id"]], demo)) for r in rows
                    if r["tier"] == tier and r["conversation_id"] in cases]
        selected = [(r, v) for r, v in selected if v in ASSESSABLE]
        if not selected:
            continue
        by_criterion, by_language = defaultdict(Counter), defaultdict(Counter)
        na_confusion, critical = Counter(), Counter()
        for r, v in selected:
            case = cases[r["conversation_id"]]
            for bucket in (by_criterion[r["criterion_id"]], by_language[case["language"]]):
                bucket["labeled"] += 1
                bucket[v] += 1
            if v == "invalid":
                continue
            criterion = case["criteria"][r["criterion_id"]]
            predicted = case["cells"][r["criterion_id"]]["response"]
            if criterion.get("na_condition") is not None:
                na_confusion[("label_N/A" if r["accept"] == ["N/A"] else "label_applicable") + " / " +
                             ("pred_N/A" if predicted == "N/A" else "pred_applicable")] += 1
            if criterion["kind"] == "critical":
                label_yes, pred_yes = r["accept"] == ["yes"], predicted == "yes"
                critical[{(True, True): "true_positive", (True, False): "miss",
                          (False, True): "false_alarm", (False, False): "true_negative"}[(label_yes, pred_yes)]] += 1
        result[tier] = {"cells": len(selected), "match": sum(v == "match" for _, v in selected),
                        "invalid": sum(v == "invalid" for _, v in selected),
                        "by_criterion": {k: dict(v) for k, v in sorted(by_criterion.items())},
                        "by_language": {str(k): dict(v) for k, v in sorted(by_language.items(), key=str)},
                        "na_confusion": dict(na_confusion), "critical_08": dict(critical),
                        "total_error": _total_error(rows, cases, tier, demo)}
    return result, dict(excluded)


def _total_error(rows, cases, tier, demo):
    """Absolute total error only for cases whose every weighted criterion has a single label of this tier."""
    errors = []
    for cid, case in cases.items():
        if case["total"] is None or (case["origin"] != "model" and not demo):
            continue
        labels = {r["criterion_id"]: r["accept"][0] for r in rows
                  if r["conversation_id"] == cid and r["tier"] == tier and len(r["accept"]) == 1}
        weighted = [c for c in case["criteria"] if case["criteria"][c]["kind"] != "critical"]
        if all(c in labels for c in weighted):
            label_total = exact_total(labels, {"criteria": list(case["criteria"].values())})
            if label_total is not None:
                errors.append(abs(case["total"] - label_total))
    if not errors:
        return {"cases": 0, "note": "no case has a complete weighted label set in this tier"}
    return {"cases": len(errors), "mean_absolute_error_unrounded": str(sum(errors) / len(errors)),
            "mean_absolute_error_display": round_half_up(sum(errors) / len(errors))}


def _issue_keys(case):
    return {(i["criterion_id"], i["invariant"], i["message"]) for i in case["issues"]}


def _evidence_totals(cases):
    totals = Counter()
    for case in cases:
        for cell in case["cells"].values():
            totals.update({k: v for k, v in cell["evidence"].items()})
    return dict(totals)


def _cf_outcome(case_base, case_variant, cf, rows, demo):
    out = {}
    for cid in cf["expect"]:
        b, v = case_base["cells"].get(cid), case_variant["cells"].get(cid)
        valid = case_base["valid_output"] and case_variant["valid_output"] and b and v
        criterion = case_base["criteria"][cid]
        fb = favorability(criterion, b["response"]) if valid else None
        fv = favorability(criterion, v["response"]) if valid else None
        monotonic = None if fb is None or fv is None else fv <= fb
        label = {r["part"]: verdict(r, case_base if r["part"] == "base" else case_variant, demo)
                 for r in rows if r["item_id"] == cf["id"] and r["criterion_id"] == cid}
        out[cid] = {"base": b["response"] if b else None, "variant": v["response"] if v else None,
                    "monotonic": monotonic,
                    "label_flip": (label.get("base") == "match" and label.get("variant") == "match")
                    if {"base", "variant"} <= set(label) and all(x in ASSESSABLE for x in label.values()) else None}
    return out


def run_summary(run, cases, rows, spec, demo):
    metrics, excluded = label_metrics(rows, cases, demo)
    counterfactuals = {}
    for cf in spec.get("counterfactuals", []):
        if cf["conversation_id"] in cases and cf["id"] in cases:
            counterfactuals[cf["id"]] = _cf_outcome(cases[cf["conversation_id"]], cases[cf["id"]], cf, rows, demo)
    return {"run_id": run["manifest"]["run_id"], "engine_commit": run["manifest"]["engine_commit"],
            "description": run["manifest"]["description"], "origins": run["origins"],
            "measurement_status": measurement_status(cases, demo),
            "cases": len(cases), "accepted": sum(c["kind"] == "accepted" for c in cases.values()),
            "source_preserved": sum(not any(i["invariant"] == "INV-SRC" for i in c["issues"]) for c in cases.values()),
            "invariant_violations": dict(Counter(i["invariant"] for c in cases.values() for i in c["issues"])),
            "evidence": _evidence_totals(cases.values()), "label_metrics": metrics, "excluded_labels": excluded,
            "counterfactuals": counterfactuals,
            "engine_runs": sorted({(a["run"]["provider"] or "?", a["run"]["model"] or "?",
                                    a["run"]["prompt_version"] or "?", a["run"]["checklist_version"] or "?")
                                   for a in run["cases"].values()})}


def compare_runs(base_run, cand_run, catalogue, rows, spec, case_split, split, demo=False):
    A = assess_run(base_run, catalogue, case_split, split, demo)
    B = assess_run(cand_run, catalogue, case_split, split, demo)
    unpaired = [{"conversation_id": c, "reason": "only in baseline" if c in A else "only in candidate"}
                for c in sorted(set(A) ^ set(B))]
    paired = []
    for cid in sorted(set(A) & set(B)):
        if A[cid]["source_record_sha256"] != B[cid]["source_record_sha256"]:
            unpaired.append({"conversation_id": cid, "reason": "different source conversation content"})
        else:
            paired.append(cid)
    A2, B2 = {c: A[c] for c in paired}, {c: B[c] for c in paired}

    validation = Counter(f"{A2[c]['kind']} -> {B2[c]['kind']}" for c in paired)
    transitions, details = Counter(), defaultdict(list)
    labeled_cells = set()
    for row in rows:
        cid = row["conversation_id"]
        if cid not in A2:
            continue
        labeled_cells.add((cid, row["criterion_id"]))
        va, vb = verdict(row, A2[cid], demo), verdict(row, B2[cid], demo)
        if va in ASSESSABLE and vb in ASSESSABLE:
            kind = ("still_correct" if va == vb == "match" else "fixed" if vb == "match" else
                    "regressed" if va == "match" else "still_wrong")
        elif "not_assessed" in (va, vb):
            kind = "not_assessed"
        else:
            kind = "excluded_" + (va if va not in ASSESSABLE else vb)
        transitions[(row["tier"], kind)] += 1
        if kind in ("fixed", "regressed", "still_wrong"):
            def shown(case):
                cell = case["cells"].get(row["criterion_id"])
                return ("invalid output; raw " + repr(cell["response"]) if not case["valid_output"]
                        else repr(cell["response"])) if cell else "missing"
            details[kind].append({"conversation_id": cid, "criterion_id": row["criterion_id"], "tier": row["tier"],
                                  "label": row["accept"], "open_items": row["open_items"],
                                  "baseline": shown(A2[cid]), "candidate": shown(B2[cid])})
    unlabeled = []
    for cid in paired:
        if A2[cid]["valid_output"] and B2[cid]["valid_output"]:
            for crit, cell in sorted(A2[cid]["cells"].items()):
                other = B2[cid]["cells"].get(crit)
                if (cid, crit) not in labeled_cells and other and cell["response"] != other["response"]:
                    unlabeled.append({"conversation_id": cid, "criterion_id": crit,
                                      "baseline": cell["response"], "candidate": other["response"]})
    new_issues, resolved = [], []
    for cid in paired:
        a, b = _issue_keys(A2[cid]), _issue_keys(B2[cid])
        new_issues += [{"conversation_id": cid, "criterion_id": k[0], "invariant": k[1], "message": k[2]}
                       for k in sorted(b - a, key=str)]
        resolved += [{"conversation_id": cid, "criterion_id": k[0], "invariant": k[1], "message": k[2]}
                     for k in sorted(a - b, key=str)]
    totals, total_skipped = [], Counter()
    for cid in paired:
        ta, tb = A2[cid]["total"], B2[cid]["total"]
        if ta is None or tb is None:
            total_skipped["baseline invalid" if ta is None and tb is not None else
                          "candidate invalid" if tb is None and ta is not None else "both invalid"] += 1
        else:
            totals.append({"conversation_id": cid, "baseline": round_half_up(ta), "candidate": round_half_up(tb),
                           "difference": round_half_up(tb - ta), "difference_exact": str(tb - ta)})
    base_summary = run_summary(base_run, A2, rows, spec, demo)
    cand_summary = run_summary(cand_run, B2, rows, spec, demo)
    cf_changes = {}
    for cf_id, outcome in cand_summary["counterfactuals"].items():
        before = base_summary["counterfactuals"].get(cf_id)
        if before is not None:
            cf_changes[cf_id] = {cid: {"baseline": before[cid], "candidate": outcome[cid]} for cid in outcome}
    statuses = {base_summary["measurement_status"], cand_summary["measurement_status"]}
    return {"split": split, "paired_cases": paired, "unpaired": unpaired,
            "measurement_status": "genuine_model_outputs" if statuses == {"genuine_model_outputs"} else
            "demonstration_only" if demo else "not_assessed (or partial)",
            "baseline": base_summary, "candidate": cand_summary,
            "validation_transitions": dict(validation),
            "label_transitions": {f"{tier}: {kind}": n for (tier, kind), n in sorted(transitions.items())},
            "fixed": details["fixed"], "regressed": details["regressed"], "still_wrong": details["still_wrong"],
            "changed_unlabeled": unlabeled, "new_invariant_violations": new_issues,
            "resolved_invariant_violations": resolved, "counterfactual_changes": cf_changes,
            "total_differences": totals, "total_differences_skipped": dict(total_skipped)}


HOLDOUT_DETAIL_KEYS = ("fixed", "regressed", "still_wrong", "changed_unlabeled", "new_invariant_violations",
                       "resolved_invariant_violations", "counterfactual_changes", "total_differences")


def redact_for_holdout(report):
    """Holdout: aggregate counts only, so per-cell labels cannot steer tuning."""
    for key in HOLDOUT_DETAIL_KEYS:
        if key in report:
            report[key] = f"withheld on holdout ({len(report[key])} items)"
    for side in ("baseline", "candidate"):
        if side in report:
            report[side]["counterfactuals"] = "withheld on holdout"
    report["holdout_notice"] = ("Holdout result. If it informs any engine or prompt change, the holdout is "
                                "exposed: record that and freeze a new holdout before the next claim.")
    return report


def _fmt_metrics(lines, summary):
    for tier, m in summary["label_metrics"].items():
        lines.append(f"    {tier}: {m['match']}/{m['cells']} exact match ({m['invalid']} invalid outputs)")
        for cid, c in m["by_criterion"].items():
            lines.append(f"      {cid}: {c.get('match', 0)}/{c['labeled']}" +
                         (f" ({c['invalid']} invalid)" if c.get("invalid") else ""))
        lines.append("      by language: " + ", ".join(f"{k} {v.get('match', 0)}/{v['labeled']}"
                                                       for k, v in m["by_language"].items()))
        if m["na_confusion"]:
            lines.append(f"      N/A confusion: {m['na_confusion']}")
        if m["critical_08"]:
            lines.append(f"      08 confusion: {m['critical_08']}")
        if m["total_error"]["cases"]:
            lines.append(f"      total MAE: {m['total_error']['mean_absolute_error_display']} "
                         f"over {m['total_error']['cases']} fully labelled case(s)")
    if summary["excluded_labels"]:
        lines.append(f"    excluded (not scored): {summary['excluded_labels']}")


def render(report):
    lines = ["CQA Accuracy Lab - paired comparison", ""]
    if report["measurement_status"] != "genuine_model_outputs":
        lines += ["!! " + (NOT_A_MEASUREMENT if report["measurement_status"] == "demonstration_only" else
                           "Some outputs are mock/test doubles: their label cells are not assessed."), ""]
    for side in ("baseline", "candidate"):
        s = report[side]
        lines.append(f"{side.title()}: {s['run_id']} @ engine {s['engine_commit']}  origins={s['origins']}")
        lines.append(f"  {s['description']}")
        for provider, model, prompt, checklist in s["engine_runs"]:
            lines.append(f"  provider={provider} model={model} prompt={prompt} checklist={checklist}")
    lines += ["", f"Split: {report['split']}   paired cases: {len(report['paired_cases'])}   "
                  f"unpaired: {len(report['unpaired'])}"]
    for u in report["unpaired"]:
        lines.append(f"  unpaired {u['conversation_id']}: {u['reason']}")
    lines += ["", "Validation (engine verdict per case): " + str(report["validation_transitions"])]
    for side in ("baseline", "candidate"):
        s = report[side]
        lines.append(f"  {side}: accepted {s['accepted']}/{s['cases']}, source preserved "
                     f"{s['source_preserved']}/{s['cases']}, invariant violations {s['invariant_violations'] or 0}, "
                     f"evidence {s['evidence']}")
    lines += ["", "Label cells (paired, identical cells):"]
    for key, n in report["label_transitions"].items():
        lines.append(f"  {key}: {n}")
    for side in ("baseline", "candidate"):
        lines.append(f"  {side} metrics:")
        _fmt_metrics(lines, report[side])
    for key in ("regressed", "fixed", "still_wrong"):
        value = report[key]
        if isinstance(value, str):
            lines.append(f"\n{key.title()}: {value}")
            continue
        lines.append(f"\n{key.title()} ({len(value)}):")
        for d in value:
            note = f"  [open: {', '.join(d['open_items'])}]" if d["open_items"] else ""
            lines.append(f"  {d['conversation_id']} C{d['criterion_id']} label={d['label']} "
                         f"baseline={d['baseline']} candidate={d['candidate']} ({d['tier']}){note}")
    for key, title in (("new_invariant_violations", "New invariant violations"),
                       ("resolved_invariant_violations", "Resolved invariant violations")):
        value = report[key]
        lines.append(f"\n{title}: " + (value if isinstance(value, str) else str(len(value))))
        if not isinstance(value, str):
            for d in value:
                lines.append(f"  {d['conversation_id']} C{d['criterion_id'] or '-'} {d['invariant']}: {d['message']}")
    value = report["changed_unlabeled"]
    lines.append("\nChanged responses on unlabelled cells: " + (value if isinstance(value, str) else str(len(value))))
    if not isinstance(value, str):
        for d in value:
            lines.append(f"  {d['conversation_id']} C{d['criterion_id']}: {d['baseline']!r} -> {d['candidate']!r}")
    value = report["counterfactual_changes"]
    lines.append("\nCounterfactual pairs (INV-CF-MONO and label flip):" + (" " + value if isinstance(value, str) else ""))
    if not isinstance(value, str):
        for cf_id, crits in value.items():
            for cid, change in crits.items():
                b, c = change["baseline"], change["candidate"]
                lines.append(f"  {cf_id} C{cid}: baseline {b['base']}->{b['variant']} monotonic={b['monotonic']} "
                             f"flip={b['label_flip']} | candidate {c['base']}->{c['variant']} "
                             f"monotonic={c['monotonic']} flip={c['label_flip']}")
    value = report["total_differences"]
    lines.append("\nTotal score differences (only where both totals are valid):" +
                 (" " + value if isinstance(value, str) else ""))
    if not isinstance(value, str):
        for d in value:
            lines.append(f"  {d['conversation_id']}: {d['baseline']} -> {d['candidate']} ({d['difference']})")
    if report["total_differences_skipped"]:
        lines.append(f"  not compared: {report['total_differences_skipped']}")
    if "holdout_notice" in report:
        lines += ["", report["holdout_notice"]]
    return "\n".join(lines) + "\n"
