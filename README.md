# 24-Hour Data Challenge

Fast infrastructure. Deep investigation. Verified evidence. Strong deliverables.
The case, dataset, scoring, team, and permitted tools are not known yet. Do not
invent them or assume that machine learning is required.

## Start here

1. Read [CLAUDE.md](CLAUDE.md) and the current [STATUS.md](STATUS.md).
2. Inspect existing work and run `python3 -B src/git_preflight.py`. It is a local,
   read-only check, not proof of GitHub freshness. Follow
   [GIT_WORKFLOW.md](GIT_WORKFLOW.md) before synchronizing or sharing.
3. After release, reverse-engineer the official requirements before coding.
   Use [ANALYSIS.md](ANALYSIS.md) for investigation, independent validation,
   reproducible filtering, and final-deliverable checks.
4. Maintain one status/evidence record in `STATUS.md`. It identifies authoritative
   files, owners, open decisions, and evidence; do not duplicate it across logs.

`STATUS.md` stays local by default. A fresh clone will not contain it: obtain the
authoritative record from the integration owner through an approved handoff,
rather than starting a competing ledger. Current environment checks live there.

## Workspace

```text
data/raw/        Original inputs; preserve unchanged
data/processed/  Derived data that can be recreated from the originals
notebooks/       Exploratory notebooks, when a notebook environment is available
src/             Python analysis and reusable calculations, as needed
outputs/         Verified charts and summary tables
deliverables/    Final submission files in the organizer's required format
```

`src/git_preflight.py` checks repository state; no analytical pipeline, dataset,
model, notebook, or presentation is prebuilt. Empty folders are local conveniences
and are not stored by Git. Use only what the case needs; Excel or one script may
be sufficient. Give each notebook or workstream one owner and designate an
integration owner. Use short branches only when concurrent coding warrants them.

## After the case is released

1. Read the brief and rules before coding. Confirm the deadline and timezone,
   scoring, required files, submission procedure, AI rules, external-data rules,
   and permitted data storage. Record the agreed objective and owners in
   `STATUS.md`; distinguish official requirements from team preferences.
2. Put permitted original inputs in `data/raw/`. Inspect the unit of analysis,
   keys, units, dates, missing values, duplicates, and coverage. Reconcile row
   counts and key totals before and after cleaning or joins.
3. Agree on definitions and produce the simplest valid baseline. Choose the
   method from the case; do not assume machine learning is needed.
4. Explore a few questions that could change the answer. Record only material
   assumptions and decisions. Verify headline calculations independently.
5. Save verified outputs with clear names. Record their source calculation,
   inputs, filters, and limitations in the evidence ledger in `STATUS.md`. Connect each
   finding to its practical implication without overstating the evidence.
6. Build the required deliverable alongside analysis. Reserve the final hours
   for rerunning critical calculations, checking every headline number,
   reviewing requirements, and submitting with recovery time remaining.

## Reproducibility and confidentiality

- Run from the project root with relative paths. Keep raw inputs unchanged;
  record input versions and important transformations.
- Keep the final analytical path clear. Rerun notebooks from a fresh kernel
  or scripts from the original inputs before relying on their outputs.
- Once tools are chosen, record the exact run steps and versions actually used
  in `STATUS.md`. Add a dependency file only when needed; install nothing by default.
- `.gitignore` excludes data, generated outputs, final files, local evidence,
  credentials, and temporary artifacts. It does not control access, untrack
  existing files, or prevent uploads. Review every proposed upload explicitly.
- Do not upload files or data to external services without explicit permission
  and organizer approval. Check notebook outputs and derived tables for sensitive
  information too. Use AI only as permitted; humans approve final conclusions.

## Adaptable 24-hour plan

| Hours | Focus | Gate |
| --- | --- | --- |
| 0–2 | Official requirements, criterion-to-evidence map, data audit, owners | Minimum valid submission and data issues understood |
| 2–5 | Trusted definitions, competing hypotheses, simple baseline | A reproducible baseline and draft deliverable structure exist |
| 5–13 | Prioritized deep investigation and incremental verification | Produce an end-to-end candidate by about hour 10–12 |
| 13–18 | Challenge findings, sensitivity checks, integration | Select final approach; freeze major changes of direction |
| 18–22 | Finish actual artifacts, rerun, reconcile, review | Critical claims verified; files open and meet requirements |
| 22–24 | Critical corrections, fallback, submission and receipt | Submit with recovery time and verify confirmation |

These are adjustable milestones. Build deliverables as verified evidence emerges.
Timebox exploratory tasks, but allow deeper work when it can change the decision,
score, or confidence in a consequential conclusion. Protect validation and
submission time; do not keep exploring at the expense of a working submission.
