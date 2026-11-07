# Team status — sanitized shared snapshot

Updated: November 7, 2026, Asia/Almaty. Start with
[TEAM_START_HERE.md](TEAM_START_HERE.md) for the single onboarding workflow and
four-person ownership plan. Read [PROJECT_FILE_MAP.md](PROJECT_FILE_MAP.md) and
inspect disk before requesting missing materials. Local `STATUS.md` remains the
owner's detailed evidence ledger; this snapshot contains no restricted evidence.

[Architecture decisions](docs/ARCHITECTURE_DECISIONS.md) distinguish implemented
choices and Socrates-inspired foundations from deferred work.
[Experiment backlog](docs/EXPERIMENT_BACKLOG.md) proposes five measurable trials
and documents synthetic-scenario provenance, proposed labels and frozen splits.
These documentation additions generated no conversations/labels, changed no
production/QA logic and executed no live experiments.

## Published and obtainable

A successful fetch and live remote-head check confirmed:

| Branch | Observed tip | Team use |
| --- | --- | --- |
| `main` | `207b23f` | Materials/setup baseline, not the current app |
| `codex/cqa-evaluation-engine` | `ebcab33` | Initial engine baseline |
| `codex/local-mvp-integration` | `f4599f0` | Current engine/backend/browser MVP/human-viewer source |
| `feature/cqa-independent-qa` | `3ff9c76` | Independent QA and offline Accuracy Lab |

The remote is confirmed PRIVATE. These observations are a snapshot, not a lock
on ongoing work. Another session owns the active integration worktree.
`codex/team-handoff-docs-20261107` is local-only, based on `f4599f0`; this onboarding
revision has not been pushed or merged. The original checkout's dirty work and
all other worktrees remain preserved. No production/QA source changed here.
A final read-only check found the active integration session's uncommitted
`src/cqa/schemas.py` changes and untracked `src/cqa/atomic.py`; these remain
local-only, outside the pinned tests and published snapshot.

## Current implementation and executed verification

- Engine 0.5.0 / prompt `baseline-v4` / model output 1.1 / active rubric
  `2026-11-07.v3`; historical output 1.0 and rubric versions retained. Atomic
  evaluation, deterministic facts, applicability/evidence/consistency gates,
  conditional C05 agreement and full source-ID coverage for negative C08 findings
  precede exact deterministic scoring. Checks preserve original decisions;
  locator coverage is not proof of semantic truth.
- Loopback browser MVP and backend support approved DEV, owner-authorized supplied
  chat/voice records, immutable checklist save/version selection, retained rejected
  outputs and source evidence. See [current backend contract](docs/BACKEND_CONTRACT.md).
- Independent Human Review Viewer source **is tracked and pushed on integration**.
  Generated HTML, independent JSON/CSV downloads and original unfinished copies
  remain local-only. It starts blank and never imports AI decisions as labels.
- At the pinned integration snapshot: 108 Python tests run, 106 pass, two expected
  skips because the raw full DEV file is absent; both Node suites pass. Setup
  requires upgrading old pip before editable installation. Python 3.9.6,
  Pydantic 2.13.5 and Node 26.8.1 were checked.
- Claude's QA at `3ff9c76`: 81 tests pass without skips against integration
  `f4599f0`; offline Accuracy Lab demo runs. QA's own bundled engine is older, so
  onboarding explicitly selects a separate pinned engine snapshot. Lab ingests
  saved accepted/rejected artifacts and compares baseline/candidate outputs;
  it does not call a model, alter scores or adjudicate human disagreements.
- No genuine API call, credential loading or new human labels in this audit.
  Repair history records two genuine responses rejected by validation, with no
  accepted live quality total. No measured semantic accuracy is established.
  Scripted Lab demonstrations and mock application scores are not accuracy results.

## Sharing and separate provisioning

The clone provides 60 unchanged synthetic chats (RU=30/KZ=15/EN=15), the reviewed
team-safe PDFs and source code on the branches above. It does not provide the
full 65-record DEV (RU=35/KZ=15/EN=15, including five real RU calls), original
PDFs/signed access, API keys, local evidence, approval manifests or reviewer files.
Check the inventory and local paths, then obtain necessary originals/access from
the owner through a permitted secure handoff. Never stage them. New supplied
input needs exact expiring local grants; external export requires separate
permission and opt-in. Onboarding uses `--live-call-limit 0` and needs no key.

## Incomplete and next priorities

1. Establish semantic reliability with reviewed factual/policy evidence and
   independent language-competent human labels. Adopt/freeze the proposed DEV
   calibration/holdout split explicitly; no official per-conversation DEV GT exists.
2. Review Lab compatibility with v3 conditional-rule and coverage fields before
   relying on it for new-engine acceptance; passing existing QA is narrower evidence.
3. Obtain verified organizer control access/payload/permissions and implement the
   adapter. Internal authorized-input support does not mean control API integration
   is complete. Exact official accuracy metric/selection weights remain unknown.
4. Complete checklist editing and appeal/reviewer/recalculation execution. Current
   configuration rejects unsupported categories and fractional/nonzero-minimum
   scales. Second-model checking is not implemented.
5. Verify private-repository access for all four teammates (only owner access was
   checked), assign named A/B/C/D owners and submission backup, confirm timing, and
   agree deployment/access/persistence requirements. Current server is local-only,
   single-evaluation and same-origin; no production deployment is verified.
6. After explicit approval, publish/review this docs branch against integration;
   separately review QA additions without replacing the newer engine baseline.
   Do not merge automatically. Later propose a reviewed main update and a separate
   sanitized public submission repository; never publish private history.

Historical milestone counts and original experiments remain in linked
[implementation](docs/IMPLEMENTATION_REPORT.md), [MVP](docs/LOCAL_MVP.md),
[readiness](docs/CORE_READINESS_AUDIT.md) and [repair](docs/VALIDATION_REPAIR_REPORT.md)
reports. Their older limitations do not override current code/the backend contract.
