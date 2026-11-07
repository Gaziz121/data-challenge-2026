# Freedom Broker CQA Hackathon — private development workspace

**[Start here: team onboarding, setup, ownership and contribution workflow](TEAM_START_HERE.md).**
This is the single onboarding entry point for our four-person team. It explains
which branch to clone, exact safe run/test commands, separate QA/Lab setup and
what must be provisioned outside Git. The default `main` is still the materials
baseline; current app development is on `codex/local-mvp-integration`.

## Current shared implementation

Engine 0.5.0 / prompt `baseline-v4` / rubric `2026-11-07.v3` is available on
integration, including the loopback backend, browser MVP, immutable checklist
versions and independent Human Review Viewer source. New supplied chat/voice
input requires owner-provisioned content approvals; external export has separate
permissions. Original model decisions and rejected outputs are preserved.

Claude's independent QA and offline Accuracy Lab are pushed on
`feature/cqa-independent-qa` at `3ff9c76`. That branch's engine is older; follow
the onboarding guide to test its `qa/` against the pinned integration engine.
Two genuine responses are recorded as rejected; no accepted live quality total
or measured semantic accuracy is established. Appeals/reviewer execution,
organizer control fetch, complete checklist UX and production deployment remain
incomplete. See [current shared status](TEAM_STATUS.md).

## Documentation map

| Need | Read |
| --- | --- |
| First setup, commands, four workstreams, Git/PR workflow | [TEAM_START_HERE.md](TEAM_START_HERE.md) |
| Official constraints and exact scoring interpretation | [Requirements](case/CQA_REQUIREMENTS.md), [scoring spec](case/CQA_SCORING_SPEC.md), [team-safe PDFs](case/shared/) |
| Frontend requests/responses, errors, input/export permissions | [Current backend contract](docs/BACKEND_CONTRACT.md) |
| Core pipeline and evidence/scoring semantics | [Evaluation engine](docs/EVALUATION_ENGINE.md) |
| Independent human labeling, JSON/CSV save and resume | [Viewer instructions](tools/dev_review/README.md) |
| Available files, local-only materials and source authority | [Project file map](PROJECT_FILE_MAP.md), [CLAUDE.md](CLAUDE.md) |
| Git safety and publication boundaries | [GIT_WORKFLOW.md](GIT_WORKFLOW.md) |
| Historical implementation and repair evidence | [Initial engine](docs/IMPLEMENTATION_REPORT.md), [local MVP](docs/LOCAL_MVP.md), [readiness audit](docs/CORE_READINESS_AUDIT.md), [repair history](docs/VALIDATION_REPAIR_REPORT.md) |

The clone includes only the reviewed **60 synthetic chats** and team-safe PDFs.
The original **65-record DEV**, five real RU calls, original PDFs, credentials,
local evidence and reviewer outputs require a separate permitted handoff and
must stay outside Git. Do not treat absent-from-Git as absent-from-disk.
Keep this repository private; final public submission needs a separately reviewed
sanitized repository without private history.
