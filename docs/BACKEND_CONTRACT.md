# Implemented backend contract for the frontend teammate

Source: `src/cqa/web.py`, `schemas.py`, `loader.py`, `engine.py`, `scoring.py`.
Engine 0.3.0 / prompt `baseline-v3`. This describes implemented source after
backend restart, not a promised future API. No frontend code changed in this task.

## Versions and request boundary

- Conversation, checklist and evaluation-result wrappers: `schema_version="1.0"`.
- Active provider output: `schema_version="1.1"`, format name
  `cqa_evaluation_v1_1`; historical output `1.0` still parses.
- Default checklist ID `freedom-cqa-initial`, version `2026-11-07.v2`.
- Strict JSON types; extra request/contract fields rejected. Missing, null, numeric
  zero, `"no"` and `"N/A"` have distinct meanings.

| HTTP route | Implemented behavior |
| --- | --- |
| `GET /api/config` | Default provider, model, key-presence boolean (never key), external opt-in, remaining per-process live-call count/null, complete active checklist |
| `GET /api/conversations` | Array of approved DEV `{conversation_id, channel, language}` metadata |
| `GET /api/conversations/{id}` | Normalized Conversation below; only approved cached DEV IDs |
| `POST /api/evaluations` | ID + optional provider/model -> new EvaluationResult, or explicit error |
| `GET /api/diagnostics/{id}` | Retained rejected output with model/run/input/checklist/criterion issues; only named local synthetic diagnostics |

There is no conversation-upload endpoint, checklist CRUD/version-selection
endpoint, result-history GET, appeal/override endpoint or organizer control fetch.
Do not send a conversation or checklist object in POST `/api/evaluations`:
those extra fields return 422. The current local app is single-process,
loopback-only, unauthenticated, and has no cross-origin CORS API for a separately
hosted frontend. Same-origin integration or a later reviewed adapter is needed.

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

Checklist input is Python/startup configuration, not a POST field:

```sh
PYTHONPATH=src python3 -m cqa.web --checklist path/to/saved-checklist.json --live-call-limit 0
```

`Checklist`: ID/version/source, rounding/local note, criteria. Each criterion has
ID/title/instructions, binary/discrete/critical kind, integer weight, levels and
anchors, nullable N/A condition/rule, atomic questions, consistency implications
and evidence policy. A rule binds a question ID to a yes/no N/A trigger; question
references must match the definitions. Categories remain the official three.
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

Only `conversation_id` is required. Provider defaults to mock; model defaults to
the server setting when needed. OpenAI needs explicit supported model, authorized
server credentials, export opt-in and remaining call budget; new input is still
blocked by exact approved-membership policy. No automatic retry or mock fallback.

Successful HTTP 200 contains these actual keys, all unmodified from the engine:

`schema_version`, `evaluation_id`, `status`, `conversation`, `checklist`,
`model_evaluation`, `validated_evaluation`, `evidence_repairs`, `score`, `run`,
`facts`, `check_outcomes`, `audit`, `revision_history`.

Minimal **excerpt**, not a complete response or schema-valid fixture:

```json
{"schema_version":"1.0","status":"mock_only","model_evaluation":{"schema_version":"1.1"},"score":{"total_score":"0.00","applicable_weight":100,"critical_violation":false},"run":{"provider":"mock","is_mock":true}}
```

The complete audit-generated example is local-only at
`outputs/readiness-audit/full-mock-result.json`; this is a fixed fixture, never
a quality judgment. Produce a full fresh HTTP result with the mock request above.

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
Result status is mock_only, needs_review or structurally_valid. These are not
accuracy certifications; review results still carry provisional raw decisions
and a calculated total. A critical flag does not currently auto-escalate status.

## Re-evaluation and errors

Repeating POST with the same ID generates a new evaluation ID and retains a
separate result; it does not overwrite a human label. To change checklist version,
reconfigure/restart the current server (or pass another Checklist to the Python
core). There is no HTTP `checklist_version` selector or deduplicating result cache.

| HTTP status | Meaning |
| --- | --- |
| 403 | Wrong Host or missing/foreign Origin |
| 404 | Unknown route/conversation/diagnostic |
| 409 | Another evaluation is running |
| 413 / 415 | Body not 1..4096 bytes / Content-Type is not JSON |
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
