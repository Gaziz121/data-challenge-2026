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

## Synchronization and publication

Use live Git preflight/fetch and history comparison, not this snapshot, to verify
current synchronization. Maintain one authoritative `main` and deliberate review.
The existing repository stays PRIVATE for development. The required eventual
public submission is a separately reviewed sanitized repository; do not expose
this private repository or copy its history publicly. Private sharing approval
does not authorize restricted materials or public redistribution.
