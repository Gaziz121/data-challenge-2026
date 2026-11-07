# Start here — Freedom CQA team

This is the team's authoritative onboarding and work-ownership guide. Read it
before choosing a branch. Technical contracts remain in the linked documents;
original organizer materials remain authoritative for competition requirements.
Snapshot: **November 7, 2026, Asia/Almaty**. Engine checked: `6481390`; independent
QA checked: `3ff9c76`. Branch tips can advance; inspect Git before relying on this
snapshot. [TEAM_STATUS.md](TEAM_STATUS.md) records the concise shared status.

For the reasoning behind the implementation, read
[Architecture Decisions](docs/ARCHITECTURE_DECISIONS.md). For five measurable
future trials, existing synthetic collections and the safe scenario/label
contribution workflow, read [Experiment Backlog](docs/EXPERIMENT_BACKLOG.md).

For daily branch/PR/conflict steps and which safeguards GitHub actually enforces,
read [Git collaboration workflow](GIT_WORKFLOW.md#four-person-daily-workflow).
The owner explicitly confirms PUBLIC visibility and authorizes reviewed safe
documentation publication. Latest remote integration is `6481390` (0.6.1);
setup/test evidence below is refreshed to that commit. This branch contains only
documentation changes on older source; run the integration clone, not this branch.

## 1. What we must deliver

Build an operator-quality evaluation application for RU/KZ/EN chats and voice-call
transcripts, using the eight-criterion Freedom checklist. Bot/system events are
context, not operator actions. The required workflow is checklist setup/save →
dialogue input → evaluation with per-criterion reasons/evidence and total → appeal
→ reviewer decision → recalculated final result with the original preserved.

- Top-50 selection prioritizes scoring accuracy against official Ground Truth on
  **10 unseen API transcripts**. The exact accuracy metric and numerical selection
  weights are unspecified. Functional completeness, UX, genuine new-input
  evaluation and technical diversity also matter. Never hardcode results by ID.
- Checklists must be flexible: criteria, wording, weights, answer types, scales,
  N/A settings and call-specific configurations. Current implementation supports
  only a subset of that flexibility; see the readiness table below.
- Required interface: HTML/CSS/JavaScript, structured for later Dynamics 365
  adaptation; no demonstration login required. Audio-based speech assessment is
  optional; do not infer acoustic quality from transcripts.
- Final handoff requires a **separate sanitized public GitHub repository** and a
  five-minute defense. The guide describes control release at hour 23 and code
  stop at hour 24; exact event start/deadline and presentation logistics still need
  confirmation. The owner has intentionally made this repository public; final
  submission scope/redistribution remains a separate decision. Do not change settings.

Read [requirements and user-relayed clarifications](case/CQA_REQUIREMENTS.md),
[exact scoring specification](case/CQA_SCORING_SPEC.md), and the three reviewed
[team-safe PDFs](case/shared/). Clarifications O1–O7 were relayed by the owner;
an original organizer-message export was not provided. Do not invent rules,
accuracy thresholds, factual policies or an official development answer key.

## 2. Choose the correct code

Repository: `https://github.com/Gaziz121/data-challenge-2026.git`.
Successful fetch and remote-head inspection confirmed these published branches:

| Branch | Observed tip | Use |
| --- | --- | --- |
| `main` | `207b23f` | Shared materials/setup baseline; lacks the current engine/app |
| `codex/cqa-evaluation-engine` | `ebcab33` | Original engine baseline; superseded for app development |
| `codex/local-mvp-integration` | `6481390` | Current engine 0.6.1, compatibility v3 and opt-in atomic v4, backend, browser MVP and human viewer |
| `feature/cqa-independent-qa` | `3ff9c76` | Claude's independent `qa/` tests, scenarios, replay and Accuracy Lab |
| `codex/team-handoff-docs-20261107` | Documentation-only branch based on `f4599f0` | This guide/navigation; proposed PR targets integration, no engine merge |

The QA branch descends from the original engine baseline. Its bundled `src/` is
older than integration; use its `qa/` against a pinned integration engine as below.
QA is not merged into integration; its report's older “not pushed” note is
historical. Human Viewer **source is pushed** on integration
(`f03d823` preservation commit and later integration); only generated viewer pages,
reviewer files and the original checkout's unfinished copies remain local.

Owner's Mac worktrees (paths are not teammate prerequisites):

| Directory under `/Users/User/` | Branch / ownership boundary |
| --- | --- |
| `data-challenge-2026` | Original engine checkout; dirty docs/viewer work must be preserved |
| `data-challenge-2026-integration` | Active Evaluation Engine session; do not edit another owner's worktree |
| `data-challenge-2026-independent-qa` | Claude's QA worktree; preserve independent tests |
| `data-challenge-2026-team-handoff-docs` | Isolated documentation worktree based on `f4599f0` |

The engine owner has now published `5d256ac` and `6481390`; they are no longer
local-only. This audit tested an archive of `6481390`, leaving the active worktree
untouched. The original dirty viewer/docs files also remain preserved.

Local working files, local commits, cached `origin/*` and actual remote heads are
different states. Use `git status`, `git worktree list`, `git branch -avv`,
`python3 -B src/git_preflight.py`, and an authorized `git fetch origin`.
See [safe Git workflow](GIT_WORKFLOW.md). Do not stash, reset, clean, merge or
rebase someone else's work to make setup easier.

## 3. First setup and safe run

Prerequisites: Git, Python **3.9+** with venv/pip, and Node
to run the two JavaScript tests. Verified here: Python 3.9.6, Pydantic 2.13.5,
Node 26.8.1. No npm install, frontend build, database, API key or raw DEV is needed
for the mock application and synthetic-data tests. These commands target macOS/
Linux shells; choose a new empty destination, never an existing owner's checkout.
Public cloning needs no invitation; accepted write access is needed to push a
branch in this repository. Two write invitations remain pending.

```sh
git clone --branch codex/local-mvp-integration --single-branch https://github.com/Gaziz121/data-challenge-2026.git freedom-cqa
cd freedom-cqa
git status --short
git rev-parse HEAD
python3 -B src/git_preflight.py
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e .
python3 -B tools/dev_review/build.py
PYTHONPATH=src python3 -B -m cqa.web --port 8765 --live-call-limit 0
```

Read `CLAUDE.md`, the [file map](PROJECT_FILE_MAP.md) and team status after cloning.
If HEAD differs from `6481390`, review the newer changes with the integration owner;
the verification counts here apply to that pinned snapshot. The integration clone
will contain this guide only after the documentation PR is accepted; this docs
branch is not an engine upgrade.

Open <http://127.0.0.1:8765/>. Select a synthetic RU/KZ/EN conversation, evaluate
with **MOCK**, inspect evidence and download the result. Mock scores are fixed
test fixtures, not quality judgments. Human Review opens separately at
<http://127.0.0.1:8765/human-review/>. Stop with Ctrl+C; choose another port if
8765 is occupied. Running from the repository root is required: editable source
expects the tracked data and web/viewer assets alongside it.

For the opt-in atomic path on integration 0.6.1, stop the default server and use
`PYTHONPATH=src python3 -B -m cqa.web --port 8765 --checklist src/cqa/checklists/official-v4.json --live-call-limit 0`.
Atomic mock facts may be unresolved and intentionally produce no quality total.
See the atomic contract before changing frontend result rendering.

`.env.local` is optional and ignored. Only an owner-authorized live run needs
`OPENAI_API_KEY` and an explicit model (`CQA_MODEL` or `--model`). Have the owner
provision the key securely; never paste it in chat, source, browser, command
arguments or PRs. The server does **not** automatically load `.env.local`; explicit
`--env-file .env.local` reads only the key/model settings without shell expansion.
Do not source an env file. Keep the documented zero-call cap for onboarding;
live opt-ins and any nonzero budget require a separate owner decision under the
[backend export policy](docs/BACKEND_CONTRACT.md#content-authorization-for-supplied-input).
No live command needs to be run to complete onboarding.

## 4. Tests and reproducibility

In a second terminal, from the engine clone with its venv activated:

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
node tests/test_dev_review.cjs
node tests/test_web_ui.cjs
PYTHONPATH=src python3 -B -m cqa list
PYTHONPATH=src python3 -B -m cqa schema result
```

At `6481390`: **127 Python tests, 125 passed, two expected skips** without local raw
DEV; both Node suites pass. The skipped loader and authorized-voice checks need
the local-only original. Do not remove the skips or substitute synthetic chats
and claim real-call coverage. Once permitted raw DEV is provisioned at its mapped
path, rerun the relevant tests; `CQA_TEST_FULL_DEV` can select an alternate file
for the authorized-input voice test only. All these suites use offline providers.

### Independent QA and Accuracy Lab

Keep the engine venv active. From the engine clone root, create a separate QA
clone and export the **tested engine commit** into its ignored temporary folder:

```sh
CQA_ENGINE_ROOT="$(pwd)"
git clone --branch feature/cqa-independent-qa --single-branch https://github.com/Gaziz121/data-challenge-2026.git ../freedom-cqa-qa
cd ../freedom-cqa-qa
git rev-parse HEAD
mkdir -p tmp
mkdir tmp/engine-6481390
set -o pipefail
git -C "$CQA_ENGINE_ROOT" archive 6481390de7f4bd1905b79168c54b600642dc7ef7 src data/shared | tar -x -C tmp/engine-6481390
export PYTHONPATH="$(pwd)/tmp/engine-6481390/src"
python3 -B -c 'import cqa; print(cqa.__file__)'
python3 -B -m unittest discover -t . -s qa -v
python3 -B -m qa.lab demo --engine-commit 6481390de7f4bd1905b79168c54b600642dc7ef7
```

Use a new snapshot directory for a new engine commit; do not overwrite a prior
snapshot. Check that QA HEAD is `3ff9c76` for these results. Against the pinned
engine: **81 QA tests pass without skips**, and the scripted Lab demo runs.
The demo is explicitly **not a semantic accuracy measurement**. Return to the
engine clone and `export PYTHONPATH=src` before further engine work.

[Accuracy Lab instructions on the QA branch](https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/lab/README.md)
cover `ingest`, `report`, `compare` and human-label import. Lab reads saved accepted
results and rejected diagnostics, verifies sources, and compares identical
baseline/candidate cells without changing decisions or calling a model. Preserve
every rejection. Use `--engine-commit` matching the engine that produced each run;
the flag records provenance, it does not switch engine code.

Keep `proposed_unreviewed` AI scenario labels, `team_human` judgments, disputed
cells and ambiguous cells distinct. Mock/test-double cells are not assessed as
model accuracy. Tune on calibration; use frozen holdout only for the designated
final check with `--holdout-confirm`, and record exposure. A DEV benchmark split
is proposed, not adopted/labeled. Lab predates v3 rule/coverage additions and v4 wire 1.2/projection semantics.
These 81 tests and the demo use compatibility mode; they do not independently
certify the atomic-v4 path. D must review raw-wire/projection handling and new
fields before using Lab to certify that mode.

## 5. What exists and how it connects

`conversation → normalization → checklist + facts → atomic provider output →
validation/evidence/rule checks → deterministic scoring → result + audit`.
HTTP wraps this same pipeline. Lab reads saved artifacts independently.

| Component / source | Implemented behavior and limit |
| --- | --- |
| `src/cqa/loader.py`, `schemas.py` | Strict known DEV shape; preserve text/order/timestamps/source IDs and bot/system context; normalize local message IDs. New organizer envelopes still need mapping. |
| `checklists/official-v3.json`, `checklists.py`, `preprocessing.py` | Active rubric `2026-11-07.v3`, structural facts and immutable checklist versions; v1/v2 retained. Supports configurable IDs/questions/integer weights/zero-based integer levels/N/A, not arbitrary categories or fractional/nonzero-minimum scales. |
| `prompt.py`, `providers.py`, `engine.py` | Engine 0.6.1; compatibility default `baseline-v4`/rubric v3/output 1.1 and historical 1.0 reading. Mock and real adapter; no independent second-model checker. |
| `atomic.py`, `atomic_prompt.py`, `checklists/official-v4.json`, `tests/test_atomic_path.py` on integration | Opt-in `atomic-v2`/wire 1.2: facts-only C01/C02/C03/C05/C08, configured backend-derived decisions and all-criterion applicability; C04/C06/C07 applicable judgments remain discretionary. Raw provider output and criterion review origins preserved; unresolved/conflicting facts block totals. |
| `validation.py`, `evidence.py`, `decision_rules.py`, `coverage.py` | Strict field/applicability/atomic/evidence checks; optional formatting-only quote resolution; configured conditional agreement and negative critical scope coverage. Blocks contradictions, retains original reply, never replaces a model answer. Locator coverage does not prove semantic truth. |
| `scoring.py` | Exact arithmetic; weighted 01–07, permitted N/A redistribution, two-decimal final total. Critical 08 is a separate flag, with no invented penalty/cap. HALF_UP is a documented local rounding convention. |
| `web.py`, `access.py`, `docs/BACKEND_CONTRACT.md` | Loopback API, content-bound expiring input approvals, separate provider export permissions, checklist save/select, retained rejection diagnostics. No organizer API fetch or production hosting. |
| `web/`, `tools/dev_review/` | Runnable browser MVP and separate blank human-label viewer; no checklist-editor or appeal/reviewer execution UI. |
| QA branch `qa/`, `qa/lab/` | Adversarial/replay tests, synthetic scenarios, independent checks, paired offline artifact comparison. AI proposals and scripted demos are not official/human reference answers. |

See [engine internals](docs/EVALUATION_ENGINE.md) for compatibility detail and
the [published atomic contract](https://github.com/Gaziz121/data-challenge-2026/blob/6481390de7f4bd1905b79168c54b600642dc7ef7/docs/BACKEND_CONTRACT.md#atomic-first-contract-engine061-explicit-rubric-v4)
for the opt-in path. Historical provider failures, including the atomic-v1 run,
remain rejected; **no accepted live quality total or semantic accuracy is recorded**.
This documentation audit made no provider calls. `structurally_valid` means gates passed, not that an
answer is factually correct. Appeals/revision contracts exist; execution is incomplete.

## 6. Frontend teammate: integrate through the contract

Own `web/` and `tests/test_web_ui.cjs`; coordinate any shared renderer changes with
the human-review owner. Use the same-origin backend above, not a separate dev
origin: there is no CORS support. The backend serves an explicit asset list, so
new asset paths require coordination with workstream C. Keep all API keys server-side.

| Route | Frontend purpose |
| --- | --- |
| `GET /api/config` | Read checklist, provider readiness and remaining call budget |
| `GET /api/conversations`, `GET /api/conversations/{id}` | Select approved DEV and render normalized transcript |
| `POST /api/evaluations` | Exactly one DEV ID or owner-authorized supplied record; optionally select saved checklist version |
| `GET /api/checklists`, `GET /api/checklists/{sha256}`, `POST /api/checklists` | List/retrieve/save immutable checklist versions |
| `GET /api/diagnostics/{id}` | Inspect retained rejected output if authorized |
| `GET /human-review/` | Separate human-review workflow |

The [backend contract](docs/BACKEND_CONTRACT.md) is authoritative for exact request
and response fields, Origin/JSON requirements, permissions, limits and errors.
Start with this safe request against the running app:

```sh
curl --fail -H 'Origin: http://127.0.0.1:8765' -H 'Content-Type: application/json' --data '{"conversation_id":"p1-ru-001","provider":"mock"}' http://127.0.0.1:8765/api/evaluations
```

Render totals/points from backend strings; do not recompute rounded contributions.
Join evidence by conversation ID plus local message ID. Show mock/review status,
N/A reasons, atomic checks and critical flags. On 422, show issues and fetch a
diagnostic only when an ID exists; a rejected output has **no accepted score**.
Handle 403/409/413/415/422/502 explicitly; do not silently retry a paid request or
replace it with mock. No appeal or result-history GET endpoint currently exists.

## 7. Independent human review and data provisioning

Build the viewer as above, or open `outputs/dev_review/index.html` in a browser.
[Reviewer instructions](tools/dev_review/README.md) explain exact evidence and
export/resume validation. Each reviewer starts blank with a separate reviewer ID,
without seeing AI scores or importing someone else's labels. Save JSON regularly;
there is no browser autosave. CSV is for comparison, not resume. Keep each original
`team_human-<reviewer>-<timestamp>.json` separate under ignored
`outputs/dev_review/labels/`; never overwrite, auto-merge or call it official GT.
Only explicit JSON import resumes a review. Null means unscored, not zero/N/A.
Lab can import multiple JSON files; disagreement is excluded and listed, not
adjudicated automatically. Preserve source/dataset/rubric hashes and evidence.

| Material | Available from clone? / action |
| --- | --- |
| 60 synthetic chats, RU=30/KZ=15/EN=15; 882 messages | Yes: `data/shared/DEV_synthetic_60.json`; already public; organizer redistribution permission unverified |
| Team-safe organizer PDFs, specs, engine/app/viewer source | Yes on integration; safe PDFs omit signed API access |
| QA/Lab source, synthetic scenarios and replay fixtures | Yes on QA branch; separate from integration |
| Full 65-record DEV, RU=35/KZ=15/EN=15, including five real RU calls | No: owner-provisioned `data/raw/DEV_conversations.json`; includes restricted transcripts/signed audio links |
| Original PDFs, local `STATUS.md`, generated outputs/reviewer labels | No: see [file map](PROJECT_FILE_MAP.md); originals/evidence remain local |
| API credentials, organizer endpoint/group/access, `restricted/input-approvals.json` | No: separate secure owner handoff; never commit or copy into PRs |

Inspect actual local directories, including ignored files, before requesting a
material again. Full originals exist in the owner's checkout; they are deliberately
absent here. Do not copy them into Git. New organizer control input needs verified
access/payload mapping and a matching local grant even for HTTP mock evaluation.
Requests cannot self-authorize. External model export additionally needs explicit
provider permission, runtime opt-in, key/model and budget. The repository is now
public by owner decision; never add full DEV, signed URLs, human evidence, secrets
or other restricted material. Public read access is not organizer redistribution permission. Ignore rules
are not an upload review; inspect exact staged contents and outgoing history.

## 8. Four workstreams and file ownership

Assign one person to each stream before editing; names are not yet recorded here.
Workstream B is owned by the frontend teammate. C is the integration owner; D is
the submission/QA owner with a named human backup still to be assigned. A's active
engine session retains ownership of production evaluation changes.

| Stream | Deliverable and acceptance | Owned files / dependencies |
| --- | --- | --- |
| **A. AI Evaluation Engine and semantic accuracy** | Improve valid live decisions and rubric fidelity; deliver versioned prompt/checklist changes plus reproducible baseline/candidate evidence. Acceptance: engine + unchanged independent regressions pass; retain rejections; evaluate identical inputs with reviewed labels and report regressions/coverage. Paid tests require separate budget authorization. | `src/cqa/` evaluation modules, versioned rubric JSON, core `tests/test_*.py`. Excludes C's files below. Depends on D's independent labels/Lab and approved factual policy sources; notify B/C of contract changes. |
| **B. Frontend and UX — teammate owner** | Complete checklist editing, new-input UX, evidence/rejection states and then appeal/reviewer screens when supported. Acceptance: RU/KZ/EN flow on mock, immutable checklist save/select/re-evaluate, exact source jumps, backend totals, explicit errors, independent human labels preserved; Node UI checks pass. | `web/`, `tests/test_web_ui.cjs`. Depends on C's API; request endpoint/asset additions rather than editing backend/core. `tools/dev_review/transcript.js` is shared with D; coordinate before editing. |
| **C. Backend integration, organizer control API and deployment** | Implement verified organizer adapter and permitted ingestion; define missing appeal/history services with A/B; design and verify deployment. Acceptance: unseen permitted RU/KZ/EN chat/voice works without ID lookup, denied input/export stays denied, checklist snapshots and provenance survive, loopback protection remains until reviewed replacement. Deployment needs tested access/privacy controls, persistence and operational instructions. | `src/cqa/web.py`, `access.py`, `checklists.py`, `tests/test_web.py`, `tests/test_control_backend.py`, `docs/BACKEND_CONTRACT.md`; new organizer/deployment files by agreement. Depends on organizer access/schema/permissions, A's contracts and B's needs. |
| **D. QA, Accuracy Lab, reproducibility and final submission** | Maintain independent gates, review v3/v4 Lab compatibility, collect separate human labels, freeze calibration/holdout, compare candidates, assemble sanitized submission and defense. Acceptance: pinned engine+QA runs; source hashes/counts and disputed/unresolved denominators reported; no scripted accuracy claims; public export passes human review and runnable setup. | QA branch `qa/`; `tools/dev_review/` and viewer tests on integration-derived branch; onboarding/status/file map and final docs. Depends on language-competent reviewers, A's saved runs, C's permitted control workflow; publication requires explicit approval. |

`schemas.py`, `loader.py`, `pyproject.toml`, `.gitignore` and scoring semantics are
cross-stream contracts: A coordinates changes with C and D before editing; B uses
the published schema. D reviews independent tests; A must not weaken them to make
a candidate pass. Avoid concurrent edits to shared Markdown; D collects status
updates and maintains navigation. Workstreams describe planned ownership, not
claims that missing features or deployment are complete.

## 9. Lightweight GitHub workflow and next priorities

1. Start from the agreed integration commit in your own clone/worktree. Create
   an isolated branch, e.g. `git switch -c codex/frontend-checklist-ui`; use distinct
   `codex/engine-*`, `codex/backend-*`, `codex/qa-*` topics for the other streams.
   D can keep Lab-only changes on a branch from QA. Agree paths and contracts first.
2. Keep PRs limited to one deliverable. Stage named files, inspect the staged diff
   and confidential content, and include base commit, behavior, exact checks,
   skips/limitations and any contract change. Keep generated outputs/labels local.
3. Open a PR to **`codex/local-mvp-integration`**, not default `main`, for integrated
   app work. C reviews integration; A reviews semantics; D checks reproducibility.
   QA-only PRs can target `feature/cqa-independent-qa` until an integration PR is
   agreed. No automatic merges/rebases or duplicate copying of engine trees.
4. Recommended integration sequence: review this docs-only PR against latest
   integration (`6481390` at audit); separately review Claude's **`qa/` additions**
   for integration, preserving independent fixtures and provenance. Do not replace
   newer engine source with the QA branch's baseline. C chooses the integration
   method after testing the then-current engine; no merge has been performed here.
5. After integrated verification, C can propose a reviewed main update. Final
   public submission is a separate sanitized export/repository after explicit
   authorization, never a visibility change or push of private history.

Public read access is available. Owner plus one collaborator have accepted write
access; two write invitations remain pending. Each teammate should verify their
own branch/PR workflow after accepting, with named ownership agreed first.

Immediate blockers to the complete competition workflow: semantic reliability
and factual-policy evidence; human labels/frozen DEV benchmark; organizer control
access/schema/consent and adapter; checklist-editor and appeal/reviewer execution;
deployment/access/persistence decisions; confirmed timing and named owners/backup.
QA/Lab and engine code are obtainable now, but are not unified on one branch.
Mock app/frontend work can proceed independently with no secrets or raw DEV.
Documentation publication is explicitly authorized; C should review the PR and
latest engine contract before accepting it. No merge is performed by this audit.
