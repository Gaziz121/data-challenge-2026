# Independent QA and adversarial review of the CQA engine

Date: 2026-11-07. Reviewed code: commit `ebcab33` (`src/cqa`, unchanged on
`codex/cqa-evaluation-engine` and `codex/local-mvp-integration` at review time).
Reviewer: Claude (independent QA). No production code was changed. No LLM or
external API was called. Nothing here measures semantic scoring accuracy.

## How to run

```sh
PYTHONPATH=src python3 -m unittest discover -t . -s tests   # engine owner's suite
PYTHONPATH=src python3 -m unittest discover -t . -s qa -v   # this QA suite
PYTHONPATH=src python3 -m qa.harness                        # scenario harness, mock only
```

## Results actually executed (Python 3.9.6, pydantic 2.13.5)

| Suite | Ran | Passed | Failed | Skipped |
| --- | --- | --- | --- | --- |
| Existing `tests/` | 53 | 52 | 0 | 1 (full DEV is local-only, absent in this worktree) |
| `qa/` | 41 | 29 | 12 | 0 |

The 12 failures are the `DefectTests` below. Each asserts behavior required by
the checklist; each fails on `ebcab33`. They are evidence, not flaky tests.
The harness mock run produced 27 cases, 31 locked rows, all `not_assessed`,
0 passes, and 0 engine errors. That is the correct result: a mock cannot pass a semantic test.
The shared DEV file hash was unchanged after all runs (`836b1cd8...c17`).

## Defects found (deterministic, reproducible)

| ID | Failure mode | Minimal reproduction | Expected (source) | Actual | Proposed fix |
| --- | --- | --- | --- | --- | --- |
| QA-D01 | Greeting credit from a non-first operator turn | `LATE_INTRO_EN`: first reply "Please open Settings first."; 01=yes cites the later "Hello, I'm Sam" | Reject: C1 01 places greeting+introduction in the FIRST reply | Accepted: the gate only needs *some* agent quote | Configurable evidence locator per criterion (e.g. `positive_evidence: first_agent_message`); validator requires a quote from `facts.first_agent_message_id` |
| QA-D02a-g | Atomic answers and the official response can contradict each other for 02-07 | e.g. 03.q1=yes, 03.q2=no, response yes; 07.q3=no (no farewell), response yes; 04.q2=no, response 20 | Reject (C1/C3 explicit No rules; C2 anchors) | All 7 accepted; consistency rules exist only for 01 and 08 | **Config-only.** Add the rules in `qa/test_proposed_config_fix.py::PROPOSED_RULES` to a new checklist version. Verified in memory: rejects all 7, still accepts correct downgrades and every N/A path, and the mock runs on all 60 chats |
| QA-D03 | Valid identification evidence rejected | 03=yes citing only the system event "Customer identity verified." | Accept: G2/C3 allow citing a system message. In DEV, verification appears as a system event in 4 chats | `ValueError: Positive operator performance needs quoted agent evidence`, and the **whole evaluation fails** | Per-criterion allowed evidence roles (e.g. 03: `agent` or `system`) |
| QA-D04a | Critical flag with no supporting atomic answer | 08=yes, category insult, all of 08.q1-q3 = no | Reject | Accepted (rules only fire on yes) | Validator: 08=yes requires at least one yes category question |
| QA-D04b | Critical category does not match the atomic answer | 08.q1 (insult)=yes, category listed = confidential_disclosure | Reject | Accepted | Map each 08 question to its category in config; require `set(categories) == {category of each question answered yes}` |
| QA-D05 | Meaningless citation accepted | 05=yes evidence quote `"!"` (a substring of "Goodbye!") | Reject: not a supporting fragment | Accepted | Require at least one letter or digit in a quote. A minimum length is an owner decision |

## Risks pinned by characterization tests (pass today, need a decision)

| ID | Behavior | Why it matters |
| --- | --- | --- |
| QA-C01 | Quote check is exact: `"Standard"` fails against source `«Standard»` | 42 of 882 shared messages use «» or “”. Models often normalize quote marks and whitespace, so valid outputs get rejected |
| QA-C02 | One bad citation anywhere raises, giving no result and no score | Combined with C01/D03, one cosmetic quote mismatch loses a control conversation |
| QA-C03 | An empty turn makes the conversation unloadable | Possible in API or voice exports; the whole conversation fails |
| QA-C04 | Speaker labels other than client/operator/bot/system fail closed | Correct not to guess, but the control API labels are unconfirmed |
| QA-C05 | Language code not validated (`kz`, `Kazakh` accepted) | 01 depends on the client's language; inconsistent codes are not caught |
| QA-C06 | Discrete scales must start at 0 (a 1-5 scale is rejected) | R05 requires configurable scales; also needs a formula decision |
| QA-C07 | New critical criteria are limited to the 3 official categories | A replacement critical criterion cannot be expressed without a contract change |
| QA-C08 | External gate rejects every team-authored fixture | The semantic scenarios below cannot run on the OpenAI adapter as written; needs a reviewed export policy for synthetic QA data |
| QA-C09 | 08=yes from a non-mock provider leaves status `structurally_valid` | No risk-based escalation of critical violations to review |

## Existing coverage (not duplicated)

Exhaustive scoring with N/A redistribution (2,592 combinations), invalid
values, missing/duplicate/extra criteria, fabricated quote text, unknown IDs,
bot-only positive evidence, applicability contradictions, 01/08 consistency
rules, critical full-scope rule, a new organizer criterion, CLI, provider
transport failures, and the 60-chat mock run. QA only adds what these miss:
wrong-message attribution, RU/KZ end-to-end gates, a one-letter Kazakh change,
decision-order invariance, and an independent hand-computed N/A total (94.71).

## Semantic tests that remain unverified (need a real model and human review)

`qa/scenarios/semantic_v1.json` has 19 hand-written scenarios (RU 7, KZ 5,
EN 7) and 4 counterfactual edit pairs of reviewed synthetic DEV chats
(p1-en-009, p1-ru-006), built in memory only. Labels are
`team_qa_synthetic / proposed_unreviewed`. They are not official Ground Truth
and not `team_human` until reviewed. They cover:
bot greeting credit, greeting without name, late introduction, a system message
that names the operator, verification requested but not confirmed, disclosure
before verification, system verification before disclosure, a general tariff
question (03 N/A), closure without farewell (07 No), abrupt disconnect (07 N/A),
ending before a request (04 N/A), partial and complete consultation, insult, a
private paid offer, a legitimate phone request (08 No), prompt injection, and
a greeting in the wrong language. **None has been tested on a model.**

## Five most important accuracy risks

1. **The atomic questions don't constrain the score (D02).** The model can answer the
   atomic checks correctly and still choose a contradictory official response.
2. **Exact-quote matching combined with all-or-nothing validation (C01, C02, D03).** Plausible
   valid outputs fail completely, so a control conversation may get no score.
3. **Operator attribution in criterion 01 (D01).** All 60 shared chats show a bot
   turn before the operator, so crediting the wrong turn is the most likely error.
4. **Order of verification and disclosure in 03.** Nothing deterministic checks the order; it rests
   entirely on model judgment, and D03 blocks the best evidence.
5. **No semantic accuracy measured.** The only provider ever run is the mock;
   the external gate blocks the QA scenarios (C08).

## Fixes ranked by likely impact

1. Adopt the D02 consistency rules as a new checklist version (configuration only, verified).
2. Make the quote check tolerant to formatting (NFC, collapse whitespace, fold quote marks)
   while storing the exact source span, and turn a single-decision evidence failure
   into `needs_review` for that decision instead of discarding the run (C01, C02).
3. Allow system-event evidence for 03 (D03) and enforce the first-reply locator for 01 (D01).
4. Enforce the link between 08 categories and the atomic answers (D04a/b), and send 08=yes to review (C09).
5. Approve an export policy for team-synthetic QA fixtures, then run the harness on
   one real model after human review of the scenario labels.

## Update: RCA of genuine evaluation a94e48f7 (engine `f84d364`)

The integrated engine fixes D01-D05: the original 41 QA tests pass 41/41 against
`codex/local-mvp-integration@f84d364` (re-run independently). One genuine
`gpt-5.4-mini-2026-03-17` response on synthetic `p1-ru-001` was rejected for
criteria 02, 04 and 07. It is the only real sample (n=1); `3ea9543c` is the same output.

| Criterion | Model output | Verdict |
| --- | --- | --- |
| 02 | `response=yes`, but `02.q1=yes` (enough info); `na_reason` = N/A condition | Correct rejection. The reported na_reason error masked the real applicability contradiction. N/A is the checklist answer |
| 04 | `response=15`, `04.q1=yes`; `na_reason` = negated condition text | Rejected only for format; the decision is otherwise valid |
| 07 | `response=N/A`, but `07.q1=no`, q2=yes, q3=yes; `na_reason` contradicts N/A | Correct rejection |

Causes: (1) the `Decision` schema puts `response` before `atomic_checks`, and
OpenAI Structured Outputs produce keys in schema order (verified in the current
guide, "Key ordering"), so the model commits to an answer before reasoning;
(2) strict mode requires `na_reason` on every decision and it has no description.
The model filled it for all four N/A-capable criteria and none of the others;
(3) `engine.diagnose_output` stops at the first schema error, hiding the
contextual issue.

Fixes, smallest first: reorder `atomic_checks` before `response`; describe
`na_reason` ("null unless response is N/A") in schema and prompt; report all
issues in diagnostics; then adopt deterministic decision rules
(`qa/decision_rules.py` is a reference checker) that flag model/rule
disagreement for review and never override silently. Not weakened: an
applicable decision with N/A text stays invalid (R2).

Open human-review questions: 07.q2=yes for "Пожалуйста. Хорошего вечера!" (no
summary or further-help offer; strict reading gives 07=no) and 04=15 vs 20.

Regression suite `qa/test_rca_a94e48f7.py` (15 tests) replays the saved output
(`qa/replays/a94e48f7.json`, verbatim model output only, with no run IDs or usage)
through a test double. Against `f84d364`: 12 pass, 3 fail, namely R1 masked
diagnostic, R3 schema order and R4 na_reason description. Full QA suite against
`f84d364`: 56 run, 53 pass, 3 fail. On the `ebcab33` baseline the replay
classes skip. Run:

```sh
PYTHONPATH=../data-challenge-2026-integration/src python3 -m unittest discover -t . -s qa -v
```

## Files and Git state

Changed files (all new, all under `qa/`): `__init__.py`, `fixtures.py`,
`test_adversarial_gates.py`, `test_proposed_config_fix.py`, `harness.py`,
`test_harness.py`, `scenarios/semantic_v1.json`, `REPORT.md`.
Worktree `../data-challenge-2026-independent-qa`, branch
`feature/cqa-independent-qa` from `ebcab33`. Not pushed, not merged. The primary
checkout and GPT Work's files were not modified. `PROJECT_FILE_MAP.md` and local
`STATUS.md` were not edited, to avoid conflicting with GPT Work's uncommitted edits.
The integration owner should add one map line: `qa/` = independent QA
tests and unreviewed synthetic scenarios, GIT TRACKED.
