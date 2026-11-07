# First CQA Evaluation Engine — implementation report

> Historical initial-engine report (`ebcab33`). Its implementation limits and
> verification counts describe that milestone. Use [team onboarding](../TEAM_START_HERE.md)
> and the [current backend contract](BACKEND_CONTRACT.md) for present setup/behavior.

Date: 2026-11-07, Asia/Almaty. Base: `207b23f`. Feature branch:
`codex/cqa-evaluation-engine`. Main is not merged. Use live Git state for the
current commit/synchronization; this report does not claim a cached ref is fresh.

## Files

Created:

- `pyproject.toml`
- `src/cqa/__init__.py`, `src/cqa/__main__.py`
- `src/cqa/schemas.py`, `src/cqa/io.py`, `src/cqa/loader.py`
- `src/cqa/preprocessing.py`, `src/cqa/checks.py`, `src/cqa/prompt.py`
- `src/cqa/providers.py`, `src/cqa/validation.py`, `src/cqa/scoring.py`
- `src/cqa/engine.py`, `src/cqa/cli.py`
- `src/cqa/checklists/official-v1.json`
- `tests/__init__.py`, `tests/helpers.py`, `tests/test_loader.py`
- `tests/test_pipeline.py`, `tests/test_provider.py`
- `tests/test_scoring.py`, `tests/test_validation.py`
- `docs/EVALUATION_ENGINE.md`, `docs/IMPLEMENTATION_REPORT.md`

Modified: `README.md`, `PROJECT_FILE_MAP.md`, `TEAM_STATUS.md`; local ignored
`STATUS.md` records the detailed evidence. No dataset or organizer source changed.
Generated mock results/schemas/verification records remain ignored under
`outputs/cqa/`; PDF review PNGs remain ignored under `tmp/cqa-source-review/`.

## Delivered behavior and validation

The layers and stable contracts are documented in `EVALUATION_ENGINE.md`.
The pipeline has actual normalization, deterministic pre-facts/applicability
constraints, a useful pre-check, primary atomic rubric evaluation, contextual
validation, optional independent checks, exact scoring and structured audit.
The pre-check and extension tests prove behavior; they are not empty stage stubs.
New criterion IDs/questions/scales/weights/applicability work through JSON config.

Executed command:

```sh
PYTHONPATH=src python3 -B -m unittest tests.test_loader tests.test_pipeline tests.test_provider tests.test_scoring tests.test_validation -v
```

53 engine tests passed, zero final failures/skips on the owner's local workspace.
Full discovery also passed 56 tests, including three concurrently added viewer
tests outside this engine's implementation/commit scope. Engine coverage includes:

- Independent Decimal verification of all 2,592 permitted weighted-response
  combinations; every binary/discrete level and permitted N/A combination.
- N/A proportional redistribution, 04's 0/5/10/15/20 scale, 06's 0/4/7/10 scale,
  separate gross flags, exact fractions, local rounding tie and null total case.
- Wrong/missing/extra/duplicate outputs, false quotes, unknown/reversed locators,
  missing atomic answers, applicability/consistency contradictions and bot evidence.
- All 60 unchanged synthetic chats normalized and mock-evaluated across RU/KZ/EN.
  All five local voice transcripts mock-evaluated with timestamp preservation,
  no exported audio URLs and external-provider export blocked. On a fresh clone
  lacking full local DEV, only the local-voice test intentionally skips.
- Advisory/no-agent checks preserve scores; post-block preserves maker/audit;
  pre-block prevents inference; mutating extensions cannot alter pipeline state.
- Offline OpenAI HTTP payload/schema, token/provenance parsing, missing key,
  refusal/incomplete/malformed output, transport failures and export boundary.
- Arbitrary new organizer criterion and JSON serialization/schema export.

An intermediate run caught a test configuration copying the old criterion's
consistency rules while replacing its question IDs. The fixture now replaces
those rules explicitly; the validator correctly rejected the stale references.

The shared-subset integrity utility and original-source hashes are rechecked
separately. Mock DEV execution is functional coverage, not scoring accuracy.
No human benchmark IDs were selected and no reference labels were assigned.

Concurrent `tools/dev_review/`, its two test files and its documentation additions
are preserved in the working tree and excluded from the engine commit. They are
a separate workstream; this report does not claim authorship or review of them.

## Real versus mock output

No genuine LLM evaluation occurred: no usable `OPENAI_API_KEY` was present in the
process environment or project env files. The real adapter is implemented and
tested using injected offline transport; those tests are not live OpenAI calls.
No key, paid service or resource was created. Latency and usage from offline
fixtures must never be described as genuine provider performance or cost.

Two repeatable DEV examples require only a different ID:

```sh
PYTHONPATH=src python3 -m cqa evaluate --id p1-ru-001 --output outputs/example-001.json
PYTHONPATH=src python3 -m cqa evaluate --id p1-ru-002 --output outputs/example-002.json
```

Representative excerpt (both are mock fixture results, not quality judgments):

```json
{
  "status": "mock_only",
  "score": {"total_score": "0.00", "critical_violation": false},
  "run": {"provider": "mock", "model_returned": "deterministic-fixture-v1", "is_mock": true}
}
```

All eight fixture decisions carry `needs_review=true` and explicitly say no
semantic assessment occurred. Full saved files include all contracts, atomic
checks, applicability constraints, evidence locators and audit/provenance.

## Remaining work and limits

The first genuine run requires authorized API access and an explicit supported
model, followed by the synthetic-only opt-in. This is the highest-priority next
engineering step. Secure key setup is available when the owner chooses to create
or connect access. The user explicitly requested completing offline integration
when credentials are absent, so implementation was not stopped for provisioning.

Next, separately commission the proposed 12-calibration/8-holdout human benchmark
and approved factual/policy references. Accuracy has not been established against
independently reviewed labels. Quotation/ID/schema consistency does not prove
semantic truth, correct N/A reasoning or financial-product factual correctness.

Technically supported seams, not implemented experiments: criterion-specific
verifiers, independent models/disagreement findings, risk-based review/blocking,
synthetic counterfactual inputs, saved custom rubrics and audit-preserving human
revisions. No second LLM, synthetic lab, appeal executor, frontend, automatic
revision acceptance, fine-tuning, deployment or public submission was built.
