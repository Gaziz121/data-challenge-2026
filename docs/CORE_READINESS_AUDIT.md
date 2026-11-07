# Evaluation-core readiness audit

> Historical engine 0.3.0 readiness audit. Later integration commits implement
> authorized supplied-input ingestion and immutable checklist save/select; the
> unseen-input limitations below belong to the audited snapshot. Use
> [team onboarding](../TEAM_START_HERE.md) and the
> [current backend contract](BACKEND_CONTRACT.md) for present behavior.

2026-11-07, Asia/Almaty. Core fixes: `9ee9605` on
`codex/local-mvp-integration`, from `f84d364`. Workstream B changed no production
code. No paid calls, credential loading, UI changes or rule-derivation system.
Independent QA stayed at `10647cf`, with its source/tests unchanged.

## Workstream A: verified corrections

- **R1:** diagnostics parse independent fields, then collect metadata,
  applicability, consistency, role/locator and citation failures together. A bad
  N/A reason or nested citation no longer hides an applicable-response conflict.
  Partial diagnostic projections are never scored. Runtime acceptance still
  requires a complete strict `Decision` and all configured gates.
- **R3:** actual provider JSON has `atomic_checks` before `response` in both
  `properties` and `required`. Model input puts the configured applicability
  question first, including an edited rubric whose saved array used another
  order. Saved checklist content/hash is not changed. Prompt hashes now preserve
  schema-key ordering, since generation uses that order. See the
  [official key-ordering guidance](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
- **R4:** model-facing `na_reason` explicitly requires JSON null for every
  applicable answer, and a nonempty condition explanation only for N/A. The
  prompt repeats this distinction; strict acceptance remains enforced.
- **Versions:** engine `0.3.0`, prompt `baseline-v3`, active model output `1.1` /
  provider format `cqa_evaluation_v1_1`. The reader also accepts historical model
  output `1.0`. Conversation/checklist/result wrappers remain `1.0`; official
  rubric remains `2026-11-07.v2`. No weights, anchors, scorer or export gate changed.

| Executed suite | Run | Passed | Failed/errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| Application/backend `tests/` | 83 | 82 | 0 | 1 |
| Original Claude QA: adversarial + harness + proposed config | 41 | 41 | 0 | 0 |
| New Claude replay/RCA `qa.test_rca_a94e48f7` | 15 | 15 | 0 | 0 |
| JavaScript manual export/resume suite | 1 suite | Pass | 0 | 0 |
| JavaScript existing rendering suite | 1 suite | Pass | 0 | 0 |

The expected skip is the full-DEV voice test: the original 65-record file exists
in the original checkout, but is intentionally absent from this worktree. Before
the fix, the new 15-test suite reproduced exactly three failures: masked C02
applicability, schema order and missing N/A description. It now passes without
editing independent tests or the saved replay. The old genuine output remains
rejected without a score. No new real inference or accuracy measurement occurred.

Commands from the integration root and QA root respectively:

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -q
node tests/test_dev_review.cjs
node tests/test_web_ui.cjs
# In ../data-challenge-2026-independent-qa:
PYTHONPATH=../data-challenge-2026-integration/src python3 -B -m unittest qa.test_adversarial_gates qa.test_harness qa.test_proposed_config_fix -q
PYTHONPATH=../data-challenge-2026-integration/src python3 -B -m unittest qa.test_rca_a94e48f7 -q
```

## B1. Unseen-conversation readiness

**The core supports new local input; the deployed DEV path does not yet support
new real-provider input.** Do not describe the existing web demo as control-ready.

| Component | Actual readiness | Evidence |
| --- | --- | --- |
| Raw normalization | New IDs/groups accepted in known DEV shape, with strict role/channel/field handling; no original-60 lookup | `loader.normalize_record`, `read_dataset`; loader tests; audit new-ID probe |
| Roles/context | client/operator/bot/system -> customer/agent/bot/system; exact order/text/timestamps/source IDs retained | `loader.py`; RU/KZ/EN tests |
| Schema variation | Empty turns, unknown speaker aliases, unknown context fields/channels fail closed; language is only a nonempty string | `schemas.py`, `loader.py`; QA characterization tests |
| IDs/hashes inside core | No allowed-ID prefix or dataset-hash allowlist in `evaluate`; loader computes source hashes, direct callers supply dataset provenance | `loader.py`, `engine.evaluate`; new-ID serialization probe |
| Model/provider substitution | Small provider protocol; one primary invocation with versioned rubric/schema; mock accepts new input | `providers.Provider`, `engine.evaluate`; offline provider tests |
| OpenAI export | **Blocked for every new ID/content outside approved derivative**, even with run opt-in and an authorized key | `require_approved_synthetic`; audit provider transport called zero times |
| HTTP import/evaluation | Lists/loads/evaluates only cached approved DEV IDs; no upload/import endpoint | `web.Application.ids`, `.conversation`, `EvaluationRequest`; HTTP tests |
| Evidence/results | References resolve within arbitrary normalized conversations; strict gates and result JSON round-trip work locally | `validation.py`, `evidence.py`, `EvaluationResult`; new-ID probe and existing tests |
| Organizer control fetch | Not implemented; actual control endpoint/group/access/release/format remain a dependency | `case/CQA_REQUIREMENTS.md` remaining decisions; no control client in runtime |

The exact 60-ID membership, pinned shared-file hash and application ID cache are
development-specific policy, not an organizer requirement that inputs be those
60 chats. Authorized export, no secret/audio leakage, known role mapping and
grounded evidence remain necessary protections. Supporting control data needs an
explicit reviewed input/export policy, not deletion of the safeguards or a fake
synthetic label. The known DEV envelope is documentation for DEV, not a fabricated
control-API guarantee. Detailed organizer policy/product facts remain incomplete.
Export enforcement currently lives in the OpenAI adapter, not in a universal
pipeline authorizer; any replacement provider must preserve the authorization
boundary independently.

## B2. Dynamic checklists: tested scope

Audit probes used copies in memory and mock/scripted fixtures only. They did not
save edited official rubrics, produce human labels, alter source data or contact
a provider. Production-source hashes were equal before and after the audit.

| Change | Python core | HTTP app / limits | Verification |
| --- | --- | --- | --- |
| Add criterion | Yes; nine results after adding a new ID | Only process-wide saved checklist; no CRUD | Existing new-criterion test + nine-criterion probe |
| Change weights | Yes, integer 0..10000; formula normalizes applicable weights | Fractions not accepted; no browser update route | Existing scoring tests + 90.00 -> 75.00 fixture after weight 10 -> 30 |
| Change atomic questions | Yes, with unique IDs and valid rule references | No automatic rubric-to-question compiler | Existing coverage + renamed-question and applicability-first probes/tests |
| Change N/A condition/trigger | Yes: condition plus configured question and yes/no trigger | Semantic truth still model/human judgment; no free-form Boolean condition language | Existing QA N/A paths + new condition/ID/trigger probe, denominator 85 |
| Change discrete scale | Yes for sorted unique zero-based integers with anchors and updated consistency rules | Nonzero-based/fractional scales rejected; answer kinds fixed | Probe `[0,2,6]` accepted; `[1..5]` and `[0,0.5,1]` rejected |
| Change critical categories | Existing three can be selected/mapped via config | **New category names rejected** by contract enum; critical weight must be zero | Two-category subset probe; new taxonomy rejection + QA C07 |
| Re-evaluate same ID/new version | Yes; new evaluation ID, checklist snapshot/hash and prompt hash | Same POST can repeat, but changing checklist requires process reconfiguration/restart; no per-request version selector | Probe preserves old 90.00 result and produces distinct 75.00 result/version |

Explicit version naming is caller-managed, not a database-enforced immutable
registry. No hot reload, version-selection endpoint or checklist editor is
implemented. Acceptance of a valid configuration is not evidence that a new
criterion is evaluated accurately. The probe scores above are calculation
fixtures, not predictions or Ground Truth. Full artifacts are ignored under
`outputs/readiness-audit/`; the frontend contract is [here](BACKEND_CONTRACT.md).

## B4. Requested Gemini/Socrates concept inventory

This classifies the requested concepts from code, not from presumed research
recommendations. No separate Gemini report was supplied/read for this audit.

| Concept | Classification | Actual implementation / boundary |
| --- | --- | --- |
| Atomic checklist compilation | **Partial** | Hand-authored `Criterion.questions` + generic applicability-first serialization in `prompt.build_request`; no compiler deriving atomic questions from an arbitrary edited criterion |
| Decision rules | **Partial in production** | Configurable implications/applicability/category constraints reject contradictions in `validation.py`; no full response derivation. `qa/decision_rules.py` is an independent QA reference checker on another branch, not imported into runtime |
| Evidence validation | **Implemented** | Exact IDs/quotes/scopes, allowed roles/first operator, punctuation gate, optional traceable formatting resolution, retained diagnostics; semantic support/product truth remains unverified |
| Structured verification | **Partial** | Executed pre-facts, agent-presence check and deterministic post-validation; versioned advisory/review/block hook tested with snapshots. No production criterion verifier/second LLM |
| Maker/Checker | **Not implemented as independent inference** | One provider call. Checker hooks and audit/original-decision retention are foundations, not an independent Maker/Checker system |
| Counterfactual testing | **Partial, QA only** | Separate `qa/harness.py`, `apply_edits`, hand-authored scenarios and counterfactual pairs; tests run offline, expected labels proposed/unreviewed. No production Synthetic Accuracy Lab or measured real-model agreement |
| Dynamic checklists | **Partial end to end** | Typed saved JSON + generic scorer/provider input and tested mutations; missing per-request import/version selection/editor and unrestricted scale/category support |

`DecisionRevision` is a contract; accepted appeals/overrides and recalculation
workflow are not executed. Findings cannot rewrite responses. There is no
multi-model disagreement or risk-based routing service. These were not added.

## Three highest-priority blockers

1. **Unseen authorized input path:** organizer control access/schema plus HTTP
   ingestion and a reviewed provider-export policy for those inputs. Today a
   genuinely new control conversation cannot reach the OpenAI adapter.
2. **Demonstrated evaluation reliability:** no accepted genuine evaluation or
   independent accuracy benchmark. The new ordering/descriptions are regression-
   tested, not live-model validated; product/identity/confidentiality references,
   semantic calibration and authorized future experiments remain necessary.
3. **Editable checklist delivery:** generic Python configuration is verified,
   but frontend-facing save/version/apply endpoints and broader scale/category
   decisions are missing. The frontend teammate needs the documented implemented
   contract, not assumed endpoints or an unimplemented checklist compiler.

No competition-ready claim is made. No UI, full deterministic decision-rule
engine, new export permission or additional model call was implemented here.
