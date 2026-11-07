# Validation repair and single OpenAI smoke test

Date: 2026-11-07, Asia/Almaty. Working branch: `codex/local-mvp-integration`;
base `76016fb`. No merge to main. Original dirty checkout and independent QA
worktree/commit `cbdec73` were preserved. The final commit is reported in delivery
and the ignored local evidence ledger, avoiding a self-referential commit ID.

## Confirmed defects

| Defect | Repair | Status |
| --- | --- | --- |
| D02a-g | Reviewed Claude's configuration-only implications against the exact anchors. Adopted as default rubric `2026-11-07.v2`, keeping N/A in permitted sets where allowed. | All seven tests pass |
| D01 | Configurable positive-evidence locator; greeting credit requires a quote from the first HUMAN operator reply. | Pass |
| D03 | Configurable positive-evidence roles; identification allows agent or system evidence. Other criteria retain their appropriate operator attribution. | Pass |
| D04a-b | Each critical atomic question maps to a category. The listed categories must equal the yes answers, and the flag must equal whether any category is asserted. | Both pass |
| D05 | Quoted evidence must contain a Unicode letter or digit, preventing punctuation-only citations. | Pass |

No known confirmed D01-D05 defect remains. This does not establish semantic
accuracy or make every possible inconsistency detectable. The engine does not
infer product-policy truth or the meaning of an utterance deterministically.

`official-v1.json` is preserved as historical configuration. `load_checklist()`
now selects `official-v2.json`. Weights, raw levels, anchor wording, N/A conditions,
applicability triggers, gross-violation separation and `scoring.py` are unchanged.
No rule silently changes the model's selected response. Inconsistent output is
rejected. New criterion IDs/questions remain configuration; no validator branch
is keyed to IDs 01/03/08. Question/category mappings and evidence policies are
part of saved checklist versions.

## Quotations and failed evaluations

Strict `validate_evaluation()` remains exact and fails closed. The application
explicitly opts into `quote_policy="normalize_formatting"`. That resolver allows
Unicode combining-mark canonical equivalence, whitespace folding and typographic
quote folding within the specified source message. It allows no case changes,
spelling edits, fuzzy matching, cross-message search or ambiguous span selection.

Successful matches become exact source substrings, with original quote, resolved
quote, message ID, original start/end offsets and formatting-policy version saved
in `evidence_repairs`. The original model evaluation is retained separately from
the validated evidence view. Responses/applicability/scores are never repaired.

A genuine unresolved citation or decision error still prevents an accepted total.
Failed criteria cannot be silently dropped or converted to N/A: that would invent
a new scoring denominator. Instead `EvaluationRejected` retains the original
reply, model/usage/configuration, transcript/checklist, audit and per-criterion
issues/statuses. The backend saves a `rejected-<id>.json` diagnostic, returns an
explicit 422 and provides a restricted named diagnostic route. The browser shows
all retained decisions as **unvalidated**, with no points or total. Other valid
criteria remain inspectable, rather than losing the entire provider response.

This resolves the data-loss aspect of all-or-nothing rejection while preserving
strict official-score acceptance. Independent characterization tests C01/C02
still pass: direct exact validation rejects formatting changes and invalid runs
still raise instead of fabricating a partial total. Separate new tests exercise
explicit formatting recovery and diagnostic preservation.

## Executed tests

```sh
# From the integration worktree:
PYTHONPATH=src python3 -B -m unittest discover -s tests -q
node tests/test_dev_review.cjs
node tests/test_web_ui.cjs

# From Claude's untouched QA worktree, testing this corrected engine:
PYTHONPATH=/Users/User/data-challenge-2026-integration/src python3 -B -m unittest discover -t . -s qa -q
```

- App/original tests: 75 run, 74 passed, zero failures, one expected skip because
  the separate worktree has no local-only full DEV voice dataset. This includes
  the existing 2,592-combination independent scoring check and all prior engine,
  export, multilingual, pipeline, dynamic-criterion and HTTP tests.
- Independent QA: 41 run, 41 passed, zero failures/errors/skips. Previously all
  12 confirmed defect tests failed. Claude's tests/report/scenarios were not edited.
- Both Node suites passed: manual JSON/CSV/resume, rendering, N/A, exact backend
  totals, repaired evidence display and genuine-rejected-result presentation.
- Existing test fixtures were made internally coherent: a “fully compliant”
  fixture now answers no to “did wording force the client to ask again?”; critical
  flag tests now assert the matching atomic category. No independent assertion
  was weakened. Failure-persistence tests now require saved diagnostics/no score.
- Initial development runs caught those stale fixtures; the final results above
  include the corrected fixtures and new repair/diagnostic/one-attempt-cap tests.

## Exactly one genuine provider request

The owner explicitly authorized reuse of the existing key in the original
checkout's `.env`. It was loaded in memory, never printed, copied or written.
The file remains ignored with mode 0600. No paid resource/key/service was created.

A free model-metadata authentication request returned HTTP 200. Then exactly one
paid `POST /v1/responses` evaluated the approved synthetic DEV conversation
`p1-ru-001` through the browser/backend and existing provider. The exact approved
subset/hash gate remained active; no real-call records or audio links were sent.

| Observed field | Value |
| --- | --- |
| Provider | OpenAI Responses API |
| Requested model | `gpt-5.4-mini` |
| Returned model | `gpt-5.4-mini-2026-03-17` |
| Provider latency | 10,132 ms |
| End-to-end engine latency | 10,139 ms |
| Input / output / total tokens | 4,348 / 3,165 / 7,513 |
| Cached input / reasoning tokens | 0 / 0 |
| Rubric / prompt | `2026-11-07.v2` / `baseline-v2` |
| Transport / structured JSON | Completed, with all eight criterion decisions |
| Accepted quality evaluation | **Failed validation; no total** |

Estimated cost is **USD 0.0175035**, about 1.75 cents, using published standard
rates of USD 0.75 per million input and USD 4.50 per million output tokens:
`4348 * 0.75 / 1e6 + 3165 * 4.50 / 1e6`. This is an estimate, not an invoice or
balance check. [Official model/pricing source](https://developers.openai.com/api/docs/models/gpt-5.4-mini).

The genuine output violated the contract:

- 02 returned yes with an N/A reason, while its applicability question said
  enough information existed from the outset.
- 04 returned numeric 15 with a non-null N/A reason explaining applicability.
- 07 returned N/A while its own atomic answer denied an interrupted ending.

Five other decisions passed structural/contextual gates; that is not a human
accuracy judgment. The original payload's field values were preserved unchanged;
no N/A response or score was silently corrected. There was no retry, second model,
batch or additional paid call. The server used `--live-call-limit 1` for the call,
then restarted with a zero cap for safe replay and continued mock use.

## Browser and saved artifacts

Open the retained result without another model request:

`http://127.0.0.1:8765/?diagnostic=a94e48f7-9886-4a3e-9510-6f7dffb167e9`

The browser visibly showed **REAL OPENAI RESPONSE — VALIDATION FAILED**, eight
original decision cards, the three errors, exact model/usage and no accepted
score. Downloaded diagnostic JSON matches the retained payload. The live button
is disabled under the zero cap. No browser console errors were observed. A
separate browser mock evaluation passed with eight v2 cards; the independent
human page still opened with all eight responses blank.

Ignored local artifacts: `outputs/app/live-smoke/auth-check.json`, `summary.json`,
`browser-rejected.png`; original diagnostic
`outputs/app/rejected-3ea9543c-4017-47b9-a149-7b9d9ec131aa.json`; enriched diagnostic
`outputs/app/rejected-a94e48f7-9886-4a3e-9510-6f7dffb167e9.json`. The latter adds
criterion diagnostics and links to the original, without changing AI decisions.
These generated files and transcripts are not committed.

To restore the current safe replay server:

```sh
PYTHONPATH=src python3 -m cqa.web --port 8765 --env-file /Users/User/data-challenge-2026/.env --allow-external-synthetic --model gpt-5.4-mini --live-call-limit 0
```

## Exact source changes

Created: `src/cqa/checklists/official-v2.json`, `src/cqa/evidence.py`,
`tests/test_evidence_repairs.py`, `docs/VALIDATION_REPAIR_REPORT.md`.

Modified: `pyproject.toml`; `src/cqa/__init__.py`, `engine.py`, `io.py`, `prompt.py`,
`providers.py`, `schemas.py`, `validation.py`, `web.py`; `web/app.js`, `web/app.css`;
`tests/helpers.py`, `test_scoring.py`, `test_web.py`, `test_web_ui.cjs`;
`README.md`, `PROJECT_FILE_MAP.md`, `TEAM_STATUS.md`, `docs/EVALUATION_ENGINE.md`,
`docs/LOCAL_MVP.md`. The ignored original `STATUS.md` receives the evidence record.
`scoring.py`, `loader.py`, historical v1 checklist, organizer materials, datasets
and all `tools/dev_review/` source files are unchanged.

## Remaining risks and control-data blockers

The first live run demonstrated that syntactically structured output can still
violate applicability and reason constraints. Next, strengthen provider-side
decision/applicability structure and calibration; any further paid call needs new
authorization because this task's one-call allowance is exhausted. No scoring
accuracy is established without independently reviewed labels and policy facts.

The unseen control endpoint/group/release/access and exact judging metric remain
unconfirmed. The current external-export policy intentionally allows only the
reviewed synthetic DEV subset; control data requires a reviewed authorization/
export policy, not relabeling it as synthetic. No control API is called here.

Saved checklist criteria/questions/weights/scales/N/A and evidence policies are
configurable and tested, but a browser checklist editor is not implemented. V1
contracts still restrict critical categories to the official three and discrete
scales to zero-based levels. These known characterization risks require explicit
design/organizer decisions for arbitrary replacements. Detailed verification/
disclosure ordering and semantic evidence meaning still require model/human
judgment. Appeals/accepted overrides and independent verification remain future
work; no filter silently changes an official score.
