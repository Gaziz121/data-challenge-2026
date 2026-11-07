# Freedom Broker CQA Hackathon - private development workspace

Accuracy, reproducibility and required end-to-end functions take priority over
cosmetics. This is a shared development workspace; no CQA application or external
model evaluation has been built. Read the [requirements](case/CQA_REQUIREMENTS.md)
and [scoring specification](case/CQA_SCORING_SPEC.md).

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

1. Obtain private repository access and run `gh repo clone Gaziz121/data-challenge-2026`
   into your chosen local directory. Do not clone over the owner's existing work.
   Confirm `pwd` and `git status`, then follow the discovery steps above.
2. Read the inventory, team status, requirements, scoring spec and team-safe PDFs.
   The shared chat JSON is available immediately. Python 3.9+ is sufficient for
   the two stdlib preparation/checking utilities. No application runtime or
   dependencies have been installed or prescribed by this setup.
3. For full DEV/voice/API access, first inspect local expected paths. If absent,
   obtain the original JSON and PDFs from the integration owner through an
   organizer-permitted handoff. Store the full JSON at
   `data/raw/DEV_conversations.json` and PDFs at the inventory paths; never stage
   them. The owner also retains originals in Downloads. A clone does not fetch
   these files, real calls, local `STATUS.md`, or signed API access.
4. Create only needed local folders: `data/raw`, `data/processed`, `notebooks`,
   `outputs`, `deliverables`. Empty folders are not stored by Git. Keep credentials
   in ignored local configuration, never source files, commit text or URLs.
5. Assign one owner per notebook/workstream and one integration owner. Use short
   branches and review for consequential shared changes. This setup does not
   itself authorize external AI/API calls or application implementation.

The original guide's GET button is intentionally inactive in the shared PDF.
Obtain approved API access separately; do not copy signed links into Git, issues,
chat logs or documentation. A teammate lacking a LOCAL ONLY file is not evidence
that the material never existed.

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

Keep this development repository **PRIVATE**. Final submission requires a separate
sanitized PUBLIC repository after a later approval. Do not change this repository's
visibility or copy its private Git history into the future public repository.

## Adaptable execution gates

Understand requirements and audit inputs first; establish a reproducible baseline
by about hours 2-5; investigate high-value accuracy/generalization issues through
about hour 13; integrate and validate by about hour 18; finish actual deliverables
and QA through hour 22; protect the last two hours for critical corrections,
submission and confirmation. Adjust to official timing. Build an end-to-end
candidate early rather than sacrificing a working submission for exploration.
