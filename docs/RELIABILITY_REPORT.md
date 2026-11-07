# Atomic-path reliability: diagnosis, changes and offline measurement

Branch `feature/cqa-atomic-reliability` (worktree `../data-challenge-2026-reliability`),
based on verified integration commit `6481390` (engine 0.6.1, atomic-v2, rubric v4,
wire 1.2). Engine 0.7.0. No paid call, no frontend change, no validator or scoring
change, no checklist change. Main and the documentation worktree are untouched.

## Root cause (from the four saved genuine replies, all synthetic p1-ru-001)

| Run | Path | Rejected criteria | Class |
| --- | --- | --- | --- |
| a94e48f7 | legacy v2 | 02, 04, 07 | model-owned N/A / na_reason contradictions |
| c379231 | legacy v2 | 05, 08 | final answer vs atomic rule; **C08 missing full scope** |
| f4599f0 | legacy v3 | 03 | final answer vs N/A; evidence role |
| 5d256ac | atomic-v1 | 03, 05, 07 | **missing full scope ×2; missing applicable judgment** |

The atomic design already removes the legacy final-answer classes. The remaining
observed classes are model compliance failures that the decoding schema permitted:
the genuine 5d256ac reply is **fully valid under the atomic-v2 strict schema** (0
JSON Schema errors). Scope and judgment obligations lived only in prose and in the
post-hoc validator. The validators were correct here: the model's facts (general
tariff question, no complaint, polite closing) were plausible, but the required
locator/judgment was absent, and no rule was over-restrictive in a way that
changed a semantic outcome. The full-scope requirement proves locator coverage,
not attention; it is kept because it is cheap once enforced in the grammar.

## Changes

1. Schema compiler (`src/cqa/atomic_prompt.py`). **`atomic-v4` is the recommended
   opt-in**: same instructions/payload as v2; per-criterion branches over
   controlling answers mirror existing validator rules: exact full-dialogue scope
   for full-scope answers; judgment null under N/A, required when applicable;
   need=no -> verified=not_applicable; conditional trigger -> obligation; critical
   facts yes/no/unknown; applicable all_of facts not not_applicable; minimum item
   counts. Three documented narrowings (`NARROWINGS`) only remove outputs the
   validator could never accept. v2 stays the byte-identical default.
   `atomic-v3` additionally restricted discretionary scores by consistency rules;
   it is retained only to reproduce its recorded live request (see below).
2. `src/cqa/strict_schema.py`: offline strict-subset/limit guard (limits verified
   against OpenAI docs 2026-11-07) and a small conformance checker.
3. `src/cqa/repair.py` + engine/provider hooks: disabled-by-default bounded repair
   (one call, pinned answers, separate audit/usage, `needs_review`). Repair schemas
   never restrict scores by consistency rules.
4. `tools/reliability_measure.py`: reproducible offline comparison (outputs ignored).

## The one authorized live call (atomic-v3, commit a958142)

Synthetic p1-ru-001, gpt-5.4-mini-2026-03-17, repair disabled, one transport.
**Structurally accepted** (first accepted genuine total): 8/8 criteria valid,
C03/C05 absence facts cited the exact full scope, C07 judgment present. Total
76.92. Provider latency 16.6 s (5d256ac: 9.5 s); input 24,105 / output 2,500
tokens (5d256ac: 5,980 / 2,668): the large schema counts as input. Approx.
USD 0.0293 at published rates.

**The total is not trustworthy.** The model answered 06.q3 "no" meaning "no
explicit waiting", then wrote a C06 rationale of "clear and coherent ... no
meaningful lapse" yet emitted **0**. v3's grammar, applying the configured rule
06.q3=no -> {0,4,7}, made 10 unrepresentable. Under v2 the same contradiction is
rejected (no total); v3 converted a safe rejection into a wrong score that no
validator can detect. Constraining a *score* from an ambiguous atomic answer is a
regression; constraining locators/presence/derived couplings is not. Hence
atomic-v4 drops score ranges. Regression fixture: `tests/fixtures/live_atomic_v3_a958142.json`.
Under v4 the rationale-consistent 06=10 is representable and the validator rejects
it (no total) — a correct, visible failure. The underlying defect is the
ambiguous checklist question 06.q3 ("If there was explicit waiting, did the
operator warn?"), which conflates "no waiting" with "no warning"; changing it is a
checklist-version decision for the team, not made here.

## Offline before/after (reproduce with tools/reliability_measure.py)

| Measure | Baseline v2 (6481390) | v3 | **v4** |
| --- | --- | --- | --- |
| Genuine saved replies accepted, unchanged validators | 0/4 | 0/4 + 1 live accept (C06 forced) | not live-tested |
| Genuine 5d256ac criteria representable | 8/8 | 5/8 (03/05/07) | 5/8 (03/05/07) |
| Structural-failure fixtures representable | 724/805 | 0/805 | **0/805** (+1 verified=no residual) |
| Score/answer contradictions | representable, rejected | unrepresentable, **forced** | representable, rejected |
| Validator-accepted fixtures representable | 691/691 | 691/691 | 691/691 |
| Schema p1-ru-001 | 8.7 KB / 8 branches | 108 KB / 43 | 40 KB / 18 |

Enumeration = 6,672 per-criterion fixtures (all answer combinations x 3 evidence
modes x judgment options) on p1-ru-001. Fixtures are not model behaviour.
Controlled fixture (genuine 5d256ac facts + hand-written repair) is accepted
8/8 with one repair call; not model output.

Remaining v4-representable rejections, validator/repair-owned: consistency-rule
contradictions (288), eligible speaker role for a positive fact (65), first
operator reply (6), identification events (12), verified=no scope (1). Event
chronology, exact quotes and question duplicates are not schema-encodable.

## Tests

`CQA_TEST_FULL_DEV=<local full DEV> PYTHONPATH=src python3 -B -m unittest discover -t . -s tests`:
148 run, 147 pass, 1 expected skip (loader full-DEV path absent in worktree);
original 127 unchanged. Independent QA (`feature/cqa-independent-qa` 3ff9c76,
unchanged) against candidate: 81/81. QA scenario harness: 27 cases, 0 engine
errors, 31 not_assessed (correct for mock). Both Node suites pass. Shared dataset
hash unchanged. No holdout command was run.

`tests/test_schema_reliability.py` (21 tests): v2 byte identity; genuine reply
representability; strict limits over all 60 chats, a 400-turn dialogue and an
added criterion; exhaustive soundness/completeness; C03 chronology stays
validator-owned; provider prompt binding; live v3 reproduction and C06 regression;
repair disabled by default, pinning, flip rejection, retreat-to-unknown, single
call, gates and separate usage; C04 incorrect vs incomplete (rejected, not
forced); C05 politeness vs empathy; C07 missing/partial/interrupted closing; C08
hidden violation among 40 irrelevant turns and truncated scopes; RU/KZ/EN and
inserted-turn invariance.

## Not established

No semantic accuracy (one synthetic conversation; C06 wrong in the only accepted
run). A model can still miss a hidden C08 violation with a valid full scope,
misjudge C04 correctness, misclassify complaints, or answer an ambiguous atomic
question in a way that the validator then rejects. v4 latency/tokens are not
live-measured; by schema size, input is estimated at roughly 11–12k tokens
(v3 live: 24.1k; v2-class: 6.0k), i.e. about USD 0.02 per call — an estimate.
Repair estimate: ~14 KB schema + ~12 KB input, roughly USD 0.01 per repair call.

## Draft checklist 2026-11-07.v5 (C06 waiting fact) — needs team review

Source: official 06 anchor 10 is conditional — «Ответы ясные и связные. Если было
явное ожидание, оператор предупредил.» v4 asked the condition as a yes/no question
(06.q3 "If there was explicit waiting, did the operator warn?") with rule
no -> {0,4,7}, so "no" meant either "no waiting" or "no warning".

`src/cqa/checklists/official-v5.json` is v4 with only C06 changed:
- 06.q3 retired; new 06.q4 "Did the human operator leave the client in an explicit
  wait WITHOUT warning them? Answer no if every explicit wait was warned or there
  was no explicit waiting at all." `no` is an absence claim (full-dialogue scope).
- Consistency rule 06.q4=yes -> {0,4,7} (same cap as before, now unambiguous).
- C06 instructions add the explanation; no time threshold (open A07).
- Weights, levels, anchors, N/A, applicability, output sources and all other
  criteria are identical (asserted in `tests/test_checklist_v5.py`).

Not the default anywhere; the web registry is unchanged (an existing test pins its
four versions). Select by loading the file, or register it at runtime via the
existing `POST /api/checklists`. The live a958142 reply is not migrated to v5.
Hand-authored counterfactual only: with 06.q4=no and C06=10, the p1-ru-001 total
would be 100.00 — that is a fixture, not a measured result. Open: whether
pre-handover queue waiting announced by the bot counts as "explicit waiting" for
the operator — a reviewer calibration question, not encoded.

Tests: 153 run, 152 pass, 1 expected skip; QA 81/81; both Node suites pass.

## Second authorized live call (atomic-v4 + draft checklist v5, commit 2fcd958)

Synthetic p1-ru-001, gpt-5.4-mini-2026-03-17, repair disabled, one transport.
**Rejected, no total.** 7/8 criteria validated, including C06=10 with 06.q4=no and
the exact full scope — the v5 wording removed the forced/ambiguous C06 outcome on
this conversation. C04 failed only because the model emitted 04.q1 twice (same
answer): v4 bounded item counts from below only, so the duplicate was legal output
(same root-cause class: a validator rule absent from the grammar). Provider
14.2 s; input 12,557 / output 2,918 tokens; approx. USD 0.0225 (pre-call estimate
11–12k input tokens was close). Fixture: `tests/fixtures/live_atomic_v4_2fcd958.json`.

Offline follow-up, no further call: **atomic-v5** = v4 + exact item counts
(`maxItems`, documented as supported by OpenAI, verified 2026-11-07; first live use
would be v5). The genuine reply is unrepresentable in v5 only at C04. Repair now
pins agreeing duplicate answers; a hand-authored repair of C04 is accepted with one
repair call (fixture, not a measurement). v5 cannot prevent a duplicate that
replaces a missing question (no uniqueness keyword); the validator still rejects it
and the opt-in repair can fix it. atomic-v3/v4 remain only to reproduce their
recorded requests. Tests: 155 run, 154 pass, 1 expected skip; QA 81/81; Node pass.

Live record so far: 6 genuine replies; 1 structurally accepted (v3, C06 forced —
untrustworthy); 0 trustworthy accepted totals; no semantic accuracy established.
