# Modular evaluation baseline and contract v1

Current core note: engine 0.6.1 compatibility mode defaults to `official-v3.json` / rubric
`2026-11-07.v3`, prompt `baseline-v4` and active model-output schema `1.1`.
Atomic checks precede the response in the actual serialized provider schema;
applicability questions precede other questions in the model input. Legacy
model-output `1.0` remains readable. Independent field diagnostics report metadata,
applicability, consistency and evidence failures together without accepting partial
decisions. Configurable evidence policies and
atomic/category consistency now close the 12 independent QA defects. Successful
results preserve original `model_evaluation`, `validated_evaluation` and exact-span
`evidence_repairs`. Rejected replies retain per-criterion diagnostics and no score.
Configured conditional binary rules now produce explicit agreement/disagreement
records, without response replacement; source coverage proofs bind all cited
scope intervals to the original ordered message manifest. Critical negative
proofs include each negative category atomic check in rubric v3.
See [current repair/live-call report](VALIDATION_REPAIR_REPORT.md). Historical
baseline behavior below remains useful context; optional formatting resolution
does not weaken direct strict validation or change any response/weight.

The Python entry point is `cqa.engine.evaluate(conversation, checklist, provider,
config=None, checks=()) -> EvaluationResult`. No frontend or database is required.
The authoritative initial scoring interpretation is `case/CQA_SCORING_SPEC.md`;
the actual original checklist and student guide were read and visually inspected.

## Functional stages

1. `loader.load_conversation(path, id)` strictly parses the organizer envelope,
   verifies counts/unique IDs and preserves all turns in original order. Source
   roles client/operator/bot/system map to customer/agent/bot/system. Unknown roles
   and unmapped context fields fail instead of being dropped or guessed. Languages
   are strings, channels chat/voice. Original timestamps are never recalculated.
2. `preprocessing.extract_facts()` computes role counts, first/last human agent
   locators and the checklist's applicability constraints. These are observable
   facts/configuration, not guessed product-policy facts or semantic N/A decisions.
3. Optional pre-checks inspect a snapshot. The included `AgentPresenceCheck` flags
   bot-only inputs for review without creating a new N/A exemption.
4. `Provider.evaluate()` receives normalized context, the complete saved checklist,
   structural facts and a versioned prompt/schema. The primary model answers each
   configured atomic question, then selects an official raw response/anchor.
   Atomic answers are explanations, never extra weighted criteria or subweights.
5. `validation.validate_evaluation()` rejects missing/duplicate/extra decisions,
   wrong types/levels, forbidden N/A, missing reasons, atomic-question omissions,
   applicability contradictions, configured consistency contradictions, unknown or
   reversed evidence locators and quotations absent from the exact source text.
   Unknown atomic answers require review. Positive operator performance requires
   an agent quote; bot statements cannot provide that evidence. Critical yes needs
   a category and agent quote; critical no needs the full inspected scope.
6. Optional post-validation checks inspect the maker's preserved decision. Findings
   can request review or block scoring; they cannot assign replacement scores.
7. `scoring.score_evaluation()` applies the official weights/scales/N/A formula
   using exact rational arithmetic. Critical flags have zero weight. No applicable
   weighted criteria yields null, never zero. Two decimal places are official;
   HALF_UP tie-breaking is explicitly a local convention pending clarification A06.
8. `EvaluationResult` retains the normalized input, complete rubric, original AI
   decision, atomic checks, exact score fraction, display contributions, findings,
   stage hashes and run metadata. Output files remain local/ignored.

The initial rubric's atomic wording and two simple implication sets are team
operationalizations of official rules, not a new official answer key. Criterion
01's missing greeting/introduction implies no; criterion 08's identified listed
violation implies yes. Both are configured in JSON, with no criterion-ID branch
in the pipeline. Semantic applicability and evidence meaning still need model or
human judgment; gates validate structural consistency, not scoring accuracy.

## Stable typed contracts

All contracts are in `src/cqa/schemas.py`, forbid unknown fields and use strict
types. Conversation/checklist/result contracts carry `schema_version="1.0"`;
new model outputs use `1.1` (the reader also accepts historical `1.0`). A breaking
change requires a new major contract version; a saved checklist change requires
a new checklist version. Never repurpose a question ID within a saved version.

| Contract | Important fields / meaning |
| --- | --- |
| `Conversation` | ID, channel, language, dataset group/hash, source-record hash, messages |
| `Message` | Stable local `m0000` ID, original message ID if supplied, zero-based source index, exact timestamp/speaker/text, normalized role |
| `Checklist` / `Criterion` | ID/version/source, binary/discrete/critical kind, weight, levels/anchors, N/A condition/rule, atomic questions and configurable consistency rules |
| `PreEvaluationFacts` | Structural extractor version, role counts, first/last agent, applicability constraints |
| `AtomicCheck` | Configured question ID, yes/no/unknown/not_applicable, rationale and evidence |
| `Decision` | Criterion ID, strict yes/no/N/A or integer response, reason, N/A reason, atomic checks, evidence, critical categories, review marker/reason |
| `Evidence` | quote with message ID/exact substring, or scope/omission with start/end IDs; every kind has an explanation |
| `OverallScore` | Two-decimal total string/null, exact rational numerator/denominator, applicable denominator weight, separate critical flag/categories, criterion contributions |
| `EvaluationResult` | Full input/rubric/maker output, facts/findings/audit, score, run provenance, revision history |
| `DecisionRevision` | Original/proposed decision, actor/source/time/reason/state; future explicit revision workflow, empty in baseline |

Optional evidence fields are explicit JSON nulls; raw responses use English
`yes`/`no`/`N/A` tokens corresponding to the official Russian answers. Booleans,
numeric strings and arbitrary intermediate levels are rejected. For N/A, the
configured atomic question must assert its exact allowed condition. The reason
and evidence must explain it; a syntactically valid reason is not proof of truth.

Evidence joins through `conversation.messages[].message_id`; source index and
timestamp resolve the original utterance even when timestamps repeat. Source
message IDs are retained separately because DEV itself supplies none. Voice
references are transcript positions/original timestamps, never invented offsets.
Signed audio links are excluded from contracts and are not fetched.

Full precision drives the total. Per-criterion `effective_weight` and
`earned_points` strings show 12 decimal places for display only; do not sum them
to reconstruct a final score. Use the recorded exact total fraction or scorer.

Export machine-readable JSON Schemas directly from these types:

```sh
PYTHONPATH=src python3 -m cqa schema conversation
PYTHONPATH=src python3 -m cqa schema checklist
PYTHONPATH=src python3 -m cqa schema model
PYTHONPATH=src python3 -m cqa schema result
```

## Extending the baseline

Edit a copy of the JSON checklist, change its version and pass `--checklist`.
Provide new criteria, atomic questions, scales/anchors and N/A applicability
rules there. N/A rules reference a configured question and its yes/no trigger.
Consistency rules express `question_id + when_answer -> permitted_responses`.
They reject contradictions; they never convert an invalid result to a score.
Critical categories remain the three enumerated official categories in contract
v1; expanding that taxonomy requires an explicit contract update.

Providers implement the small `Provider` protocol in `providers.py`, returning a
`ProviderReply` containing raw structured evaluation and model/usage provenance.
The mock deliberately always selects the lowest applicable level and marks all
questions unknown/review. It assesses no content, holds no DEV answer lookup,
and is always labeled `mock_only`. Its scores/critical flags have no semantic use.

An extension implements `name`, `version`, `phase` (`pre_evaluation` or
`post_validation`) and `run(CheckInput) -> CheckOutcome`. The input contains a deep
snapshot of conversation/checklist/facts and, after validation, the maker result.
Output contains only info/review/block findings with criterion IDs and explicit
explanations. Unknown criterion IDs or component identity mismatches are rejected.

```python
class ConsultationReview:
    name, version, phase = "consultation-review", "1", "post_validation"

    def run(self, context):
        # Inspect configured criteria/evidence here; return findings, not scores.
        return CheckOutcome(check_name=self.name, check_version=self.version,
                            phase=self.phase, findings=[])

result = evaluate(conversation, checklist, provider, config,
                  checks=[ConsultationReview()])
```

This illustrates the interface; no consultation verifier is shipped or claimed.
Actual extension behavior (advisory, blocking, attempted mutation and arbitrary
new criterion compatibility) is exercised by the pipeline tests. Review findings
change result status, never the maker decision or deterministic total. A block
raises `CheckBlocked`, retaining check outcomes/audit and the original maker if
one exists; it produces no score. A pre-block prevents the provider call entirely.

Future second-model verifiers must independently obey data/credential permission
rules. Applying human/checker revisions is not implemented: the typed history is
reserved to retain both original and changed decisions, with explicit approval
state and recalculation in a later workflow. The baseline never silently mutates
the original decision or presents a checker proposal as accepted.

## Real adapter and reproducibility

`OpenAIProvider` implements the [Responses API structured-output contract](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
with `text.format` JSON Schema, `strict=true`, and `store=false`. It uses a fixed
HTTPS endpoint, rejects redirects and performs no automatic retries. Credentials
remain in memory/environment; request bodies contain no key. API errors/refusals,
incomplete output and invalid structured results fail explicitly, with raw
provider bodies/private values withheld from CLI error messages. A structured
result still needs factual and semantic review.

The default/CLI policy requires explicit run opt-in AND exact content membership in the
reviewed 60-chat derivative with its pinned file hash. Changing a channel/ID does
not bypass the check. Full-DEV synthetic records pass the same content comparison;
all five real calls and altered/unreviewed records fail before transport. This
default policy remains restricted to that authorized dataset. The HTTP backend can
explicitly supply `InputPolicy`/`ExportPolicy` for new transcripts. These require
owner-provisioned, expiring exact-content grants and separate provider export
opt-in; unapproved private data is denied before transport. They do not authorize
audio retrieval/export or certify organizer consent. See the internal
[backend contract](BACKEND_CONTRACT.md) for manifests, supplied conversation JSON
and saved checklist version selection. No new model call was made in this pass.

Each result records provider, requested/returned model, engine/Python/Pydantic
versions, checklist snapshot/version/hash, input ID/source hashes, full prompt
hash/version, config, UTC start time, total/provider latency, response ID, token
counts when supplied, and each executed check's version/findings. No temperature
or seed is silently assumed. Identical inputs/configs recreate the same prompt,
but external model output is not guaranteed deterministic. No official metric,
pricing claim, product-policy knowledge base or accuracy benchmark is invented.


## Explicit atomic-first decision path

Rubric official-v4.json selects atomic-v2 / wire schema1.2. The existing evaluate
pipeline validates typed observations and fact evidence before materializing
unambiguous decisions; the original provider output is separately retained.
`atomic.py` is this input stage, using the existing validators, scope proof and
scorer. It is not a second evaluator. C01/C02/C03/C05/C08 have configured derivation;
all applicability/N/A is backend-owned. C04/C06 remain discrete model judgments,
and applicable C07 remains discretionary. Per-criterion review states prevent one
bad criterion from hiding the others or producing a fabricated total. Legacy
outputs remain legacy; no silent migration/repaired historical accepted scores.
See BACKEND_CONTRACT.md for source provenance and the explicit v4 selector.
