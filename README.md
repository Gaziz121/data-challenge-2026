# Freedom Broker CQA — evidence-first conversation quality evaluation

Evaluates broker customer-service conversations (RU / KZ / EN chats and supplied voice
transcripts) against the organizer's eight-criterion checklist: per-criterion raw level,
rationale and source-grounded evidence, exact weighted scoring with N/A redistribution,
a separate critical flag, versioned checklists, appeals with reviewer decisions, and the
official `results.json` export.

Authoritative branch: **`main`** (includes `integration/final-submission` and the frontend; see [TEAM_START_HERE.md](TEAM_START_HERE.md)).
Requirements: [case/CQA_REQUIREMENTS.md](case/CQA_REQUIREMENTS.md),
[case/CQA_SCORING_SPEC.md](case/CQA_SCORING_SPEC.md), team-safe PDFs in [case/shared/](case/shared/).

## Quick start (no API key, no paid call)

Python 3.9+ with `pydantic>=2.11,<3` (`python3 -m pip install "pydantic==2.13.5"`), Node 18+ for UI tests.

```sh
git clone https://github.com/Gaziz121/data-challenge-2026.git && cd data-challenge-2026
CQA_REVIEWER_KEY=demo-reviewer-key PYTHONPATH=src python3 -m cqa.web --port 8765 \
  --checklist src/cqa/checklists/official-v7.json --live-call-limit 0
```

Open http://127.0.0.1:8765/ and follow the [five-minute demo](docs/DEMO.md). The fastest
complete path: conversation `p1-ru-001`, checklist `2026-11-07.v5`, provider **Replay**,
Evaluate → appeal C07 → reviewer (key `demo-reviewer-key`) changes it → revised total.
The interface is in Russian. Without an OpenAI key it preselects exactly that pair
(«Повтор записанного ответа ИИ»), so the first click on «Оценить» gives a score; a yellow hint
explains combinations that cannot score (e.g. the Mock fixture with atomic checklists v4–v7).
Jury defense materials (Russian script, runbook, backup screenshots) are in [docs/defense/](docs/defense/);
on Windows double-click `tools\demo\demo-start.cmd` (or `demo-reset.cmd` for a clean demo).

### Windows (PowerShell)

```powershell
git clone -c core.autocrlf=false https://github.com/Gaziz121/data-challenge-2026.git
cd data-challenge-2026
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip "pydantic==2.13.5"
$env:PYTHONUTF8 = "1"; $env:PYTHONPATH = "src"; $env:CQA_REVIEWER_KEY = "demo-reviewer-key"
.\.venv\Scripts\python.exe -m cqa.web --port 8765 --checklist src/cqa/checklists/official-v7.json --live-call-limit 0
```

`core.autocrlf=false` matters: with Windows line endings the reviewed dataset hash no longer
matches and the server refuses to start. Tests also need `$env:PYTHONUTF8 = "1"`; on Windows
four subtests that assert POSIX file mode `0o600` fail (`test_control_backend.py:102`).
For a real AI evaluation (paid, about USD 0.02 each) add an ignored file with one line
`OPENAI_API_KEY=...` and start with
`--env-file <that file> --model gpt-5.4-mini-2026-03-17 --allow-external-synthetic --live-call-limit 10`,
then choose «OpenAI — настоящая оценка ИИ».

Tests (all offline; the same suite runs in GitHub Actions, `.github/workflows/offline-tests.yml`):

```sh
PYTHONPATH=src python3 -B -m unittest discover -t . -s tests   # production
PYTHONPATH=src python3 -B -m unittest discover -t . -s qa      # independent QA + Accuracy Lab
node tests/test_web_ui.cjs && node tests/test_dev_review.cjs   # frontend + human viewer
PYTHONPATH=src python3 -B -m cqa_results.rehearsal --out outputs/rehearsal/$(date +%H%M%S)
```

## What works (verified offline)

| Capability | Where |
| --- | --- |
| Evaluate DEV chats, supplied new RU/KZ/EN chats and voice transcripts (owner-approved input only) | `src/cqa/engine.py`, `web.py`, `access.py` |
| Atomic-first evaluation: the model reports facts with exact quotes/scopes; the backend validates evidence, derives rule-based decisions, computes N/A and exact scores | `atomic.py`, `validation.py`, `scoring.py` |
| Invalid model output is never scored or silently corrected; optional bounded one-call repair | `repair.py`, batch `--repair-authorization` |
| Versioned, immutable checklists; edit/save/select in the UI (wording, weights, scales, anchors, N/A text, new criteria via JSON) | `checklists.py`, UI checklist editor |
| Evaluation history, appeals, reviewer confirm/change, original vs revised total (stored result never modified) | `appeals.py`, `/api/evaluations/...` |
| Official `results.json` exporter, independent strict validator, public-URL verification | `src/cqa_results/` |
| PROD intake (fetch exact bytes, envelope check, bounded re-wrap) and full offline final-hour rehearsal | `cqa_results.envelope`, `cqa_results.rehearsal` |
| Separate human-labelling viewer (`team_human`, never Ground Truth) | `tools/dev_review/`, `/human-review/` |

API: [docs/BACKEND_CONTRACT.md](docs/BACKEND_CONTRACT.md). Submission: [docs/RESULTS_SUBMISSION_RUNBOOK.md](docs/RESULTS_SUBMISSION_RUNBOOK.md).
Rationale: [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md), reliability evidence:
[docs/RELIABILITY_REPORT.md](docs/RELIABILITY_REPORT.md), evaluator comparison plan:
[docs/EVALUATION_COMPARISON_PLAN.md](docs/EVALUATION_COMPARISON_PLAN.md), backlog: [docs/EXPERIMENT_BACKLOG.md](docs/EXPERIMENT_BACKLOG.md).

## Evaluator, model and cost — what is and is not established

- FROZEN provisional production configuration (`tools/production.env`): checklist `official-v7.json` + prompt
  `atomic-v5` + opt-in review evidence gate + OpenAI `gpt-5.4-mini-2026-03-17` (Responses API, strict structured
  output). v6 clarified C07 wording; v7 additionally clarifies C01 (see the runbook §0 for the selection record).
- Live evidence: 7 genuine single calls, all on synthetic `p1-ru-001`. Only the atomic-v5 + v5 reply is a
  trustworthy structural acceptance (total 100.00); an earlier atomic-v3 acceptance had a grammar-forced
  C06 and is not trusted. That reply credits a farewell as an offer of help under C07; the official text
  requires a summary or offer of help **and** a farewell, so a reviewer would likely score C07 = no (92.31).
  v6 clarifies exactly that wording. **v6 gate (3 owner-authorized calls, RU/KZ/EN synthetic):** 2/3
  structurally accepted (p1-ru-001 100.00; p1-kz-013 92.31 with a correct critical flag for an off-company paid
  offer); p1-en-013 rejected on evidence/coverage rules. The clarified wording did NOT change C07 on p1-ru-001
  (still credits the farewell) — a known open semantic bias, not tuned further on DEV items.
- Measured cost: ~12.6k input / ~2.6–2.9k output tokens, **USD 0.013–0.023 per call** (DEV-65 ≈ USD 1–2;
  PROD-10 ≈ USD 0.1–0.3 including optional repair calls); latency ≈ 14 s per call.
- **Semantic accuracy against official Ground Truth is unknown.** No official labels exist for development;
  mock, replay and fixture outputs prove wiring only, never quality.

## Shared versus local-only materials

| Path | Availability and purpose |
| --- | --- |
| `case/CQA_REQUIREMENTS.md`, `case/CQA_SCORING_SPEC.md`, `case/shared/*_TEAM_SAFE.pdf` | Tracked requirements, clarifications and reviewed PDF copies (embedded links removed) |
| `data/shared/DEV_synthetic_60.json` | Tracked: 60 synthetic DEV chats (RU 30 / KZ 15 / EN 15); not the full DEV set |
| `docs/demo/fictional_new_conversations.json` | Tracked: three invented conversations for the supplied-input demo |
| `data/raw/DEV_conversations.json` | LOCAL ONLY authoritative 65 records incl. five real RU calls; never committed |
| Original organizer PDFs under `case/`, results appendix | LOCAL ONLY (the student guide contains a signed API link) |
| `STATUS.md`, `outputs/`, `restricted/`, `.env` | LOCAL ONLY evidence ledger, generated results, owner approvals, credentials |
| `results/dev/results.json`, `results/prod/results.json` | Official submission files — created only by the exporter from genuine runs |

## Start every session with filesystem discovery

1. Confirm the project root; read [CLAUDE.md](CLAUDE.md), [PROJECT_FILE_MAP.md](PROJECT_FILE_MAP.md),
   [TEAM_STATUS.md](TEAM_STATUS.md) and local `STATUS.md` if present.
2. Inspect ignored directories too (`ls -la case data outputs restricted`); `git ls-files` is not an inventory.
3. Run `python3 -B src/git_preflight.py` and follow [GIT_WORKFLOW.md](GIT_WORKFLOW.md). No force pushes.

The repository is intentionally PUBLIC (owner decision). Never commit keys, `.env`, real transcripts,
audio, organizer originals, signed links, approvals or reviewer exports. `.gitignore` excludes them,
but review the staged manifest before every push. Human labels from `tools/dev_review/` are
`team_human`, never official Ground Truth ([viewer README](tools/dev_review/README.md)).
