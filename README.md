# Freedom Broker CQA Hackathon — team development workspace

**[Start here: four-person team onboarding](TEAM_START_HERE.md).**
The guide is the single setup/ownership entry point. See
[Git collaboration and actual safeguards](GIT_WORKFLOW.md#four-person-daily-workflow),
[architecture decisions](docs/ARCHITECTURE_DECISIONS.md) and
[experiment/scenario backlog](docs/EXPERIMENT_BACKLOG.md).

Owner decision, November 7: this repository is intentionally **public**.
Only reviewed public-safe documentation is authorized in this handoff; raw DEV,
real calls, keys, approvals and reviewer outputs remain excluded. Organizer
redistribution rights for already-tracked derivatives are not certified by this audit.

Accuracy, reproducibility and required end-to-end functions take priority over
cosmetics. This workspace now includes a working modular Python evaluation baseline.
Three historical single-pass OpenAI responses were rejected by validation.
The new explicit atomic-first path is described below; live outcomes are retained locally. Read the [requirements](case/CQA_REQUIREMENTS.md)
and [scoring specification](case/CQA_SCORING_SPEC.md).

Validation repairs, the 41/41 independent QA result and the exact single-call
OpenAI outcome are documented in [the repair report](docs/VALIDATION_REPAIR_REPORT.md).

The current core is engine 0.6.1. Compatibility mode retains baseline-v4/schema1.1.
Select rubric `2026-11-07.v4` for atomic-v2/schema1.2: the model supplies facts and
the backend derives unambiguous decisions after validating their evidence.
C04/C06 remain discretionary; N/A is backend-derived for every criterion. See the
[readiness audit](docs/CORE_READINESS_AUDIT.md) and
[implemented backend contract](docs/BACKEND_CONTRACT.md) before frontend work.
The backend accepts new chat/voice transcripts using owner-provisioned,
content-bound approvals and explicit provider export permissions. Existing DEV-ID
requests remain supported. Checklists can be saved as immutable versions and
selected per evaluation; see the backend contract for exact JSON and safe startup.
The compatibility default remains `2026-11-07.v3`: conditional C05 checks and full
source-ID coverage for negative critical findings. Original model decisions are
never replaced by the checker. Older v2 remains selectable. The readiness audit
records the earlier `b5702b1` snapshot.

Start the atomic backend explicitly with:

```sh
PYTHONPATH=src python3 -m cqa.web --checklist src/cqa/checklists/official-v4.json --live-call-limit 0
```

An existing server also registers v4 for explicit per-request checklist selection.
Atomic mock output requires review and carries no fabricated total. Full raw wire
output and decision origins are retained separately from the normalized projection.

## Run the local browser application

From this checkout with the existing Python/Pydantic dependency available:

```sh
PYTHONPATH=src python3 -m cqa.web --port 8765 --live-call-limit 0
```

Open [the local application](http://127.0.0.1:8765/), select a synthetic DEV
conversation and click **Evaluate**. RU/KZ/EN are supported. The application calls
the existing engine and shows eight results, reasons, N/A conditions, atomic
checks, clickable evidence, deterministic points/total and audit metadata.
The default is visibly labeled **MOCK**, a fixed wiring fixture without semantic
assessment. Result JSON is saved under ignored `outputs/app/` and can be downloaded.

**Independent human review** opens in a separate tab with blank manual forms and
its existing `team_human` JSON/CSV/resume workflow. No AI score is copied into a
human assessment. Both screens reuse the viewer's read-only transcript renderer.

The integration branch is `codex/local-mvp-integration`, in the separate worktree
`/Users/User/data-challenge-2026-integration` on the owner's Mac. The original
checkout and its unfinished viewer files remain preserved; main is unchanged.
See [local MVP setup, API and verification](docs/LOCAL_MVP.md), including the exact
steps to enable authorized OpenAI access without changing scoring code.

## Run the evaluation baseline

From the project root, use Python 3.9+ with `pydantic>=2.11,<3` (verified with
Python 3.9.6 and Pydantic 2.13.5). An optional editable install is
`python3 -m pip install -e .`; otherwise the commands below use `PYTHONPATH=src`.

```sh
PYTHONPATH=src python3 -m cqa list
PYTHONPATH=src python3 -m cqa evaluate --id p1-ru-001 --output outputs/example-001.json
PYTHONPATH=src python3 -m cqa evaluate --id p1-ru-002 --output outputs/example-002.json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
PYTHONPATH=src python3 -m cqa schema result
```

The default provider is a deterministic **mock fixture**, not a quality evaluator.
Its fixed lowest scores test wiring only; every decision requires review. Outputs
include source-grounded locators, atomic checks, facts, validation/scoring stages
and reproducibility metadata. Existing output files are preserved. CLI evaluation
files must stay under ignored `outputs/`, since they contain transcript evidence.

Use `--data data/raw/DEV_conversations.json` for the full local dataset or
`--checklist path/to/versioned-checklist.json` for a changed checklist. New criteria,
atomic questions, weights, scales, N/A rules and basic consistency implications
are configuration, not Python branches keyed to the eight initial criterion IDs.

The real OpenAI adapter uses strict structured output through the Responses API.
It requires an authorized `OPENAI_API_KEY`, an explicit `--model`, and
`--allow-external-synthetic`. Obtain credentials through secure key setup; never
paste them into chat or source files. The adapter rechecks complete record content
against the reviewed synthetic derivative before any network request. All five
real calls remain blocked by that default CLI policy; audio links are never exported.
The HTTP backend has a separate explicit, content-bound authorization policy for
new synthetic/control transcripts; no request can authorize its own data export.
An authorized existing credential has now been used for one smoke request; its
response failed validation. Current live attempts are capped at zero; see the
repair report before authorizing another request.

See [pipeline and contracts](docs/EVALUATION_ENGINE.md) and the
[implementation report](docs/IMPLEMENTATION_REPORT.md). The layered baseline
supports future verifiers and audit-preserving revisions; it does not yet implement
appeal/reviewer execution, a second LLM, or measured scoring accuracy. A browser
MVP is implemented; the full competition workflow remains incomplete.

## Start every session with filesystem discovery

1. Confirm the actual project root. Read [CLAUDE.md](CLAUDE.md),
   [PROJECT_FILE_MAP.md](PROJECT_FILE_MAP.md), [TEAM_STATUS.md](TEAM_STATUS.md),
   and local `STATUS.md` if present. The local status is intentionally not in Git.
2. Inspect relevant directories **including ignored files**. `git ls-files` and
   default `rg --files` do not inventory the whole local workspace. Use `ls -la`
   or Python `Path.iterdir/rglob` on `case/`, `data/`, `src/`, `notebooks/`,
   `outputs/` and `deliverables/`. List paths/metadata, not sensitive contents.
3. Locate and read the actual sources needed before reporting them missing.
   A file absent from GitHub may exist locally. Check the file map, expected
   paths and applicable Downloads locations before requesting materials again.
4. Run `python3 -B src/git_preflight.py`; follow [GIT_WORKFLOW.md](GIT_WORKFLOW.md)
   before synchronization. Check modifications and a successful fetch before
   claiming which version is latest. Cached refs alone do not prove freshness.

## Shared versus local-only materials

| Path | Availability and purpose |
| --- | --- |
| `case/CQA_REQUIREMENTS.md`, `case/CQA_SCORING_SPEC.md` | Tracked requirements, official clarifications, rubric and benchmark proposal |
| `case/shared/*_TEAM_SAFE.pdf` | Tracked reviewed PDF copies; visible pages retained, embedded links/actions and metadata removed |
| `data/shared/DEV_synthetic_60.json` | Tracked partial DEV derivative: 60 synthetic chats, RU=30/KZ=15/EN=15 |
| `PROJECT_FILE_MAP.md`, `TEAM_STATUS.md` | Tracked inventory and sanitized status snapshot |
| `src/git_preflight.py`, `src/prepare_shared_chats.py` | Git inspection and safe subset preparation; neither is application code |
| `data/raw/DEV_conversations.json` | LOCAL ONLY authoritative 65-record original: RU=35/KZ=15/EN=15; includes five real RU calls |
| Original PDFs directly under `case/` | LOCAL ONLY originals; student guide contains a signed API link |
| `STATUS.md`, other raw/processed data, outputs and deliverables | LOCAL ONLY; may contain restricted evidence and real-call data |
| `notebooks/`, other `src/` files | Future analysis/code, subject to file-level review |

The 60-chat file is not the full DEV dataset. It preserves chat IDs and record
content, including empty audio fields, but contains no real call records,
transcripts, audio links or related sensitive metadata. Its `DEV_SYNTHETIC_ONLY`
group label is a local derivative label, not an organizer API group ID. No
conversation-specific official Ground Truth is available for development; future
team labels must identify themselves as `team_human`.

## New teammate setup

Follow [TEAM_START_HERE.md](TEAM_START_HERE.md), which selects the integration
branch rather than default main, creates an isolated environment, upgrades old
pip, and provides exact mock/test/QA commands. Public cloning needs no invitation;
pushing in-repository branches requires accepted write access. Two write
invitations remain pending at the collaboration audit.

The detailed runtime notes here include historical baseline milestones. Use the
[current backend contract](docs/BACKEND_CONTRACT.md) and onboarding version
checkpoint before assuming an older limitation or live-call count is current.

## Local human conversation review

Build and open the offline, read-only DEV transcript viewer:

```sh
python3 -B tools/dev_review/build.py
open outputs/dev_review/index.html
```

It provides blank eight-criterion human forms and separate `team_human` JSON/CSV
downloads, with JSON resume. It uses no external dependencies or AI scoring and
does not modify the dataset or import the production evaluation engine. See
[reviewer instructions](tools/dev_review/README.md) for independent labeling,
evidence references, provenance, and save/resume behavior. Save JSON before
closing: there is no browser autosave. These labels are never official Ground Truth.

## Reproduce the shared chat subset

With the approved full original available locally:

```sh
python3 -B src/prepare_shared_chats.py --check
```

This verifies 60 unique unchanged chats, the 30/15/15 language split, no calls or
audio links, and preservation of the original. Without `--check`, it creates the
derivative only if absent or verifies an identical existing copy; differing work
is never overwritten. See the inventory for provenance and local handoff paths.

## Reproducibility, sharing and submission

Preserve originals and timestamps; record input/checklist/model/prompt versions,
filters, definitions and evidence. Reconcile transformations, independently verify
consequential numbers, and inspect actual final deliverables. [ANALYSIS.md](ANALYSIS.md)
has the full procedure. The local `STATUS.md` is the detailed evidence record;
`TEAM_STATUS.md` is a sanitized snapshot, not a competing ledger.

`.gitignore` allows only named safe files under `case/` and `data/shared/`.
Other materials/data remain excluded. Ignore rules do not untrack existing files
or prevent uploads: review the exact staged manifest and content before pushing.

The owner intentionally made this repository **PUBLIC**. Do not change its
visibility, permissions or rulesets in this workstream. Public access does not
authorize restricted inputs or new data uploads. Final submission scope and any
separate repository remain an owner decision; review content and history before
any further redistribution.

## Adaptable execution gates

Understand requirements and audit inputs first; establish a reproducible baseline
by about hours 2-5; investigate high-value accuracy/generalization issues through
about hour 13; integrate and validate by about hour 18; finish actual deliverables
and QA through hour 22; protect the last two hours for critical corrections,
submission and confirmation. Adjust to official timing. Build an end-to-end
candidate early rather than sacrificing a working submission for exploration.
