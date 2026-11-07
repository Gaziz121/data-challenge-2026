# CQA Accuracy Lab (offline)

The lab measures whether a change to the Evaluation Engine improves CQA decisions
on the same conversations. It reads outputs the engine has already saved and
compares a baseline run with a candidate run, cell by cell. It never calls a
model, never changes a decision and never feeds labels to the engine.

Nothing here is official Ground Truth. Every label is either a QA proposal written
by an AI agent (`team_qa_synthetic`) or a team reviewer's Viewer export
(`team_human`). Neither is official.

## Commands

Run everything from the QA worktree root, with an engine `src` on `PYTHONPATH`.
To pin an exact engine commit without touching another worktree, export a
read-only snapshot first:

```sh
ENGINE=/tmp/cqa-engine-c379231
mkdir -p $ENGINE && git archive c379231 src data/shared | tar -x -C $ENGINE
export PYTHONPATH=$ENGINE/src
```

```sh
python3 -B -m unittest discover -t . -s qa -v           # all QA tests, including qa/test_lab.py
python3 -B -m qa.lab demo --engine-commit c379231        # scripted demo, prints a paired report
python3 -B -m qa.lab ingest FILE... --out outputs/lab/RUN --run-id RUN --engine-commit SHA --description TEXT
python3 -B -m qa.lab report  --run outputs/lab/RUN [--split calibration|holdout|unassigned|all]
python3 -B -m qa.lab compare --baseline outputs/lab/A --candidate outputs/lab/B [--human-labels X.json ...]
python3 -B -m qa.lab make-split --out outputs/lab/dev-split.json   # proposed DEV split, metadata only
```

`--json-out FILE` writes the full report to a new file. No command overwrites an
existing file or directory. `outputs/` is git-ignored.

## Inputs

**Runs.** A run is a directory holding one saved engine artifact per conversation
plus `run.json` (`run_id`, `engine_commit`, `description`). `ingest` builds one from
the engine's own files without changing them:

* `EvaluationResult` JSON, the app's accepted results (`outputs/app/<id>.json`);
* rejected diagnostics (`outputs/app/rejected-<id>.json`, status `validation_failed`).

Each artifact embeds its conversation and checklist. The lab checks against
those embedded copies, after verifying the conversation against the source record.
It does not use the engine's validator, so an engine change cannot loosen the
yardstick.

**Origin.** The lab sets each artifact's origin from the artifact itself, never from a
claim in `run.json`: `mock` (`is_mock`), `test_double` (provider `qa-*`), otherwise
`model`. Only `model` outputs are scored. Mock and test-double label cells are
reported as `not_assessed`. `--demo-mechanics` computes agreement for them anyway,
and the report then opens with a banner saying it is not a semantic accuracy
measurement.

**Labels.** There are two sources, and they are never blended:

| Tier | Source | Scored? |
| --- | --- | --- |
| `deterministic_invariant` | `label_registry.json` `invariants` (INV-SRC, -RESP, -APPL, -ATOM, -EVID, -POLICY, -CRIT, -TOTAL, -CF-MONO) | Checked on every output; label-free |
| `proposed_unreviewed` | 30 rows of `qa/scenarios/semantic_v1.json` with a single expected response | Exact match, reported as unreviewed AI proposals |
| `ambiguous` | 4 rows where the checklist allows more than one answer (open items A05, A07, section 5) | Counted as excluded, never scored |
| `team_human` | Viewer exports (`--human-labels`) | Exact match; one reviewer, or several who agree exactly |
| `disputed` | Human reviewers who disagree | Excluded and listed; no consensus merging |

The human import reads the Viewer's actual export contract (`dev-team-human-1`,
`tools/dev_review/viewer.js` `bundle` at `c379231`). It requires
`label_source=team_human` and `official_ground_truth=false`, and the dataset SHA256
must match the source file. Language and channel must match the source record,
and every evidence object must equal the source turn exactly (index, timestamp,
speaker, text). Unscored (`null`) cells are skipped and never treated as zero
or N/A. Nothing else is assumed. The Viewer has no adjudication format, so the
lab does not invent one.

## Calibration and frozen holdout

`splits/synthetic_v1.json` splits the synthetic fixtures using metadata only.
Inside each stratum (EN, RU, KZ, counterfactual), groups are ranked by
SHA256(seed:group_id), and floor(0.4n + 0.5) of them go to holdout. That is the
8/20 ratio proposed in `case/CQA_REQUIREMENTS.md` section 4A. A counterfactual's
base and variants always stay on one side.

| Split | Conversations | Scored rows | Ambiguous rows |
| --- | --- | --- | --- |
| calibration | 13 | 16 | 3 |
| holdout | 12 | 14 | 1 |

* The default is `--split calibration`. Tune only on calibration.
* `--split holdout` refuses to run without `--holdout-confirm`, and it prints
  aggregate counts only, with no per-cell labels or diffs.
* The split stores a hash of every holdout label row. If a holdout label is edited,
  loading the split fails (`FrozenHoldoutChanged`). Once a holdout result informs a
  change, record the exposure and freeze a new holdout.
* The DEV benchmark split is not selected yet: `make-split` writes a proposed
  metadata-only manifest (3 calibration and 2 holdout per language/channel). That
  file must be passed with `--split-manifest`. Choosing to adopt it is a team
  decision under section 4A.

## What the comparison reports

These follow case/CQA_REQUIREMENTS.md section 4C. They are internal diagnostics,
not the organizer's metric.

* **Validation:** engine verdict per case (`accepted -> rejected`, and so on), source
  preservation (INV-SRC), and invariant violations that are new or resolved per case.
* **Label cells:** paired transitions on identical cells: `fixed`, `regressed`,
  `still_correct` and `still_wrong`, with the regressions listed first. A rejected
  output is `invalid`: no valid decision exists, and it counts as not correct.
* **Per run:** exact match by criterion and language, N/A confusion, a confusion
  table for 08 (misses and false alarms), and total-score MAE. The MAE appears only
  where every weighted criterion has a single label.
* **Unlabelled cells:** any response that changed.
* **Evidence:** exact, formatting-only and invalid quotes, counted on the
  original model output.
* **Counterfactuals:** INV-CF-MONO, meaning the edited variant is never more favorable,
  and whether both labels flip.
* **Total difference:** only where both runs have a total that reconciles with an
  exact-fraction recomputation (INV-TOTAL). Other cases are counted as skipped.

## Baseline versus a Socrates-improved engine

1. Freeze the inputs: the checklist version, the conversations (calibration only
   while iterating) and the labels. Do not edit labels to match a candidate.
2. Run the baseline engine commit on those conversations and save every result,
   including rejections. `ingest` them into `outputs/lab/baseline-<sha>`.
3. Make the change on its own commit and run the identical conversations again.
   Ingest the results into `outputs/lab/candidate-<sha>`.
4. Run `compare --baseline ... --candidate ...`. Read the regressions and the new
   invariant violations before the counts. A candidate improves only if it fixes
   more cells than it regresses on the same cells, adds no invariant violations,
   and does not lose valid outputs. Ambiguous and disputed rows are not evidence
   either way.
5. When calibration looks better, run the holdout once with `--holdout-confirm`
   and record the result and the exposure.

The model is stochastic. Run each side more than once, using one run directory
per repetition, before reading a single fixed or regressed cell as a real change.

## Demonstration (scripted, not a measurement)

`demo/baseline.json` and `demo/candidate.json` are hand-written outputs for 7
calibration conversations. `demo` replays them through the engine on `PYTHONPATH`
with the `qa-scripted` test double, in a temporary directory, and compares them.
Against `c379231` it shows:

* 2 rejected → accepted validation transitions;
* 4 fixed cells and 1 deliberate regression (`qa-kz-positive-control` C07 yes → no);
* 1 ambiguous cell excluded and 1 changed unlabelled cell (C06 10 → 7);
* 5 formatting-only quotes accepted under `quote_policy=normalize_formatting`;
* the counterfactual label flip on `cf-en-009-remove-intro`;
* total differences on the 5 cases that are valid in both runs.

These numbers show only how the lab works. They measure no model.

## Known limits

* The demo uses scripted outputs. The only genuine model output available
  (`rejected-a94e48f7`, n=1) is rejected, so no accuracy has been measured.
* Proposed labels were written by an AI QA agent and still need a language-competent
  human review. KZ coverage is small (4 scenarios).
* Synthetic fixture outputs come only from the test double, because the engine's
  external gate rejects team-authored conversations for real providers (QA-C08).
* Lab checks read the checklist schema of `c379231` (`evidence_policy`,
  `applicability_rule`, `consistency_rules`). Check the lab against any later
  checklist schema before trusting its results.
