# Results submission runbook (organizer appendix, JSON 1.0)

Authority: organizer appendix *«Как сдать результаты»* (`CQA_Student_Guide_Appendix_Results.pdf`,
3 pages, local original in the owner's Downloads; not committed). This runbook applies it
to the code in `src/cqa_results/`. Where this file and the appendix disagree, the appendix wins.

## 0. FROZEN production configuration and final command sequence (use this; older sections are background)

Owner decision 2026-11-07: checklist **v7** (`src/cqa/checklists/official-v7.json`, sha256 `02e1f9e9…fafd0`) +
prompt **atomic-v5** + **opt-in review evidence gate** + `gpt-5.4-mini-2026-03-17`, bounded one-call repair,
`normalize_formatting` quotes, 8000 output tokens, 90 s timeout, 3 workers — all in `tools/production.env`,
pinned by tests and re-checked by the script before every paid step. v7 FAILED pre-registered C01 criterion 1
(one wrong-language false Yes shared with v6) and was selected because it improved over v6 without observed
regressions on the paired sample (2 fixes, 0 regressions, n = 17). Prompt and checklist are frozen: no v8.

All steps go through `tools/final_submission.sh` (paid steps refuse without `CQA_PAID_OK=yes`; official
`results/` files are written only from runs made with the frozen configuration and a real team name):

```sh
sh tools/final_submission.sh check
# DEV (needs approval; 60 synthetic chats sent, the 5 real calls stay honest errors without a grant)
CQA_PAID_OK=yes ENV_FILE=/path/to/ignored/.env sh tools/final_submission.sh dev-batch
CQA_PAID_OK=yes ENV_FILE=... sh tools/final_submission.sh resume dev outputs/submission/dev-final-<stamp>   # optional, once
sh tools/final_submission.sh export dev outputs/submission/dev-final-<stamp>                      # validation copy
TEAM_NAME='<registered name>' sh tools/final_submission.sh export dev outputs/submission/dev-final-<stamp>
# PROD (final hour)
read -rs CONTROL_URL; export CONTROL_URL; sh tools/final_submission.sh prod-fetch
sh tools/final_submission.sh prod-check
PERMISSION_REF='<organizer rule reference>' sh tools/final_submission.sh prod-grants
CQA_PAID_OK=yes ENV_FILE=... sh tools/final_submission.sh prod-batch
CQA_PAID_OK=yes ENV_FILE=... sh tools/final_submission.sh resume prod outputs/submission/prod-final-<stamp>  # once, if time
TEAM_NAME='<registered name>' sh tools/final_submission.sh export prod outputs/submission/prod-final-<stamp>
#   out of time: add UNATTEMPTED_REASON='Not evaluated before code stop: <cause>' to the export
# Publish (on a checkout of the submission branch itself; refuses divergence, staging extras, force)
TEAM_NAME=... SUBMIT_REPO=Gaziz121/data-challenge-2026 SUBMIT_REF=<branch> sh tools/final_submission.sh submit
SUBMIT_REPO=... SUBMIT_REF=... sh tools/final_submission.sh verify dev
SUBMIT_REPO=... SUBMIT_REF=... sh tools/final_submission.sh verify prod
```

Previous runs (`dev-run1`, `gate-v6`, `c01-compare/*`) are never overwritten: each batch gets a new timestamped
directory. Expected DEV outcome from the measured gate: roughly 40–45 of 60 chats scored, the rest honest errors.

## 1. What the organizers require (appendix pp. 1-3)

| Requirement | Source | Enforced by |
| --- | --- | --- |
| `results/dev/results.json` (65 = 60 chats + 5 calls) and `results/prod/results.json` (exactly 10 controls, errors included) at repository root | p.1, p.3 | validator `--set dev/prod` |
| Both files committed **and pushed** to the open repository at the URL given to organizers, before code stop. Local save or unpushed commit is not enough | p.1 | step 7-8 below (`verify_remote`) |
| Controls arrive 23 h after start, via an organizer API; code stop at 24 h. The hour covers fetching, evaluation, checking and pushing | p.1 | time budget below |
| Original `conversation_id`s exactly as in the API; one record per dialog; no gaps or duplicate IDs | p.1, p.3 | exporter + validator |
| Top level `schema_version:"1.0"`, `team_name`, `model:{mode,name}`, `results[]`; `mode` ∈ local / external_api / hybrid; `name` = model(s) actually used | p.2-3 | exporter (from engine run metadata) + validator |
| `ok` record: all 8 criteria exactly once: contact bool; discovery bool/null; identification bool/null; consultation 0/5/10/15/20/null; empathy bool; dialogue 0/4/7/10; closure bool/null; critical bool. null = N/A | p.3 | validator |
| `evidence_turns`: 1-based indexes over the ORIGINAL transcript array incl. client, bot and events; never operator-only renumbering | p.3 | exporter mapping + validator range check |
| `final_score` 0-100, two decimals; N/A criterion excluded and its weight redistributed proportionally. Weights 10/15/20/20/15/15/5, critical unweighted | p.3 | engine exact scoring, re-checked independently |
| `critical_flag` = value of `critical`; does **not** zero the total | p.3 | validator |
| Failure: `status:"error"`, `criteria:[]`, `score:null`, real reason in `error`; never hidden, never a zero score | p.3 | exporter + validator |
| UTF-8, no comments, no trailing commas | p.3 | validator (also rejects BOM, NaN, duplicate keys) |

Unknown until organizers publish it: control API URL, authentication, payload shape, and
access rules. Nothing here assumes them. Do not guess an endpoint.

## 2. How the code maps engine output (no engine logic changed)

* Internal criteria `01..08` → `contact, discovery, identification, consultation, empathy,
  dialogue, closure, critical`. The exporter refuses any checklist whose IDs, kinds, weights,
  levels or N/A permissions differ from the appendix table (v3 and v4 both match).
* `yes/no` → `true/false`; `"N/A"` → `null`; discrete integers unchanged.
* Rationale = the validated engine decision rationale, unmodified (trimmed whitespace only).
* `evidence_turns`: engine message `mNNNN` has `source_index` NNNN (0-based position in the
  original `transcript` array, enforced by the engine contract). Exported index =
  `source_index + 1`, looked up by message ID, never parsed from the ID text. A quote maps to
  its one turn and is re-checked as a substring of that ORIGINAL turn text; a scope/omission
  locator maps to every turn it spans (inclusive). So "no critical violation" (which the
  engine proves with a full-transcript scope) lists all turns `1..N`.
* `final_score` = engine `score.total_score` (exact rational, HALF_UP 2 dp), after the
  exporter re-runs `cqa.scoring.score_evaluation` and requires identical results.
* Status mapping: engine `EvaluationResult` → `ok` (`needs_review` results are engine-accepted
  and exported as ok; the export report counts them). `EvaluationRejected` diagnostic,
  `CheckBlocked`, `ProviderError`, `AccessDenied`, normalization failure or any other
  exception → `error` with a safe reason. The exporter aborts (writes nothing) on a missing,
  duplicated, malformed, tampered or foreign outcome, a dataset mismatch, or mock output
  without `--allow-mock`. Dry-run/mock files can only be written under `outputs/`.
* `model.name` = sorted distinct `model_returned` values; `mode` from the provider
  (`openai` → `external_api`, mock → `local`, mixed → `hybrid`).

Modules: `batch.py` (run the unchanged engine per conversation), `export.py`, `validate.py`
(stdlib only, independent of the engine), `grants.py` (owner approvals), `verify_remote.py`,
`dryrun.py`. Tests: `tests/test_results_submission.py`.

## 3. Preparation before hour 23 (do once; owner + one teammate)

Run everything from the checkout root of the branch that contains this code, with
Python 3.9+ and pydantic 2.

```sh
export TEAM_NAME='<exact team name registered with organizers>'
export SUBMIT_REPO='<owner>/<repo>'        # the OPEN repository in the URL given to organizers
export SUBMIT_REF='<branch in that URL>'   # usually main
export CQA_MODEL='<exact OpenAI model id>'
python3 -B src/git_preflight.py
PYTHONPATH=src python3 -B -m unittest discover -s tests          # all must pass
PYTHONPATH=src python3 -B -m cqa_results.dryrun --out outputs/submission-dryrun/$(date +%H%M%S)
PYTHONPATH=src python3 -B -m cqa_results.rehearsal --out outputs/rehearsal/$(date +%H%M%S)   # must print REHEARSAL PASSED
gh repo view "$SUBMIT_REPO" --json visibility                    # must be PUBLIC
test -f .env && echo ".env present (do not print it)"
```

Decide and record (in `STATUS.md`) before the controls arrive:
1. Exact team name, submitted repo URL and branch.
2. Evaluator pair and model, chosen by the explicit procedure below, and whether organizer rules
   permit sending control transcripts to OpenAI. Real batch runs REFUSE to start without explicit
   `--checklist` and `--prompt-version` (no silent fallback to the legacy v3 default).
3. Whether the 5 real DEV calls may be sent to OpenAI. Without an explicit owner grant the
   engine refuses to transmit them, and they become honest `error` records.
4. Who presses commit/push on the submission branch (one person).

### Evaluator selection procedure (decide once, then freeze)

| Pair | Evidence | Role |
| --- | --- | --- |
| `official-v6.json` + `atomic-v5` | v5 content with only C07 wording clarified (farewell alone is not a summary/offer of help) | Production candidate; NOT yet called live |
| `official-v5.json` + `atomic-v5` | 1 genuine call on synthetic p1-ru-001: structurally accepted (100.00); C07 judged generously | Fallback |
| `official-v3.json` + legacy `baseline-v4` (direct rubric) | 3 genuine legacy replies, all rejected by validation | Not used unless a paired comparison changes this |

Gate (needs owner authorization for ~3 paid calls, about USD 0.05): run v6 + atomic-v5 on one RU, one KZ
and one EN synthetic chat (the KZ/EN IDs are from the comparison plan's hash-selected set):
```sh
PYTHONPATH=src python3 -B -m cqa_results.batch --data data/shared/DEV_synthetic_60.json \
  --run-dir outputs/submission/gate-v6 --provider openai --model "$CQA_MODEL" --env-file .env \
  --checklist src/cqa/checklists/official-v6.json --prompt-version atomic-v5 --allow-external-synthetic \
  --only p1-ru-001 p1-kz-013 p1-en-013 --live-call-limit 3
ls outputs/submission/gate-v6     # *.result.json = accepted, *.rejected.json = validation failure
```
Use v6 if at least 2 of 3 are structurally accepted and none shows a new systematic failure; otherwise use v5.
Record the choice and run directory in `STATUS.md`.

**Gate executed 2026-11-07 (owner-authorized, 3 calls, ~USD 0.06, run dir `outputs/submission/gate-v6`):**
2/3 accepted (RU 100.00; KZ 92.31, critical = yes for an off-company paid offer, C07 = no); EN rejected
(02 quote from an ineligible role, 03 missing full-dialogue coverage, 04 unresolved fact). Decision: **v6 +
atomic-v5**. Caveat: on p1-ru-001 the model still answers 07.q2 = yes for a farewell, so the C07 bias is not
fixed by wording. The EN failure type is what the bounded repair targets; using `--repair-authorization` in the
DEV/PROD batches is recommended but has not yet been exercised live.

**DEV batch executed 2026-11-07 (owner-authorized, 60 synthetic chats; `outputs/submission/dev-run1`):**
25/60 accepted, 34 rejected after one repair attempt each (1 rescued), 1 provider HTTP 500, 5 real calls
refused locally (no export grant). ~USD 1.2. Main rejection causes per conversation: quote-role policy
(16, mostly C06 = 10 backed only by scope), unused events/categories on criteria that never use them (12),
quotes not found in the source (7), unresolved facts (5). Accepted results are skewed toward clean
conversations. Expect a similar error share on PROD unless the evaluator policy changes.

**Opt-in evidence gate experiment (offline re-validation of the same 59 stored genuine replies, no calls):**

| Gate | Scored | Rejected |
| --- | --- | --- |
| `strict` (default) | 25 / 59 | 34 |
| `--evidence-gate review` | 42 / 59 | 17 (29%) |

`review` turns ONLY four allow-listed issues into recorded `needs_review` exceptions (operator-role quote
missing for a positive fact/score; events or violation categories on criteria that never use them). Every
cited quote must still exist; unknown facts, coverage proofs, contradictions, model review requests and
scoring stay blocking. Exceptions are stored in `evidence_policy_exceptions` and re-checked by the exporter.
Recovered 17 = 8 quote-role, 8 unused-annotation, 1 both. They include negatives (C08 yes ×2, C04 0 and 15,
C05 no ×2, C06 0); all 42 totals match an independent Decimal recomputation. 12 recovered rely on an excepted
criterion without any operator quote (mostly C06 = 10 backed by full-dialogue scope). Still rejected: quotes
not in source (8), model review requests/other rules (7), unknown facts (5) — overlapping.

**Systematic semantic error found (both gates):** C01 = no in 20 scored results, but in ~17 the first operator
reply plainly greets and introduces themself in the client's language ("Hi, I'm Noah…", "Сәлеметсіз бе, мен Әсел…").
The model misreads "in the client language". No gate can catch this; it needs a C01 wording fix plus a live check.

**Go / no-go (2026-11-07):** strict gate = NO-GO for maximizing agreement (58% errors, survivors all near-perfect).
Review gate = GO only as an explicit owner decision (flag, not default). Direct-rubric fallback = NO-GO now:
3/3 earlier genuine replies rejected, it passes through the same evidence validators, and it is unmeasured at
scale. Before final DEV and PROD: fix C01 wording, verify with a small paid check, then run with
`--evidence-gate review --repair-authorization ...`.

**C01 v7 candidate (experimental, not default; v6 byte-pinned):** official text «Да — оператор поздоровался
на языке клиента и представился в первом ответе» — language matching IS official. v7 changes only the C01
instructions and 01.q1/01.q2 wording: any ordinary greeting counts even if the reply continues with the answer;
client language = the language the client writes in; introduction = says who they are; bot greetings never
count. Offline baseline on the 59 saved v6 replies (`tools/c01_compare.py`, audit heuristic, not labels):
42 agree, 17 model false "no" (all 01.q1; EN 11, KZ 5, RU 1), 0 false "yes". Paired live check, pre-registered
criteria and fixed conversation selection: `tools/c01_live_comparison.sh` (≤34 calls, ~USD 0.7; refuses without
`CQA_C01_PAID_OK=yes`). Do not re-run DEV-60 until that check meets its criteria.

**C01 paired live check executed 2026-11-07 (owner-approved; 34 calls, ~USD 0.53; `outputs/c01-compare/20261107-223917`):**

| Pre-registered criterion | v7 result |
| --- | --- |
| 1. Invented cases ≥ 7/8 correct and no false Yes | 7/8 correct, but 1 false Yes (Russian greeting to a Kazakh-writing client) — **FAIL** (v6: 6/8, 2 false Yes) |
| 2. DEV genuine No kept No (3) | 3/3 — pass |
| 3. DEV previously-wrong Yes fixed (≥ 2/3) | 3/3 — pass (v6 itself got 2 of them right this time: v6 is erratic) |
| 4. DEV previously-right Yes, no regression | 3/3 — pass |
| 5. Structural acceptance not lower by > 2 | 9/17 vs v6 9/17 — pass |

Paired flips: v7 fixed 2 (operator credited with the bot's greeting; English greeting judged "not the client
language"), regressed 0; 1 shared residual error. Root cause seen in rationales: the model tends to assume the
client's language is Russian. Per the pre-registered rule v7 is NOT adopted automatically; it is never worse than
v6 on this sample (n = 17, directional only). Owner decision. Never change the pair between DEV and PROD runs without
recording why; resume refuses a changed pair. Accepted structure is not semantic accuracy.

Optional `--repair-authorization '<owner reference>'` adds at most ONE bounded criterion-repair call per
rejected conversation (atomic only; original reply preserved; repaired results are `needs_review` but
exported as ok). It roughly doubles worst-case calls; `--live-call-limit` counts conversations.

## 4. Early DEV submission (do now, not in the final hour)

1. Load and check the authorized local DEV-65 (LOCAL ONLY file; never commit it):
   ```sh
   PYTHONPATH=src python3 -B -c "from cqa_results.validate import load_dataset_index as l; i,_=l('data/raw/DEV_conversations.json'); print(len(i), 'records')"
   ```
   Must print `65 records`.
2. Optional, only if the owner confirms the 5 calls may go to OpenAI:
   ```sh
   PYTHONPATH=src python3 -B -m cqa_results.grants --data data/raw/DEV_conversations.json \
     --data-class organizer_dev --reference '<owner decision reference>' --external openai \
     --expires 2026-11-09T00:00:00Z --output restricted/dev-approvals.json
   ```
3. Evaluate (60 reviewed chats via the existing synthetic gate; calls only with step 2):
   ```sh
   PYTHONPATH=src python3 -B -m cqa_results.batch --data data/raw/DEV_conversations.json \
     --run-dir outputs/submission/dev-run1 --provider openai --model "$CQA_MODEL" --env-file .env \
     --checklist src/cqa/checklists/official-v6.json --prompt-version atomic-v5 \
     --allow-external-synthetic --expect-count 65 --workers 3 --live-call-limit 80
   #   add: --authorization-manifest restricted/dev-approvals.json --allow-external-authorized
   ```
   Re-attempt only failures once, same command plus `--resume`. Never edit outcome files.
4. Export, validate and review:
   ```sh
   PYTHONPATH=src python3 -B -m cqa_results.export --set dev --data data/raw/DEV_conversations.json \
     --run-dir outputs/submission/dev-run1 --team-name "$TEAM_NAME" --output results/dev/results.json
   PYTHONPATH=src python3 -B -m cqa_results.validate results/dev/results.json --set dev \
     --dataset data/raw/DEV_conversations.json --team-name "$TEAM_NAME" --submission
   ```
   Read every validator warning. Rationales of the 5 real calls are model text about real
   people; a human must skim them for names, phone/account numbers or quotes before a
   PUBLIC push (validator flags long digit runs and e-mails). Fix by re-evaluating, never
   by hand-editing scores or values.
5. Commit and push only that file (step 7), then verify the public URL (step 8).
   Re-export later with `--overwrite` if a better run exists; push again before code stop.

## 5. Final hour: PROD controls

1. **Fetch** with the organizer-provided method only. Save the exact response bytes to
   `data/raw/PROD_control.json` (ignored). Keep tokens/signed URLs out of tracked files,
   commit messages and logs. Never commit the control transcripts. If it is a plain HTTPS GET:
   ```sh
   read -rs CONTROL_URL && export CONTROL_URL          # paste the URL; not echoed, not in history
   PYTHONPATH=src python3 -B -m cqa_results.envelope fetch --url-env CONTROL_URL --out data/raw/PROD_control.json
   #   add --header-env CONTROL_AUTH (export CONTROL_AUTH='Authorization: Bearer ...') only if instructed
   ```
2. **Check the envelope** (prints structure, never text):
   ```sh
   PYTHONPATH=src python3 -B -m cqa_results.envelope check data/raw/PROD_control.json --expect-count 10
   #   if only the OUTER wrapper differs (bare list, {records:[...]}, {data:[...]}):
   PYTHONPATH=src python3 -B -m cqa_results.envelope wrap data/raw/PROD_control.json \
     --out data/raw/PROD_control_envelope.json --group-id PROD_CONTROL
   # equivalent manual inspection:
   PYTHONPATH=src python3 -B -c "
   import json,collections; v=json.load(open('data/raw/PROD_control.json')); d=v.get('data',{}); r=d.get('records',[])
   print(sorted(v), sorted(d), d.get('total_records'), len(r))
   print(collections.Counter(x.get('channel') for x in r), collections.Counter(k for x in r for k in x))
   print(collections.Counter(t.get('speaker') for x in r for t in x.get('transcript',[])), collections.Counter(k for x in r for t in x.get('transcript',[]) for k in t))"
   PYTHONPATH=src python3 -B -c "from cqa.loader import read_dataset; d,h=read_dataset('data/raw/PROD_control.json'); print(len(d['records']), h)"
   ```
   Expected: same envelope as DEV (`isSuccess`, `error`, `data.dataset_group_id`,
   `data.total_records`, `data.records`), 10 records, speakers within
   `client/operator/bot/system`, turn keys within `timestamp/speaker/text/message_id`.
   If the shape differs: STOP, write an explicit, reviewed conversion into that envelope
   that preserves every ID, record order and the full turn array order (no dropping or
   merging turns, otherwise evidence indexes break), save it as `data/raw/PROD_control_envelope.json`,
   and use that path below. Never invent missing fields.
3. **Authorize** (only if organizer rules permit external processing of controls):
   ```sh
   PYTHONPATH=src python3 -B -m cqa_results.grants --data data/raw/PROD_control.json \
     --data-class organizer_control --reference '<organizer rule reference>' --external openai \
     --expires 2026-11-09T00:00:00Z --output restricted/prod-approvals.json
   ```
4. **Evaluate all 10:**
   ```sh
   PYTHONPATH=src python3 -B -m cqa_results.batch --data data/raw/PROD_control.json \
     --run-dir outputs/submission/prod-run1 --provider openai --model "$CQA_MODEL" --env-file .env \
     --checklist src/cqa/checklists/official-v6.json --prompt-version atomic-v5 \
     --authorization-manifest restricted/prod-approvals.json --allow-external-authorized \
     --expect-count 10 --workers 5 --live-call-limit 25
   ```
   One retry of failures: same command plus `--resume`.
5. **Export and validate:**
   ```sh
   PYTHONPATH=src python3 -B -m cqa_results.export --set prod --data data/raw/PROD_control.json \
     --run-dir outputs/submission/prod-run1 --team-name "$TEAM_NAME" --output results/prod/results.json
   PYTHONPATH=src python3 -B -m cqa_results.validate results/prod/results.json --set prod \
     --dataset data/raw/PROD_control.json --team-name "$TEAM_NAME" --submission
   ```
   Out of time with conversations never attempted: re-run the export with
   `--unattempted-reason 'Not evaluated before code stop: <actual cause>'` (they become
   honest error records; still exactly 10).
6. Human skim of `results/prod/results.json` (rationales only; no transcripts are in it).

## 6/7. Commit and push (one designated person, submission branch only)

```sh
git status --short
git add -- results/dev/results.json results/prod/results.json   # only these paths
git diff --cached --name-only                                    # must list only results/*/results.json
git commit -m "Submit CQA results (DEV and PROD)"
git push origin "HEAD:$SUBMIT_REF"
```
If the push is rejected, do not force-push: `git fetch origin`, inspect, rebase or merge only
the results commit, push again. Never stage `data/`, `outputs/`, `restricted/` or `.env`.

## 8. Verify the public URL (anonymous read)

```sh
PYTHONPATH=src python3 -B -m cqa_results.verify_remote --repo "$SUBMIT_REPO" --ref "$SUBMIT_REF" \
  --set dev --dataset data/raw/DEV_conversations.json
PYTHONPATH=src python3 -B -m cqa_results.verify_remote --repo "$SUBMIT_REPO" --ref "$SUBMIT_REF" \
  --set prod --dataset data/raw/PROD_control.json
```
Both must print `"ok": true` (anonymous fetch succeeded, SHA-256 equal to the local file,
remote bytes pass `--submission` validation). Also open
`https://github.com/$SUBMIT_REPO/blob/$SUBMIT_REF/results/prod/results.json` in a private window.

## Final-hour time budget (T = controls released, code stop = T+60)

| By | Action | Done when |
| --- | --- | --- |
| T-60 | Section 3 complete; variables set; dry run green; DEV already pushed and verified | `verify_remote --set dev` ok |
| T+5 | Controls saved to `data/raw/PROD_control.json`; envelope check prints 10 | `read_dataset` prints 10 |
| T+10 | Grants written (if permitted); 1-conversation smoke: batch with `--only <first id>` in a scratch run dir | one `result` file |
| T+30 | Full batch finished; one `--resume` retry if any error | all 10 have an outcome |
| T+35 | Export + `--submission` validation pass | exit 0 |
| T+40 | Human skim; commit; push | push accepted |
| T+45 | `verify_remote --set prod` and `--set dev` ok | both `"ok": true` |
| T+50 | HARD STOP for evaluation. If anything is missing, export with `--unattempted-reason`, validate, push, verify | pushed exactly 10 |
| T+55 | No further changes except fixing a failed push | - |

## Limitations

* Validated offline only: synthetic/invented dry runs, the engine mock fixture on the real
  DEV-65 file (wiring check, not an evaluation) and an offline OpenAI transport double. No
  paid call was made for this exporter, so genuine-model rejection rates and run time are
  unmeasured. Time a 1-conversation smoke run before the final hour.
* Unknown: control API, payload shape, whether control data may be sent to OpenAI, team
  name, submitted repo URL/branch.
* Scope locators expand to full turn ranges; that is faithful to the engine evidence but long.
