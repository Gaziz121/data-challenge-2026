# Project file map - inspect disk as well as Git

Updated: 2026-11-07. Paths are relative to the current project root. This inventory
is tracked; it does not promise that LOCAL ONLY files exist on every teammate's
machine. Inspect the filesystem including ignored paths before declaring absence.
`git ls-files` and default ignore-aware search are incomplete material inventories.

| Expected path | Status | Purpose, authority and how to read |
| --- | --- | --- |
| `README.md`, `CLAUDE.md`, this file | GIT TRACKED | Setup, mandatory discovery and material routing; read each session |
| `TEAM_STATUS.md` | GIT TRACKED | Sanitized shared snapshot; read each session; not the detailed evidence ledger |
| `STATUS.md` | LOCAL ONLY | Owner's detailed status/evidence; read if available, never upload wholesale |
| `case/CQA_REQUIREMENTS.md` | GIT TRACKED | Internal interpretation of official requirements/clarifications; includes unexecuted benchmark plan |
| `case/CQA_SCORING_SPEC.md` | GIT TRACKED | Source-grounded initial rubric and unresolved questions; not an official answer key |
| `case/CQA_Hackathon_Student_Guide_v3 1.pdf` | LOCAL ONLY | Authoritative unchanged organizer guide; inspect PDF text, visible pages and embedded actions locally; contains signed API access |
| `case/CQA_Chat_Quality_Checklist 1.pdf` | LOCAL ONLY | Authoritative unchanged criterion/scale/N/A source; read actual PDF |
| `case/Data 2 (1) 1.pdf` | LOCAL ONLY | Authoritative unchanged supplementary source; image-heavy, needs visual review; background, not Ground Truth |
| `case/shared/CQA_Hackathon_Student_Guide_TEAM_SAFE.pdf` | GIT TRACKED (GENERATED derivative) | Guide visible pages preserved; signed GET link and embedded actions/metadata removed; not usable for API access |
| `case/shared/CQA_Chat_Quality_Checklist_TEAM_SAFE.pdf` | GIT TRACKED (GENERATED derivative) | Reviewed checklist copy; original remains separate and authoritative |
| `case/shared/Data_2_TEAM_SAFE.pdf` | GIT TRACKED (GENERATED derivative) | Reviewed background copy; embedded actions/metadata removed |
| `data/raw/DEV_conversations.json` | LOCAL ONLY | Authoritative complete DEV: 65 IDs, RU=35/KZ=15/EN=15, 60 synthetic chats plus five real RU calls; includes signed audio URLs |
| `data/shared/DEV_synthetic_60.json` | GIT TRACKED (GENERATED derivative) | Partial DEV: 60 unchanged synthetic chats, RU=30/KZ=15/EN=15; no real call records/content/links; never treat as full DEV |
| `src/prepare_shared_chats.py` | GIT TRACKED | Reproduce/check the approved subset from the local full original; no network or quality scoring |
| `src/git_preflight.py`, `GIT_WORKFLOW.md` | GIT TRACKED | Inspect Git layers and synchronize safely; not a filesystem material inventory |
| `pyproject.toml`, `src/cqa/*.py` | IMPLEMENTATION / PRIVATE source | Modular baseline: strict v1 contracts, normalization, deterministic facts, atomic LLM evaluation, gates, extension checks, scoring, audit and CLI |
| `src/cqa/checklists/official-v1.json` | IMPLEMENTATION / PRIVATE configuration | Source-grounded eight-criterion initial rubric, atomic questions, configurable N/A rules and consistency implications; not conversation labels |
| `tests/*.py` | IMPLEMENTATION / PRIVATE source | Offline contract/scoring/provider/pipeline tests; hand-authored fixtures and DEV integrity/mock runs, never official labels |
| `docs/EVALUATION_ENGINE.md`, `docs/IMPLEMENTATION_REPORT.md` | IMPLEMENTATION / PRIVATE documentation | Stable teammate interfaces, extension behavior, run instructions, file manifest, executed validation and limitations |
| `outputs/cqa/` | GENERATED / LOCAL ONLY | Mock run JSON, schemas and verification summary; transcript-bearing files are never staged |
| `tools/dev_review/` | GIT TRACKED / PRIVATE source on integration branch | Preserved standalone human viewer/builder/rubric plus shared read-only `transcript.js`; no engine imports or AI scores |
| `tests/test_dev_review.py`, `tests/test_dev_review.cjs` | GIT TRACKED / PRIVATE source on integration branch | Dataset-preservation and human-label export/resume checks; fictional scoring fixtures only |
| `outputs/dev_review/` | GENERATED / LOCAL ONLY | Offline HTML snapshot, QA artifacts and separate `team_human` downloads; never official Ground Truth |
| `src/cqa/web.py`, `web/index.html`, `web/app.js`, `web/app.css` | IMPLEMENTATION / PRIVATE source | Loopback HTTP adapter to existing engine, conversation selector, transcript/evidence/results UI; no new scorer |
| `tests/test_web.py`, `tests/test_web_ui.cjs` | IMPLEMENTATION / PRIVATE source | Backend HTTP/N/A/provider/export-boundary checks and DOM rendering/identity regressions; no live API calls |
| `docs/LOCAL_MVP.md` | IMPLEMENTATION / PRIVATE documentation | Startup, secure model readiness, endpoint contract, preservation/commit scope and actual verification |
| `outputs/app/` | GENERATED / LOCAL ONLY | Saved evaluation JSON and browser QA, separate from manual human exports |
| `ANALYSIS.md` | GIT TRACKED | Reverse engineering, deep analysis, evidence and final-file checks |
| `src/`, `notebooks/` | GIT TRACKED files only after review | Development files available on disk may be uncommitted; inspect local paths and Git status |
| `data/processed/`, other `data/`, `outputs/`, `deliverables/`, `tmp/`, caches | GENERATED / LOCAL ONLY by default | Derived evidence, artifacts and temporary review files; may still be sensitive; inspect filenames before contents |
| `.env*`, credential files, private keys, restricted materials | LOCAL ONLY | Secrets/restricted inputs; do not print or stage; use approved owner handoff |

## Authority and missing-file decisions

- Original organizer PDFs plus official clarifications are authoritative for
  requirements. Shared copies preserve visible pages; internal specs interpret
  sources. Report conflicts instead of silently redefining the official rule.
  Clarifications O1-O7 were relayed as verified by the user on November 7, 2026;
  no original message export was supplied. Do not invent independent verification.
- Original full DEV is authoritative for data. The 60-chat subset is deliberately
  partial, with the local group label `DEV_SYNTHETIC_ONLY`. Missing calls in the
  shared subset do not mean missing calls on the owner's Mac.
- Local working files and GitHub commits are separate states; neither is
  automatically newest. Inspect modifications and refresh approved refs before
  claiming remote freshness. See `GIT_WORKFLOW.md`.
- Check this map AND actual relevant directories, including ignored contents,
  before claiming a file absent. If the map is stale, fix it and report the
  discrepancy. Update this map whenever material paths or sharing status change.
- A fresh clone needs a separate organizer-permitted handoff of the full JSON,
  original PDFs, API access and any needed local evidence. Ask the integration
  owner after checking disk; use the paths above. Originals also remain in the
  owner's Downloads, but teammates must not assume that directory is shared.

## Provenance and sharing boundary

The original source hashes are recorded in the requirements/scoring documents.
The shared subset preserves each chat record exactly; its SHA256 is
`836b1cd80a70f4fb901f3d7a8aacfc227ecc523a8a4d29631ff91bf88a399c17`.
Source completeness is 65; shared completeness is 60, not 65.

Team-safe PDF hashes: guide
`29b3d3f8735f45f3f5e4fa673af4e02cd2ab9199c67d1a381fa7697607da9eac`;
checklist `ba212335b908c3e0802738e37bfc6c8a352cc3d79ee00637dc2ab07bdcb16560`;
supplement `c45f733de706c0e4793b1221d6d8e9d425c898063b712da2088c8a3dcb5d2c12`.
Safe copies remove annotations/actions/source metadata, retain page content, and
were inspected for embedded credentials. Originals are never overwritten.

The user authorized reviewed safe materials for this PRIVATE team repository.
No explicit prohibition on this private-team sharing was found in supplied
organizer materials. This is not public redistribution permission. Keep real
calls, signed URLs, full DEV, local evidence and credentials outside Git. Future
public submission must be separately sanitized, without private Git history.
