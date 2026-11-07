# Evaluation quality and submission readiness — decision memo and comparison plan

Date 2026-11-07. Branch `feature/cqa-atomic-reliability`. Nothing here is an
official accuracy claim: no independently verified per-conversation labels exist.

## 1. Frozen experimental candidate

Local annotated tag `candidate/atomic-v5-checklist-v5-exp` -> `192f1e8`:
`atomic-v5` schema + draft checklist `2026-11-07.v5`. Explicit opt-in only; the
engine default (atomic-v2 on atomic checklists, legacy v3 checklist in the web app)
is unchanged. All seven genuine replies (all synthetic p1-ru-001,
gpt-5.4-mini-2026-03-17) are tracked fixtures under `tests/fixtures/`:

| Fixture | Path / version | Outcome | Limitation |
| --- | --- | --- | --- |
| live_first | legacy v2 | rejected 02/04/07 | model-owned N/A contradictions |
| live_c379231 | legacy v2 | rejected 05/08 | answer/rule contradiction; missing scope |
| live_f4599f0 | legacy v3 | rejected 03 | N/A contradiction; evidence role |
| live_atomic_5d256ac | atomic-v1, rubric v4 | rejected 03/05/07 | missing scopes, missing C07 judgment |
| live_atomic_v3_a958142 | atomic-v3, rubric v4 | accepted 76.92 | C06=0 grammar-forced; untrustworthy |
| live_atomic_v4_2fcd958 | atomic-v4, rubric v5 | rejected 04 | duplicate 04.q1 |
| live_atomic_v5_f20d00d | atomic-v5, rubric v5 | accepted 100.00 | 07.q2 doubtful (below) |

Raw API requests/responses stay in ignored `outputs/` folders of the integration
and reliability worktrees (local only; copy them before deleting a worktree).
One conversation cannot support any accuracy conclusion.

## 2. C07 investigation

Official text (original checklist PDF p.1, SHA256 `2f6908c3…7808`, matches the
spec): «Да — оператор подвёл итог или предложил дальнейшую помощь и попрощался.
N/A — чат оборвался до возможности его завершить.» Spec Open A08 records that the
AND/OR grouping is not formalized; the working reading is (summary OR offer) AND
farewell.

Transcript end: customer «Нашла, спасибо.» -> operator «Пожалуйста. Хорошего вечера!»
— an acknowledgement and a farewell; no restatement of the solution, no offer of
further help.

Findings:
- The grouping ambiguity does **not** decide this case: under either reading
  ((summary OR offer) AND farewell, or summary OR (offer AND farewell)) a literal
  application requires a summary or an offer, and neither is explicit here.
- The decision came from **model interpretation**, consistently: 7/7 genuine
  replies across legacy and atomic prompts answered 07.q2=yes, each crediting
  «Пожалуйста»/«Хорошего вечера» as summary/offer ("implicitly", "functions as").
  It is not caused by v5 or the schema.
- The rubric **contributes**: 07.q2 ("Did the operator summarize or offer further
  help?") and the C07 instructions define neither term and give no negative
  example; the official illustration covers only a missing farewell. The model
  fills the gap leniently and repeatably — a systematic bias that would affect
  many DEV chats (C07 weight 5; on p1-ru-001 the difference is 100.00 vs 92.31).
- Not established: whether organizers would accept an acknowledgement after
  confirmed resolution as «подвёл итог». That is a calibration question for a
  human reviewer/organizer, not something to encode as ground truth. If the team
  adopts the literal reading, the minimal fix is a definition in the C07
  instructions (e.g. "a courtesy or farewell alone is neither a summary nor an
  offer of further help") in a reviewed checklist version — not a schema change.

## 3. Out-of-sample comparison (plan; needs separate paid authorization)

**Arms** (same model `gpt-5.4-mini-2026-03-17`, same normalized inputs, same
rubric content, validators, evidence gates and deterministic scorer):
- A — atomic-first: checklist v5, `prompt_version=atomic-v5`, repair OFF.
- B — direct-rubric control: v5 content with `decision_path="legacy"` built in
  memory (no new file/code), existing `baseline-v4` prompt; model gives final
  responses plus the same atomic questions; schema ~3 KB vs ~41 KB.
- Optional A+R: arm A rejections only, one bounded repair each, reported separately.

**Sample** (9 conversations, metadata-only, deterministic: per language, SHA256
order of `cqa-compare-v1:<id>`, slots = ends-with-system / >=20 turns / first by
hash; excluded p1-ru-001 (tuned on) and QA counterfactual sources p1-ru-006,
p1-en-009 (holdout exposure)):
RU p1-ru-026, p1-ru-027, p1-ru-014 · KZ p1-kz-013, p1-kz-003, p1-kz-010 ·
EN p1-en-013, p1-en-006, p1-en-011. No QA holdout case is used.

**Counterfactual pairs** (in-memory edits via the QA harness edit mechanism; the
only QA calibration-split counterfactual plus two new pairs on sampled chats):
cf-en-009-remove-intro (C01 must not improve); remove the final operator farewell
from p1-en-011 (C07 must not improve); append one operator insult to p1-ru-014
(C08 must become yes with that quote). Directional assertions only.

**Budget**: 18 sample calls + 6 counterfactual-edited calls (originals reused) = 24
calls, no retries; est. USD 0.25–0.55 (A ~0.013–0.023, B ~0.006–0.018 per call).
Optional A+R adds at most one call per arm-A rejection.

**Measures** (all reported per arm and per language):
1. Structural acceptance: accepted conversations / attempted; per-criterion valid
   rate; rejection classes.
2. Semantic disagreements: every (conversation, criterion) where both arms
   validated and differ. A team reviewer, blind to arm, marks each as
   *defensible* (official text decides it) or *ambiguous*, and which side the
   text supports. Labelled `team_human`, never official Ground Truth. Known
   targeted check: C07 summary/offer leniency.
3. Counterfactual consistency: share of directional assertions satisfied.
4. Latency (provider p50/max), tokens (input/cached/output) and USD cost per
   accepted evaluation; run arms in alternating order to limit cache bias.
5. Mandatory statement: official accuracy cannot be established without verified labels.

**Pre-registered decision rule**: prefer arm B (lean) as production default if its
acceptance is >= A's and it has no more text-supported defensible errors; prefer A
if it is strictly better on acceptance or defensible errors; on a tie, prefer the
cheaper/faster arm. Do not tune prompts on these nine before the decision.

## 4. Submission pipeline (exporter PR #2) — compatibility and minimum steps

Verified read-only plus a throwaway merge in a scratch worktree (removed; exporter
worktree untouched): `feature/cqa-results-export` (5521151) and this branch share
base 6481390; the only common file is PROJECT_FILE_MAP.md and it auto-merges.
Merged tree: 200 tests run, 199 pass, 1 expected skip; independent QA 81/81. The
exporter's checklist guard accepts v3, v4 and v5 (IDs/kinds/weights/levels/N/A
unchanged). `repair_attempts` is additive; repair is not reachable from the batch.

Gap: `cqa_results/batch.py` builds `EvaluationConfig` without `prompt_version`, so an
atomic checklist runs the compatibility `atomic-v2` schema. Minimum steps:
1. Merge PR #2 and this branch into the integration branch (clean merge).
2. Add one `--prompt-version` option to `batch.py` (default unchanged) on the
   integration branch — after the exporter owner agrees, not in their worktree.
3. Choose the production pair from section 3 (A = v5 + `--prompt-version atomic-v5`,
   or B = direct control, which needs the v5-direct checklist saved as a file).
4. Resolve data permission: the 65 DEV include 5 real voice calls and PROD 10 are
   organizer controls; external OpenAI export needs owner-provisioned grants.
5. Dry-run (mock) 65+10, then the authorized real batch with `--live-call-limit`,
   export, strict validate, verify remote, per the runbook.
Estimated real batch: 75 calls, ~14 s each (~6 min with 3 workers), roughly
USD 1–2; rejections become `status:"error"` records, never zero scores.

## 5. Recommendation

Do not adopt atomic-v5 as default yet, and do not patch it further on p1-ru-001.
**Test the lean alternative against atomic-first before choosing** — one small
authorized comparison (section 3, ~24 calls, < USD 1), then pick the default by
the pre-registered rule. Meanwhile, unblock submission in parallel: merge PR #2
with this branch, add `--prompt-version`, and settle data permissions, so the
65 DEV + 10 PROD batch can run immediately after the decision. Separately, ask a
human reviewer to rule on the C07 summary/offer reading before the batch.
