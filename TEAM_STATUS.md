# Team status - sanitized shared snapshot

Updated: 2026-11-07. Read `PROJECT_FILE_MAP.md` and inspect actual local files.
This is a team-readable snapshot of local `STATUS.md`, not another evidence ledger.
A clone intentionally lacks originals, real calls, signed access and local status.

## Ready for shared development

- Confirmed requirements and scoring specification are shared, including the
  November 7 user-relayed official clarifications and unresolved decisions.
- Three team-safe organizer PDF copies are shared. Visible pages are preserved;
  embedded links/actions and source metadata are removed. The signed DEV GET
  button is intentionally inactive. Original PDFs remain local and unchanged.
- `data/shared/DEV_synthetic_60.json` provides 60 unique synthetic text chats:
  RU=30, KZ=15, EN=15. IDs/content are unchanged. All five real voice records,
  their transcripts/audio links and related metadata are excluded.
- The full 65-record JSON remains authoritative and local-only. Its composition
  is RU=35/KZ=15/EN=15, including five real RU calls. Obtain it separately through
  an approved integration-owner handoff if a task needs voice/full DEV access.
- `CLAUDE.md` requires local filesystem discovery, including ignored files,
  before declaring materials missing. The tracked file map is maintained when
  important paths or sharing status change.
- Utility scripts inspect Git state and reproduce/check the shared subset.

## Independent human-review viewer

- `tools/dev_review/` supplies a separate offline viewer for the shared 60 chats;
  its README explains build/open and independent reviewer save/resume steps.
- It preserves all 882 messages, distinguishes all four roles, and offers eight
  initially blank criterion forms with permitted scales/N/A and evidence indexes.
  Original message IDs are absent and are never invented.
- Separate reviewer JSON/CSV downloads say `team_human`, never official Ground
  Truth. JSON resume validates dataset/rubric hashes and exact source evidence.
  No browser autosave, AI scores, external dependencies, dataset edits or engine
  imports. RU/KZ/EN browser checks and dataset-fidelity/export/resume tests passed.
- This is a local manual-review aid, not a completed benchmark or production
  application. QA notes left all real-conversation scores blank.

## Working evaluation baseline

- Implementation is isolated on `codex/cqa-evaluation-engine`; main is unchanged.
  See `docs/IMPLEMENTATION_REPORT.md` for the exact file manifest and verification.
- Python/Pydantic v1 contracts cover normalized conversations, configurable
  checklists/atomic questions, decisions, quote/scope evidence, deterministic scores,
  audit stages, check findings and future explicit decision revisions.
- Functional layers: normalization -> structural facts/applicability constraints ->
  optional pre-checks -> atomic primary evaluation -> schema/evidence/consistency
  validation -> optional verification checks -> exact deterministic scoring -> result.
- Checks return info/review/block findings. They cannot replace the original model
  decision or silently alter scores. A useful agent-presence check ships in baseline.
- All 53 tests pass, including 2,592 weighted-response combinations independently
  checked against Decimal arithmetic, all 60 synthetic chat mock runs, and local
  mock-only handling/export blocking for all five real-call transcripts.
- Real OpenAI Responses adapter is implemented and tested with injected offline
  transport. No usable credential was found in the environment/project env files;
  no genuine LLM call occurred. No paid service/resource was created.
- No source dataset/PDF was changed, and no real-call content/audio link was sent
  externally. CLI artifacts stay ignored under outputs. No accuracy established.

## Required next work, not yet executed

The local browser integration below supersedes the earlier plan to build the
first frontend. Full appeals/reviewer execution and advanced experiments remain
future work.

- Configure authorized API access/model through secure setup and run the first
  genuine synthetic evaluation; inspect evidence and factual uncertainty before
  interpreting its scores. Then separately authorize the human-reviewed benchmark.
- A complete production frontend, appeals/reviewer workflow, application of explicit revisions,
  criterion-specific verifiers, second LLM, risk routing and synthetic laboratory
  remain future work. The baseline supplies contracts and testable extension points.
- A 20-case human-reviewed DEV benchmark is proposed: 12 calibration, 8 internal
  holdout. No IDs selected, human labels assigned or model predictions generated.
  Full voice coverage needs separate local-call access. Future labels must say
  `team_human`; official per-conversation development Ground Truth is unavailable.
- Top-50 selection prioritizes scoring accuracy on 10 unseen API transcripts.
  Exact accuracy metric, numerical selection weights, control API group/access
  and some policy/rounding/voice edge cases remain unspecified. See requirements.
- No genuine external LLM evaluation, deployment or public repository has been
  created. Mock outputs are not predictions or human benchmark labels.

## First runnable local MVP

- Branch `codex/local-mvp-integration`, separate integration worktree. Engine base
  `ebcab33` reused; viewer source/tests/docs preserved in commit `f03d823` before
  integration. Original checkout/viewer outputs are unchanged; main stays `207b23f`.
- Start `PYTHONPATH=src python3 -m cqa.web --port 8765`, then open localhost.
  Conversation selection -> existing engine POST endpoint -> eight criterion
  cards, atomic checks, evidence jumps, N/A reasons and deterministic total works.
- Separate `/human-review/` keeps its original manual JSON/CSV/resume workflow.
  Only a read-only transcript renderer is shared; AI results never populate labels.
- Actual browser checks passed RU/KZ/EN source fidelity, eight results, scope
  jumps, evaluation download, missing-credential gating, blank human forms, real
  JSON/CSV downloads, reload/resume and human evidence navigation. QA human
  responses remained unscored. No browser console errors were observed.
- Combined Python suite: 66 tests, 65 passed, one expected skip for full DEV voice
  data intentionally absent from the integration worktree. Original checkout's
  56-test suite passed with no skips. Both JavaScript suites passed.
- No real LLM call: no authorized key available. Existing real adapter and model
  selection are wired; tests use injected offline transport only. No scoring/core
  contract change. See `docs/LOCAL_MVP.md`; no accuracy claim or public deployment.
- Concurrent independent QA appeared at final verification. Its 41 tests were
  run against the integrated engine: 29 passed, 12 failed, no errors. These expose
  inherited validation gaps, not integration regressions: contradictory atomic
  decisions, first-reply attribution, valid system verification evidence, critical
  category consistency and punctuation-only quotations. QA remains on its separate
  worktree/branch. Targeted gate fixes are the next engineering priority before
  trusting live evaluations; authorized API access is also still absent.

## Validation repairs and first genuine provider response

- The following supersedes the earlier credential/QA-blocker snapshot. All 12
  confirmed QA defects are fixed in the integration worktree; Claude's unchanged
  independent suite passes 41/41. The active rubric is 2026-11-07.v2, with unchanged
  official weights, anchors, scales, N/A conditions and deterministic arithmetic.
- Latest app suite: 75 tests, 74 passed, one expected local-only full-DEV skip;
  both JavaScript suites passed. Original human viewer/exports and original dirty
  checkout are preserved. QA branch/commit cbdec73 remains unchanged.
- Quote normalization is opt-in, restricted to formatting equivalence with exact
  original source spans. Original AI output and resolved evidence are both kept.
  Invalid criteria retain per-criterion diagnostics and original output, with no
  partial or redistributed quality total.
- Authorized key was read in memory from the original ignored .env. Authentication
  succeeded, then exactly ONE paid Responses call evaluated synthetic p1-ru-001.
  Model gpt-5.4-mini-2026-03-17; provider latency 10.132 s; 4,348 input / 3,165
  output tokens; estimated USD 0.0175035 at published standard rates.
- The genuine reply FAILED evaluation validation: 02 and 04 had non-null N/A
  reasons on applicable responses; 07 asserted N/A despite its applicability
  answer being false. No decision was silently changed, no total produced and
  no retry made. The web MVP shows all eight original decisions as a real rejected
  response, with errors/provenance/download. Live budget is now capped at zero.
- See docs/VALIDATION_REPAIR_REPORT.md. Remaining work is improving structured
  decision/applicability consistency before another explicitly authorized run,
  control-data export policy/API integration, checklist-editor UX and calibration.

## Output-contract corrections after independent RCA

- Engine 0.3.0: R1/R3/R4 fixed with no score coercion. Complete field diagnostics
  expose applicability conflicts even when metadata or nested evidence is invalid.
- Active model output 1.1 generates atomic checks before response; prompt v3 places
  applicability checks first and explicitly requires null N/A reasons on applicable
  answers. Model input/output ordering is covered by offline serialized-payload
  tests. Saved checklist v2 and deterministic scorer are unchanged.
- Current application suite: 83 run, 82 passed, one expected full-DEV voice skip.
  Claude's unchanged original 41 and new 15 tests all pass; both Node suites pass.
- No paid model calls, key loading, frontend work, new rule derivation system or
  Maker/Checker implementation.

## Read-only readiness audit

- R1/R3/R4 core commit is `9ee9605`. Subsequent audit changed no production code.
  See `docs/CORE_READINESS_AUDIT.md` and `docs/BACKEND_CONTRACT.md` for the frontend
  handoff and source/test evidence. No organizer control schema was invented.
- New normalized IDs can run locally with mock/scripted providers and round-trip
  results. Current HTTP IDs and real-provider export remain confined to the
  reviewed 60-chat derivative; unseen control input is not yet end-to-end ready.
- In-memory probes verify new criteria/questions, changed N/A condition/trigger,
  integer weights, zero-based integer scales and same-input/new-version runs.
  New category names, nonzero/fractional scales and per-request HTTP checklist or
  conversation objects are rejected. No save/version/editor endpoint exists.
- Atomic prompting, deterministic constraints/evidence gates and advisory hooks
  exist. Full rule-derived responses, an independent model checker, semantic
  accuracy proof and production counterfactual laboratory do not. QA checker and
  scenario harness remain separate experiments with proposed/unreviewed labels.
- Highest blockers: authorized unseen-input ingestion/export path, demonstrated
  live/semantic reliability, and frontend-facing dynamic-checklist delivery.

## Authorized-input and checklist backend delivery

- Engine 0.4.0 retains prompt baseline-v3, model-output 1.1 and the existing scorer,
  evidence gates and default rubric. No frontend or independent QA files changed.
- POST /api/evaluations accepts either the compatible DEV conversation_id or an
  internal supplied chat/voice record. New content requires a matching, unexpired
  owner-provisioned local grant: synthetic_test, organizer_control or organizer_dev. Unknown
  private input is denied. External export also needs an exact provider grant and
  separate runtime opt-in; original exact-DEV export policy remains the default.
- POST /api/checklists saves immutable ID/version snapshots; GET lists/retrieves
  them. Evaluation can select an explicit saved checklist version without restart.
  Old results/snapshots are retained. Unsupported scales/categories still reject.
- Verification: application97 run/96 passed/one expected original local-file skip;
  original independent41 and replay15 all pass; both Node suites pass. Fourteen new
  tests include unseen RU/KZ/EN, new criterion, changed weight/version, denied
  export/tampering, exact evidence and all five actual local voice transcripts.
  No paid calls, API-key loading, organizer API fetch or human labels produced.
- Organizer access/payload mapping and genuine semantic reliability remain
  unverified. The manifest records owner-reviewed permission; it does not certify
  organizer consent. See docs/BACKEND_CONTRACT.md for internal JSON/setup.

## C05/C08 conditional decision and source-coverage repair

- Engine0.5.0 / baseline-v4 / active rubric2026-11-07.v3, model output1.1.
  C05 now separates complaint presence from the obligation to respond. An explicit
  configurable conditional rule records derived answers/disagreements and blocks
  contradictions; it never replaces a model answer or silently alters scoring.
- C08 negative evidence is checked as source-ID interval union over the complete
  dialogue, including each negative category atomic in v3. Proofs retain hashes,
  evidence paths and missing IDs. This proves locator coverage, not semantic truth.
- Exact second live response replay retains both failures; no guessed atomic
  migration or retroactive score. Historical v1/v2 JSON and v2 digest are preserved;
  v2 remains selectable. No hardcoded QA C01/C07 rule maps copied into production.
- Application108 run/107 pass/one expected original local-file skip; new11 tests pass;
  all56 independent QA tests unchanged and passing without skips; Node2 suites pass.
  No paid/model/auth calls, key loading, frontend work or main merge in this pass.
- See docs/VALIDATION_REPAIR_REPORT.md. Real-model compliance with the new conditional
  atoms and scope instructions is not yet verified; semantic accuracy remains open.

## Atomic-first backend implementation

- Engine0.6.0 adds explicit saved rubric2026-11-07.v4 / atomic-v1 / wire1.2.
  C01/C02/C03/C05/C08 request facts only; official responses are backend-derived
  after evidence validation. Every criterion's N/A is backend-owned. C04/C06 retain
  model-selected official scales; applicable C07 remains discretionary.
- C03 validates need/protected request/action/confirmation references, eligible
  source roles and strict source ordering. Missing/late/unresolved proof blocks
  positive acceptance. Exact quotes and full negative coverage remain required.
- Original provider output/judgments are retained with explicit per-criterion
  origin/review records. Unknown, invalid, schema or conflict states block totals;
  no final response is silently overwritten. Legacy v1/v2/v3 remain unchanged;
  compatibility default stays v3 and v4 is explicitly selectable over HTTP/startup.
- Offline125 run/124pass/one expected original local-file skip; all56 independent
  QA tests unchanged/pass/no skips; full QA discovery also passes81 tests, including
  the newly committed25 offline lab tests on peer branch3ff9c76. Both JS suites pass. New17 tests include all
  three genuine failure replays, C03 chronology/roles, unseen RU/KZ/EN, new criteria,
  version/weight re-evaluation and no fabricated partial score. No frontend changes.
- Exactly one subsequent paid evaluation was explicitly authorized by the owner
  after offline checks. Its actual outcome is recorded separately in local evidence.

## Private synchronization policy

Use live Git preflight/fetch and history comparison, not this snapshot, to verify
current synchronization. Maintain one authoritative `main` and deliberate review.
The existing repository stays PRIVATE for development. The required eventual
public submission is a separately reviewed sanitized repository; do not expose
this private repository or copy its history publicly. Private sharing approval
does not authorize restricted materials or public redistribution.
