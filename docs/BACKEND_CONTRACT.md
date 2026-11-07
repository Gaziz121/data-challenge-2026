# Implemented backend contract for the frontend teammate

> **Current additions (integration/final-submission) are in the last section,
> "Final integration: history, appeals, replay, checklist v6".** Earlier sections remain accurate
> for the routes they describe; where they say "no result-history GET / appeal endpoint", that
> limitation is now resolved.

Source: `src/cqa/web.py`, `schemas.py`, `loader.py`, `engine.py`, `scoring.py`.
Engine 0.5.0 / prompt `baseline-v4`. This describes implemented source after
backend restart, not a promised future API. No frontend code changed in this task.

## Versions and request boundary

- Conversation, checklist and evaluation-result wrappers: `schema_version="1.0"`.
- Active provider output: `schema_version="1.1"`, format name
  `cqa_evaluation_v1_1`; historical output `1.0` still parses.
- Default checklist ID `freedom-cqa-initial`, version `2026-11-07.v3`; v2 remains selectable.
- Strict JSON types; extra request/contract fields rejected. Missing, null, numeric
  zero, `"no"` and `"N/A"` have distinct meanings.

| HTTP route | Implemented behavior |
| --- | --- |
| `GET /api/config` | Default provider, model, key-presence boolean (never key), external opt-in, remaining per-process live-call count/null, complete active checklist |
| `GET /api/conversations` | Array of approved DEV `{conversation_id, channel, language}` metadata |
| `GET /api/conversations/{id}` | Normalized Conversation below; only approved cached DEV IDs |
| `POST /api/evaluations` | Exactly one DEV ID or authorized supplied conversation, optional checklist reference/provider/model -> new EvaluationResult |
| `GET /api/checklists` | Registered checklist IDs/versions/content SHA256 |
| `GET /api/checklists/{sha256}` | Full registered Checklist by content hash |
| `POST /api/checklists` | Validate/save a full Checklist; immutable ID/version, returns 201 reference/hash |
| `GET /api/diagnostics/{id}` | Retained rejected output; exact approved DEV content or currently authorized supplied input only |

The local app remains single-process, loopback-only and same-origin; it is not an
internet service. POST requires `Origin: http://127.0.0.1:<port>` (or matching
localhost Host). No CORS, remote login, result-history GET, appeal endpoint or
organizer control fetch is implemented. No frontend code changed.

## Content authorization for supplied input

New input requires a matching owner-provisioned **local** manifest, even for mock.
Request bodies cannot grant approval or set the data class. Unknown/private input
returns 403 before provider construction, call-budget reservation or result storage.
The owner must verify the actual data-use permission before adding a grant:

- `synthetic_test`: reviewed fictional test content.
- `organizer_control`: content whose local processing is organizer-authorized.
- `organizer_dev`: provided real DEV transcripts, distinct from control data.
- Unapproved private content: no grant, denied. It cannot be promoted by a request.

Save the `conversation` object below in an ignored local file (for example
`restricted/new-input.json`), then fingerprint it without exporting its contents:

```sh
PYTHONPATH=src python3 -m cqa.access restricted/new-input.json
```

The fingerprint binds the normalized messages, source IDs/order/timestamps, group,
channel/language and raw-record hash. Only the dataset-file/envelope byte hash is
excluded, so equivalent re-imports work. The raw-record hash also binds the audio
field; audio URLs are never fetched or included in normalized/model output.

For the exact fictional example below, a local-only approval manifest is:

```json
{"schema_version":"1.0","grants":[{"conversation_sha256":"63bb6b7329d08ded8d9a9e997b41c36b4058443053f0a3bfc7048e31297974e2","data_class":"synthetic_test","authorization_reference":"owner-approved-fictional-example","external_providers":[],"expires_at":"2030-01-01T00:00:00Z"}]}
```

Store approvals outside Git, e.g. `restricted/input-approvals.json`. Use a suitable
expiry and a short nonsecret approval reference, never a signed access URL. The
manifest is an owner's permission record, not independently verified organizer
consent. It is snapshotted at startup: restart to replace/revoke grants; expiry is
checked on every evaluation, provider export and diagnostic read.

```sh
PYTHONPATH=src python3 -m cqa.web --port 8765 --live-call-limit 0 \
  --authorization-manifest restricted/input-approvals.json
```

External export additionally requires `external_providers:["openai"]` on that
exact grant, `--allow-external-authorized`, an authorized key, explicit model and
remaining budget. None is enabled by the example. The original DEV-ID path keeps
its exact-content check and separate `--allow-external-synthetic` opt-in. The
OpenAI adapter defaults to the original gate unless explicitly constructed with
an input policy, and rechecks authorization before transport. No paid calls or
credential loading occurred in this implementation pass.

## Input shapes: Python ingress versus HTTP

Python `load_conversation(path,id)` reads the **known DEV** envelope:

```json
{"error":"","isSuccess":true,"data":{"dataset_group_id":"LOCAL_TEST","total_records":1,"records":[{"conversation_id":"new-001","channel":"agent chat","language":"EN","transcript":[{"timestamp":"00:00","speaker":"client","text":"Where is Help?"},{"timestamp":"00:01","speaker":"operator","text":"Hello, I am Alex. Open Help. Goodbye."}],"audio_url":null}]}}
```

This fictional example is valid for local ingestion/mock evaluation, **not an
accepted HTTP upload or an authorized external export**. It is not an organizer
control-API schema. Official control endpoint/group/access and payload guarantees
are still required. `normalize_record(record, group, dataset_hash)` also accepts
a single known-shape record; `evaluate(Conversation, Checklist, Provider, config)`
is the programmatic core entry point.

Normalized Conversation fields:

| Field | Type / meaning |
| --- | --- |
| `schema_version`, `conversation_id`, `channel`, `language` | `1.0`, nonempty ID, `chat`/`voice`, nonempty source language string |
| `dataset_group_id`, `dataset_sha256`, `source_record_sha256` | Source group, 64-hex original-file hash, canonical raw-record hash |
| `messages[]` | Nonempty ordered array; each source index retained |
| `message_id`, `source_message_id`, `source_index` | Engine-local `m0000`, original string/int/null, zero-based position |
| `timestamp`, `source_speaker`, `role`, `text` | Exact timestamp/source speaker/text; normalized customer/agent/bot/system |

Only raw client/operator/bot/system speakers are mapped. Audio URLs are not
exported in normalized/results contracts; voice timestamps are not player offsets.
Evidence IDs join within this conversation, so use conversation ID + local message
ID together; local `m0000` repeats in another conversation.

A default checklist can still be selected at startup:

```sh
PYTHONPATH=src python3 -m cqa.web --checklist path/to/saved-checklist.json --live-call-limit 0
```

`Checklist`: ID/version/source, rounding/local note, criteria. Each criterion has
ID/title/instructions, binary/discrete/critical kind, integer weight, levels and
anchors, nullable N/A condition/rule, atomic questions, consistency implications
and evidence policy. A rule binds a question ID to a yes/no N/A trigger; question
references must match the definitions. Categories remain the official three.
POST `/api/checklists` accepts the full existing Checklist contract, saves it under
ignored `outputs/app/checklists/`, and returns `{checklist_id, version, sha256}`
with HTTP 201. Reposting identical content is safe; different content under the
same ID/version returns 409. Saved snapshots have identity and content checksums
and survive restart. There is no update/delete route: save a new version instead.
Evaluation resolves a private checklist snapshot before invoking the engine.

Full schemas can be generated from the actual code:

```sh
PYTHONPATH=src python3 -m cqa schema conversation
PYTHONPATH=src python3 -m cqa schema checklist
PYTHONPATH=src python3 -m cqa schema model
PYTHONPATH=src python3 -m cqa schema result
```

The `model` CLI schema is the backward-compatible reader (1.0/1.1).
`prompt.build_request(...)[0]["schema"]` is the actual generation schema,
constrained to 1.1, with atomic checks before response. Its checklist input moves
the applicability question first without editing the saved rubric.

## Evaluation request and response

Exact minimal request (safe mock; no credentials in body):

```http
POST /api/evaluations HTTP/1.1
Host: 127.0.0.1:8765
Origin: http://127.0.0.1:8765
Content-Type: application/json
Content-Length: 62

{"conversation_id":"p1-ru-001","provider":"mock","model":null}
```

That DEV-ID request remains compatible. Alternatively supply our internal
conversation contract and an optional saved checklist reference:

```json
{"conversation":{"dataset_group_id":"INTERNAL_EXAMPLE","record":{"conversation_id":"new-en-001","channel":"agent chat","language":"EN","audio_url":null,"transcript":[{"message_id":"turn-1","timestamp":"00:00","speaker":"client","text":"Where is Help?"},{"message_id":"turn-2","timestamp":"00:01","speaker":"operator","text":"Hello, I am Alex. Open Help. Goodbye."}]}},"checklist":{"checklist_id":"freedom-cqa-initial","version":"2026-11-07.v2"},"provider":"mock"}
```

Exactly one `conversation_id` or `conversation` is required. `checklist` selects an
existing ID/version; omission uses the startup default. Provider defaults to mock,
model to the server setting. `record` uses the known DEV chat/voice structure:
`channel:"agent chat"` or `"voice call"`; roles client/operator/bot/system;
nonempty timestamp/text, optional source `message_id`. RU/KZ/EN use the same path.
Extra/unmapped fields and unknown roles fail closed. New input is returned in the
result, not added to the DEV selector or human-label workflow.

No automatic paid retry or mock fallback. This is our **internal** request shape,
not a claim about organizer control payloads. A future organizer adapter must
verify access/data-use permission, map the actual envelope/roles, retain source
provenance, and provision explicit content approvals.

Successful HTTP 200 contains these actual keys, all unmodified from the engine:

`schema_version`, `evaluation_id`, `status`, `conversation`, `checklist`,
`model_evaluation`, `validated_evaluation`, `evidence_repairs`, `score`, `run`,
`facts`, `check_outcomes`, `audit`, `revision_history`, `decision_rule_checks`,
`coverage_proofs` (the last two default to empty when reading older results).

Minimal **excerpt**, not a complete response or schema-valid fixture:

```json
{"schema_version":"1.0","status":"mock_only","model_evaluation":{"schema_version":"1.1"},"score":{"total_score":"0.00","applicable_weight":100,"critical_violation":false},"run":{"provider":"mock","is_mock":true}}
```

The complete verified supplied-input example is local-only at
`outputs/control-backend-verification/documented-response.json`, with its request
beside it. It is a fixed mock fixture, never a quality judgment. Produce a fresh
HTTP result using the request and owner-approved local manifest above.

Each criterion decision contains all of:

| Field | Values / semantics |
| --- | --- |
| `criterion_id` | Exactly one decision per active checklist criterion |
| `atomic_checks[]` | Configured question ID, yes/no/unknown/not_applicable answer, short rationale, evidence array; emitted before response |
| `response` | Strict yes/no/N/A token or permitted integer raw level, never a weighted score |
| `rationale`, `na_reason` | Nonempty rationale; N/A reason **null unless response=N/A**, then nonempty configured-condition explanation |
| `evidence[]` | Quote or scope/omission references described below |
| `violation_categories` | Empty for normal criteria; critical mapped yes categories must agree exactly with atomic answers |
| `needs_review`, `review_reason` | Boolean and required reason when true; otherwise reason=null; unknown atomic answers require review |

Exact evidence-object example over the fictional normalized input above:

```json
{"kind":"quote","message_id":"m0001","quote":"Hello, I am Alex.","start_message_id":null,"end_message_id":null,"explanation":"The first human reply greets and introduces the operator."}
```

Scope/omission uses `start_message_id` and `end_message_id` (inclusive), with
message_id/quote=null and a nonempty explanation. Quotes must resolve to source
text; role and first-reply policies are enforced. `model_evaluation` preserves
the original reply. Use `validated_evaluation` for source-resolved evidence when
present; every formatting repair retains original/source quote, message ID and
character offsets with Python's half-open `[source_start:source_end]` convention.
No response or score is repaired.

`score.criteria[]` provides criterion ID, applicability, base weight and
12-decimal display strings for effective weight/earned points. `score.total_score`
is a two-decimal string or null when no weighted criteria apply. Exact rational
numerator/denominator and applicable-weight denominator are also recorded. N/A
excludes only permitted inapplicable criteria; `"no"` keeps its weight at zero
earned points. The critical flag/categories are separate, with no automatic
penalty/cap. UI must display these backend values, not recalculate from rounded
contributions. HALF_UP tie-breaking is a recorded local convention.

`run` includes engine/Python/Pydantic versions, provider/model, mock flag, UTC
time, latencies, response ID, optional usage, prompt/checklist hashes and config.
`run.input_authorization` records the data class, source policy, exact conversation
fingerprint, permission and owner reference. An authorization event is also added
to the audit. Historical/direct-core results may have this optional field null.
Result status is mock_only, needs_review or structurally_valid. These are not
accuracy certifications; review results still carry provisional raw decisions
and a calculated total. A critical flag does not currently auto-escalate status.

The optional binary `decision_rule` specifies `all_of` question IDs and a nullable
conditional `{trigger_question_id, required_when, requirement_question_id}` plus
its source. All references must exist and be distinct. There are no rule defaults
keyed to criterion IDs. Unknown/missing facts do not produce a derived answer.
An untriggered obligation must be atomic `not_applicable`, never criterion N/A.
`decision_rule_checks` retain the model response, derived response, status and
issues. Disagreement blocks scoring; the original reply is never overwritten.

For critical `response=no`, `coverage_proofs` recompute the union of valid cited
scope intervals over exact source-message IDs. Missing IDs or invalid boundaries
fail. With `negative_coverage=decision_and_atomic` (v3), each category answered no
needs full coverage as well. Proofs include ordered required/covered/missing IDs,
evidence paths and conversation/message hashes. Quotes alone, repeated excerpts,
or claims in rationale cannot fill gaps. No scope is auto-expanded. These prove
locator coverage only; semantic absence and actual model attention remain unproven.
Both records also appear in retained rejection diagnostics, without a score.

## Re-evaluation and errors

Repeating POST with the same ID generates a new evaluation ID and retains a
separate result; it does not overwrite a human label. To change the checklist, save a new full Checklist with POST `/api/checklists`,
then pass `"checklist":{"checklist_id":"...","version":"..."}` in the next
evaluation request. No restart is needed. Results retain full checklist snapshots,
version/content hash and distinct evaluation IDs; earlier results remain intact.
There is no deduplicating result cache.

| HTTP status | Meaning |
| --- | --- |
| 403 | Wrong Host/Origin; supplied input missing/expired approval or provider export denied |
| 404 | Unknown route/conversation/diagnostic |
| 409 | Another evaluation is running, or checklist ID/version already has different content |
| 413 / 415 | Evaluation body outside 1..1048576 bytes, checklist outside 1..262144 bytes, invalid framing / Content-Type is not JSON |
| 422 | Invalid request/config, quality-check block or rejected model output |
| 502 | Provider transport/refusal/incomplete-output failure |
| 500 | Local/processing failure with private details withheld |

Exact example error for unknown conversation:

```json
{"error":"Conversation not found in synthetic DEV"}
```

Rejected model output returns 422 with `error`, `diagnostic_id`, `issues[]`.
Each issue identifies criterion ID or null, location when available and message;
multiple independent failures can belong to one criterion. GET its diagnostic
to inspect original model output, per-criterion validation states, transcript,
checklist, run metadata and audit. **It has no accepted score.** Other 422 cases
may contain only `error`, so the frontend must not assume a diagnostic ID exists.

Neither the diagnostic JSON nor accepted result is `team_human`. The independent
manual-label workflow remains separate. Appeals/revision fields are reserved
contracts; no accepted-override workflow is implemented.


## Atomic-first contract (engine0.6.1; explicit rubric v4)

The compatibility default remains v3. Select the registered `2026-11-07.v4` in
`POST /api/evaluations` using the same checklist reference shape:

```json
{"conversation_id":"p1-ru-001","provider":"mock","checklist":{"checklist_id":"freedom-cqa-initial","version":"2026-11-07.v4"}}
```

V4 declares `decision_path=atomic_first`; C01/C02/C03/C05/C08 declare
`output_source=atomic`. Their model-facing judgment field is schema-constrained
to null. Applicability is backend-owned for all criteria, including discretionary
ones. C04/C06 retain official raw levels; C07's applicable answer remains model
judgment because its Boolean grouping is still an acknowledged interpretation.
No N/A or na_reason is requested from the model. No unsolicited final answer is
silently overridden: it creates a conflict and blocks a total.

Wire schema1.2 has `criteria[]`: criterion_id, atomic_checks (question_id, answer,
rationale, evidence, events), and judgment. Judgment is null for derived/N/A
criteria; otherwise response/rationale/evidence/categories/review fields. Events
have kind protected_request/protected_action/verification, source message ID and
exact quote. Identification policy binds need/verification question IDs, source
roles and chronology; need=no requires full-dialogue coverage and no contradictory
protected event. Verified=yes requires eligible confirmation before every cited
actual protected action, with source-order ties unresolved. Other facts retain
configured quote roles, first-agent locators and negative coverage requirements.

Results include `decision_path`, `original_provider_output` and
`criterion_reviews`. In atomic mode **model_evaluation is the normalized decision
projection**, not raw LLM final answers; use original_provider_output for the exact
wire judgments and event observations. validated_evaluation is the gated projection.
Review records identify origin, response, rule source, atomic answers and original
judgment. States: accepted_derived, accepted_model, needs_review, invalid_facts,
schema_invalid, conflict. Any unresolved/invalid criterion yields 422 with full
original output and per-criterion states, plus individually validated criteria;
no partial/redistributed/provisional total is manufactured. No automatic retry.
Old schemas, exports, strict evidence gates and checklist versions remain intact.
Event classification and factual advice still need semantic calibration; exact
citations/order/coverage do not independently establish their truth.


The atomic-v2 compiler explicitly emits output_source=model instead of omitting
that storage default, and includes a per-question output plan with exact scope
templates for mandatory full-dialogue evidence. Legacy checklist hashes remain
unchanged. The one authorized atomic-v1 live run at5d256ac was rejected for missing
C03/C05 negative scopes and C07's applicable model judgment. V2's compiler changes
are offline-verified only; the original rejected response is never repaired.

## Engine 0.7.0 additions (backward compatible, opt-in)

- `atomic-v2` stays the default atomic prompt; its request bytes are unchanged
  (p1-ru-001 sha256 `9f5bcb65…cdad`). `EvaluationConfig(prompt_version="atomic-v5")`
  selects the same instructions/payload with a schema that compiles validator
  structure into the strict output grammar (full-dialogue scope where required,
  judgment present iff applicable, identification/conditional couplings).
  Scores are never range-restricted: `atomic-v3` did that and its live call
  produced a grammar-forced C06=0; v3 remains only to reproduce that record.
  v5 also fixes exact atomic/criterion item counts; v4 (open upper bound) emitted
  a duplicate 04.q1 live and remains only to reproduce that record.
  Validators are unchanged and still decide.
- Every result gains an additive `repair_attempts` key (empty list by default);
  rejection diagnostics gain the same key. Frontend code needs no change.
- `evaluate(..., repair=RepairPolicy(authorization=...))` enables at most ONE
  bounded repair call. Default is disabled; not exposed over HTTP. Only criteria
  in invalid_facts/schema_invalid/conflict are resent with their diagnostics;
  original answers are schema-pinned to themselves or `unknown`, an original
  discretionary response is pinned. The primary reply stays in
  `original_provider_output`; the repair output, merged reply, pins, answer
  changes, usage and latency are in `repair_attempts`. A result that used a
  repair is `needs_review` (non-mock). Usage in `run.usage` is the primary call only.


## Final integration: history, appeals, replay, checklist v6

Source: `src/cqa/web.py`, `appeals.py`, `replay.py`, `scoring.py`. All routes are loopback-only; POST
still requires same-origin `Origin` and `Content-Type: application/json`.

| HTTP route | Behavior |
| --- | --- |
| `GET /api/evaluations[?conversation_id=ID]` | Newest-first rows for saved results and rejected diagnostics visible to this server (approved DEV or currently authorized supplied input): `kind` result/rejected, `evaluation_id` (diagnostic ID for rejected), conversation/language/channel, `status`, `total_score`, `critical_violation`, provider, model, `is_mock`, `started_at`, checklist ID/version, `issues`, `appeals_open`, `appeals_revised` |
| `GET /api/evaluations/{id}` | The stored EvaluationResult, byte-for-byte content as saved (never modified by appeals) |
| `GET /api/evaluations/{id}/appeals` | Revised view: `original_score`, `revised_score` (null until a reviewer changes something), `original_responses`, `revised_responses`, `applied[]`, `appeals[]` |
| `POST /api/evaluations/{id}/appeals` | `{criterion_id, explanation, submitted_by, requested_response?}` → 201 `{appeal, view}`. One open appeal per criterion (409); requested value must be on the criterion's scale (422). Rejected diagnostics cannot be appealed (404: no accepted score) |
| `POST /api/appeals/{appeal_id}/decision` | Header `X-CQA-Reviewer-Key`; body `{reviewer, outcome: "confirm"|"change", reason, new_response?}` → 200 `{appeal, view}`. Wrong/missing key 403; reviewer equal to appellant 422; change must differ from the original and be on scale; decided appeals are final (409) — submit a new appeal to revisit |

Appeal record (`outputs/app/appeals/<appeal_id>.json`, schema `cqa-appeal/1`): evaluation/conversation/checklist
identity, `criterion_id`, `original_response`, `requested_response`, `explanation`, `submitted_by/at`, `state`
(open/upheld/revised), `decision {outcome, reviewer, reason, final_response, decided_at}` and an append-only
`history[]`. Recalculation re-applies the latest revised decision per criterion to the original raw responses and
calls `scoring.score_responses` — the same function `score_evaluation` uses after validation — so N/A
redistribution, HALF_UP rounding and the separate critical flag are identical. A revised critical "no" clears
violation categories. The reviewer key comes from `CQA_REVIEWER_KEY` or is generated and printed at server
start; it is a local demo control, not an identity system.

`provider: "replay"` re-runs the full engine validation on a RECORDED genuine reply. It is available only when
conversation, checklist version and prompt bytes match the recording (today: `p1-ru-001`, checklist
`2026-11-07.v5`, `atomic-v5`, model `gpt-5.4-mini-2026-03-17`); otherwise 422. Replays are `is_mock: true`
(status `mock_only`), so the official exporter refuses them.

Checklists `2026-11-07.v2`–`v6` are always registered. For `atomic_first` checklists the CLI server uses
`--atomic-prompt-version` (default `atomic-v5`; the `Application` class default remains the engine's atomic-v2).
`official-v6.json` = v5 with only the C07 instructions and 07.q2 wording clarified. Checklist save errors
return 422 with `error` and `fields`.

`GET /api/config` additionally returns `atomic_prompt_version`, `replay_recordings[]` and
`reviewer_key_required`. Batch-runner additions (`cqa_results.batch`): real providers require explicit
`--checklist` and `--prompt-version`; `--repair-authorization REF` opts into one bounded repair call per
rejected atomic conversation and is recorded in `run.json` (resume refuses a change).
