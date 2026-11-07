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

1. `atomic-v3` schema compiler (`src/cqa/atomic_prompt.py`): per-criterion branches
   over controlling answers mirror existing validator rules: exact full-dialogue
   scope for full-scope answers; judgment null under N/A, required when applicable;
   need=no -> verified=not_applicable; conditional trigger -> obligation; critical
   facts yes/no/unknown; consistency-rule response ranges for C04/C06/C07; minimum
   item counts. Three documented narrowings (`NARROWINGS`) only remove outputs the
   validator could never accept. Opt-in; v2 default byte-identical.
2. `src/cqa/strict_schema.py`: offline strict-subset/limit guard (limits verified
   against OpenAI docs 2026-11-07) and a small conformance checker.
3. `src/cqa/repair.py` + engine/provider hooks: disabled-by-default bounded repair
   (one call, pinned answers, separate audit/usage, `needs_review`).
4. `tools/reliability_measure.py`: reproducible offline comparison (outputs ignored).

## Offline before/after (reproduce with tools/reliability_measure.py)

| Measure | Baseline 6481390 | Candidate |
| --- | --- | --- |
| Genuine saved replies accepted (unchanged validators) | 0/4 | 0/4 (by design; generation-side change) |
| Genuine 5d256ac criteria representable under the schema it would be sent with | 8/8 (v2) | 5/8 under v3 — exactly 03/05/07, the validator's rejections |
| Enumerated fixtures with a structural failure class still representable | 967/1048 (v2) | **0/1048** (+1 documented verified=no residual) |
| Validator-accepted enumerated fixtures representable | 691/691 | 691/691 (asserted in tests) |
| Controlled fixture: genuine facts + hand-written repair | n/a | accepted, 8/8, one repair call |
| Schema size p1-ru-001 | 8.7 KB, 8 branches | 108 KB, 43 branches; 975 properties, 412 enum values, 12.8k chars (limits 5000/1000/120k) |

Enumeration = 6,672 per-criterion fixtures (all answer combinations × 3 evidence
modes × judgment options) on p1-ru-001. Fixtures are not model behaviour.

Remaining v3-representable rejections (validator/repair-owned, semantic locators):
eligible speaker role for a positive fact (65), first operator reply (6),
identification events missing (12), verified=no scope (1). Event chronology,
exact quotes and question duplicates are not schema-encodable here.

## Tests

`CQA_TEST_FULL_DEV=<local full DEV> PYTHONPATH=src python3 -B -m unittest discover -t . -s tests`:
146 run, 145 pass, 1 expected skip (loader full-DEV path absent in worktree);
original 127 unchanged. Independent QA (`feature/cqa-independent-qa` 3ff9c76,
unchanged) against candidate: 81/81. QA scenario harness: 27 cases, 0 engine
errors, 31 not_assessed (correct for mock). Both Node suites pass. Shared dataset
hash unchanged. No holdout command was run.

New regression module `tests/test_schema_reliability.py` (19 tests): v2 byte
identity; genuine reply representability; strict limits over all 60 chats, a
400-turn dialogue and an added criterion; exhaustive soundness/completeness;
C03 chronology stays validator-owned; provider prompt binding; repair disabled
by default, pinning, flip rejection, retreat-to-unknown, single call, gates and
separate usage; C04 incorrect vs incomplete; C05 politeness vs empathy truth
table; C07 missing/partial/interrupted closing; C08 hidden violation among 40
irrelevant turns and truncated scopes; RU/KZ/EN and inserted-turn invariance.

## Not established

No semantic accuracy: a model can still miss a hidden C08 violation with a valid
full scope, misjudge C04 correctness or misclassify complaints. Grammar compile
latency for a 108 KB per-conversation schema is unmeasured (OpenAI documents extra
latency on a schema's first request; the v3 schema changes with dialogue length).
Live acceptance of v3 is unverified until one authorized call. Repair cost estimate:
~12 KB input (~3–4k tokens) plus output, roughly USD 0.005–0.01 at gpt-5.4-mini
published rates — an estimate, not a measurement.
