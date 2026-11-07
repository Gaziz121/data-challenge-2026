# First runnable local CQA application

Integration date: 2026-11-07, Asia/Almaty. This is local-only private development.
No engine replacement, architecture redesign, deployment or public repository.

## Start and use

On the owner's Mac, the integration worktree is separate from the original:

```sh
cd /Users/User/data-challenge-2026-integration
PYTHONPATH=src python3 -m cqa.web --port 8765
```

Open `http://127.0.0.1:8765/`. On another checkout, run the second line from that
checkout's root. Python 3.9+ and the existing Pydantic 2 dependency are required;
if absent, `python3 -m pip install -e .` installs the repository's declared runtime.
No Node dependency or frontend build is needed to run the app. Stop with Ctrl+C.
If port 8765 is occupied, choose another `--port`; the startup prints its exact URL.

1. Select RU/KZ/EN and a conversation. All 60 reviewed synthetic chats are listed.
2. Read the original transcript: client, operator, bot and system are distinct.
3. Click Evaluate. The backend calls `cqa.engine.evaluate` with the saved checklist.
4. Inspect each of the eight responses, weighted contributions, explanations,
   permitted N/A condition, actual N/A reason when present, atomic answers and
   evidence. Scope links highlight all referenced turns; quote links reach the
   specific message. The total and critical flag come unchanged from the engine.
5. Download the full versioned result JSON or find it under `outputs/app/<id>.json`.
6. Choose another conversation; old results clear rather than attaching to a new
   transcript. Errors return no score; failed real calls never fall back to mock.

Default mock output always says `MOCK`, `mock_only` and “not a quality judgment.”
Its fixed 0.00 total/false critical flag are wiring fixtures only. Every decision
requires review. No genuine semantic assessment or scoring accuracy is implied.

## Independent human labels

The separate link opens `/human-review/` in a new tab with no opener reference.
This is the existing viewer, with blank manual forms, JSON/CSV exports and resume.
It never requests AI evaluation results and has no shared label store or browser
autosave. Human exports remain `team_human`, never official Ground Truth.
The standalone command is unchanged:

```sh
python3 -B tools/dev_review/build.py
```

`outputs/dev_review/index.html` remains self-contained. Its only refactor extracts
the original transcript renderer into `tools/dev_review/transcript.js`, embedded
by the builder and reused on the evaluation screen. It preserves exact text,
source speaker/order/timestamps and the distinction between original IDs and
engine-local evidence IDs. No human form/export logic was rewritten.

## Authorized real-model setup

No key was found in the process environment or project env files, so **zero real
LLM calls** occurred. The existing OpenAI adapter is actually present and wired.
No paid resource, account, credit purchase or key was created in this pass.

Minimal steps once the owner chooses authorized access:

1. Use the secure OpenAI API key setup to save an authorized key as
   `OPENAI_API_KEY` in this worktree's ignored `.env.local`, or supply that variable
   through the process environment. Do not paste a key into chat, a command line,
   a browser field or tracked source. Provisioning is a separate owner action.
2. Choose a model available to that project with structured-output support. Restart:

   ```sh
   PYTHONPATH=src python3 -m cqa.web --port 8765 --env-file .env.local --allow-external-synthetic --model YOUR_AUTHORIZED_MODEL
   ```

   Omit `--env-file` when using the environment. Replace `YOUR_AUTHORIZED_MODEL`
   with the chosen actual model ID. The optional local `CQA_MODEL` setting can
   supply the same default; `--model` takes precedence. Env-file reading supports
   only these two settings, strips surrounding quotes and performs no shell
   expansion. It never serves/logs key contents.
3. Select OpenAI LLM in the browser, confirm the model field and click Evaluate
   once on a synthetic DEV conversation. Inspect returned provider/model, response
   ID, latency, usage, review flags and source evidence before interpreting scores.

Missing credentials, opt-in or explicit model disable the live browser button and
are also rejected server-side. Key presence is readiness metadata, not proof of
validity, model access or sufficient quota. API failures are reported, never
fabricated as success. Real switching uses the same pipeline/scorer and requires
no scoring-code changes; an HTTP test exercises this through the real adapter
with injected offline transport, clearly not a genuine provider evaluation.

The original provider's exact synthetic membership/hash gate is unchanged. Only
the approved 60-chat derivative is exposed by the app. All five real calls remain
local-only in the original checkout, are not listed and cannot be submitted by
ID. No raw dataset path, arbitrary upload, audio URL or secret is accepted by the
HTTP API. The server binds only to 127.0.0.1 and rejects foreign Host/Origin on
evaluation requests. It serves an explicit asset list, never the repository root.

## Small HTTP adapter contract

| Route | Behavior |
| --- | --- |
| `GET /api/config` | Nonsecret readiness, default model and saved checklist |
| `GET /api/conversations` | IDs/languages/channels of the approved synthetic chats |
| `GET /api/conversations/{id}` | Existing normalized `Conversation` contract |
| `POST /api/evaluations` | JSON `conversation_id`, `provider` (`mock`/`openai`), optional `model`; existing `EvaluationResult` or explicit error |
| `GET /human-review/` | Existing generated independent manual viewer |

POST requires same-origin `Origin` and JSON, rejects unknown fields/unsupported
providers and limits the body to 4 KB. Only one evaluation runs at a time; an
overlapping request returns 409. Successful results are saved only under ignored
`outputs/app/`; this is a development server, not a production multiuser service.
Use `--checklist path/to/versioned-checklist.json` to apply a saved custom rubric.
No checklist editor, appeal executor or accepted human-override execution is
added. All maker/checker, atomic-question, verification, risk findings, revision
history and deterministic-scoring extension points remain intact. Filters cannot
silently rewrite official decisions. Model comparison and Synthetic Accuracy Lab
remain future experiments rather than new runtime frameworks.

## Preservation and exact integration scope

The original checkout at `/Users/User/data-challenge-2026` had engine `ebcab33`
plus uncommitted viewer work. Before editing, 12 existing viewer/source/test/doc/
output files were copied with hashes to its ignored
`tmp/integration-preserve-62fo6jiv/`. All 12 original files still match those hashes.
The original generated viewer and its local outputs were not replaced.

Integration branch: `codex/local-mvp-integration`. Worktree base: `ebcab33`.
Viewer preservation commit: `f03d823` (five viewer sources, two test files, three
documentation additions). The final integration commit is reported in delivery
and the local evidence ledger; main remains `207b23f` pending integration review.

New integration files: `src/cqa/web.py`; `web/index.html`, `web/app.js`,
`web/app.css`; `tools/dev_review/transcript.js`; `tests/test_web.py`,
`tests/test_web_ui.cjs`; this document.

Modified integration files: `tools/dev_review/build.py`, `tools/dev_review/viewer.js`,
`tools/dev_review/README.md`, `README.md`, `TEAM_STATUS.md`, `PROJECT_FILE_MAP.md`.
Existing engine/provider/scoring/schema/checklist source files are unchanged.
Local evidence is appended to the ignored original `STATUS.md`; generated app
results, browser checks, screenshots and unscored QA exports stay ignored.

## Executed verification

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
node tests/test_dev_review.cjs
node tests/test_web_ui.cjs
```

- Combined Python run: 66 tests, 65 passed, zero failures, one expected skip
  because the separate worktree deliberately lacks the five-call raw DEV file.
  Original checkout's 56-test suite also passed with no skips. Both JavaScript
  suites passed. Existing exhaustive 2,592-combination scoring tests are unchanged.
- Actual browser evaluations: `p1-ru-001`, `p1-kz-001`, `p1-en-001`. Each rendered
  all 12 source turns and eight results. DOM values were saved locally and matched
  to every original text/speaker/order/timestamp and engine-local evidence ID.
- Scope evidence highlighted the 12 expected turns. JSON evaluation download was
  received and schema-validated. New selection clears stale scores. Missing-key
  OpenAI selection disabled evaluation with a clear reason and no request.
- Independent human page started with eight blank responses even after AI-screen
  use. Actual JSON and CSV downloaded successfully. Reload started blank; JSON
  resume restored only a marked UI-test note/evidence and all eight responses
  remained null. Human evidence navigation worked. No real human labels assigned.
- Backend integration covers the real OpenAI adapter with an offline N/A fixture:
  applicable weight changes to 85, with no scoring rewrite. UI rendering tests
  verify N/A/reason display and that totals are displayed from backend values.
  No genuine LLM N/A decision was observed or claimed.
- App and human-page console checks had zero errors. Screenshots and evidence
  reside under `outputs/app/browser-qa/`. Source hashes and staged confidential
  values are checked before upload; no dataset, key, audio link or output is staged.

## Concurrent independent QA findings

A separate worktree appeared during final verification:
`/Users/User/data-challenge-2026-independent-qa`, branch
`feature/cqa-independent-qa`, commit `cbdec73`. It was not created, edited,
merged or pushed by this integration task. Its report/tests are separate from
the 66-test application suite above.

All 41 QA tests were executed against the integration worktree's actual engine:
29 passed, 12 failed, zero errors/skips. The failures reproduce inherited issues
on the unchanged `ebcab33` core: criterion 01 can cite a later operator reply;
some atomic answers can contradict final responses; criterion 03 wrongly rejects
system-only verification evidence; critical categories can contradict atomic
answers; and punctuation-only quotations can pass the substring gate. Details
remain in that worktree's `qa/REPORT.md`; the local results are saved as
`outputs/app/browser-qa/independent-qa.json`.

The integrated workflow is usable, but the original validation gates are not a
complete implementation of semantic rubric consistency. These newly available
findings are disclosed, not folded into a passing-test count or silently fixed
through score overrides. Resolving them with small configurable, reviewed gate
changes is the single highest-priority next engineering step. Authorized API
access/model selection is separately required for the first genuine evaluation.
Accuracy still requires independent human labels and approved factual/policy
references; this functional integration does not establish scoring accuracy.
