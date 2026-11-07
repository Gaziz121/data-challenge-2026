# Experiment backlog and synthetic-scenario contributions

**Proposals, not executed experiments.** Publication baseline: engine `6481390`
(0.6.1; v3 compatibility default, v4 atomic opt-in); QA/Lab
`3ff9c76`. No new conversations or labels were generated for this documentation.
Use [onboarding](../TEAM_START_HERE.md#4-tests-and-reproducibility) for pinned-engine
QA setup, [architecture decisions](ARCHITECTURE_DECISIONS.md) for current limits,
and [Lab instructions][lab] for artifact ingestion/comparison commands.

## Run contract before spending or tuning

A owns engine/prompt changes; D owns independent references/splits and Lab review.
First review Lab compatibility with v3 conditional rules/per-atomic coverage and
v4 wire 1.2: `model_evaluation` is a normalized projection in atomic mode; raw
provider output is `original_provider_output`. Existing Lab tests/default-mode
demos do not independently validate that path or its review-origin fields. Freeze a
small permitted input set, checklist, labels and split before comparing changes.
The [20-case DEV plan](../case/CQA_REQUIREMENTS.md#4-proposed-lightweight-human-reviewed-dev-benchmark)
is still a proposal; five-call coverage requires separately provisioned real DEV.

Every run records engine/QA commits, dataset and per-record hashes, checklist
version/hash, prompt/schema/model/settings, split/label versions and reviewers,
authorization reference, every accepted/rejected artifact, usage and latency.
Store transcript-bearing artifacts under ignored `outputs/`. Live trials require
explicit data/export permission and a capped owner-approved budget; nothing in
this backlog authorizes calls. Offline replays check failures, not model accuracy.

Compare the same cells in baseline and candidate; change one factor per trial.
Report `fixed/regressed/still_correct/still_wrong`, valid outputs / attempted
conversations, rejected counts, unresolved/disputed exclusions, and support by
criterion/language. Never drop rejections to improve the denominator. Repeat paired
live runs at least twice if authorized to assess variability; record every attempt,
with no automatic paid retries. Predeclare the adoption rule and cost ceiling.
Suggested internal gate: more fixed than regressed cells, no new invariant failure,
no loss of valid-output coverage and no new labeled C08 misses. Small samples are
diagnostic; this is not the unknown official accuracy metric or proof of significance.

## Five prioritized trials

All are pending; priorities reflect dependencies, not official judging weights.

| Priority / owner | Question and controlled comparison | Measurement / decision evidence |
| --- | --- | --- |
| **E1 — criterion-specific semantic accuracy (A+D)** | Establish reviewed reference cells and a baseline before optimizing. Inspect C03 identity, C04 factual completeness, C05 conditional empathy and C08 critical errors first; retain reporting for all eight criteria. Test one criterion's wording/evidence instruction at a time, with approved policy sources for factual judgments. | Exact raw-response match by criterion; N/A confusion; C08 misses/false alarms with positive support; source-support audit; total MAE only where all weighted labels are resolved. Save independent human rationale and exclusions. This enables the later trials. |
| **E2 — atomic-first evaluation (A+D)** | Compatibility v3 already emits atomics before response; opt-in v4 derives selected responses from facts. On a future isolated experiment branch, compare one prompt/schema-order ablation while holding checklist, gates, model and inputs fixed. Version/hash both request formats. Do not combine this with a new rubric or full rule-derived scoring. | Applicability/atomic/response contradiction counts per attempt, rejection rate, exact match and usage/latency. Existing serialization tests prove order, not its benefit. Historical replies with different prompts/rubrics cannot isolate this effect. |
| **E3 — RU/KZ/EN robustness (A+D, language reviewers)** | Compare baseline/candidate within each language using the same reviewed cases. Add only a few missing failure modes; separately review any meaning-preserving language variants. Keep variants of one source in the same split. | Per-language exact match and valid-output coverage, N/A/C08 confusion, evidence fidelity and reviewed error categories. Report small KZ support explicitly; do not infer voice robustness or equal language difficulty from chat results. |
| **E4 — adversarial counterfactuals (D+A)** | Use existing minimal edits before proposing new ones: remove introduction/farewell, alter verification/disclosure order, or challenge role attribution/in-transcript instructions. Compare each allowed base/variant pair on its target criterion; leave unrelated content unchanged. | Paired expected response flips, monotonicity violations, collateral changes in untargeted criteria, evidence validity and rejection counts. A pair with rejected output is a validity failure, not a successful semantic flip. Keep reviewed expected relations separate from ambiguous proposals. |
| **E5 — targeted Maker/Checker (A+D; C for authorization)** | After E1, trial a checker only on predeclared risky C03/C04/C08 or unknown/review cases, versus maker alone on identical inputs. Have the checker first assess source/checklist/approved facts without seeing the maker answer, then compare findings. Save proposals separately; never auto-apply them. | Detection recall on human-confirmed maker errors, finding precision, false alarms/correct-answer change proposals, residual error rate, routed fraction, added calls/tokens/latency. Adoption requires a reviewed benefit within budget. Current hooks allow findings; rejected-output checking needs a separate planned path because post-validation hooks do not run on rejected replies. |

Use calibration for iteration. D authorizes the designated holdout check only
after the candidate and acceptance rule are fixed, using `--holdout-confirm`.
Record exposure: once a holdout result or its labels influence a change, it is no
longer an untouched validation set. Do not tune on organizer control transcripts.
The current splitter groups counterfactuals by source, not arbitrary translations;
language variants need an explicit reviewed family assignment before evaluation.

## Existing collections: reuse before adding

Counts below were calculated from committed files at the baseline above.

| Collection / location | Provenance and proper use |
| --- | --- |
| [Shared DEV](../data/shared/DEV_synthetic_60.json) | 60 unchanged organizer-supplied synthetic chats, RU=30/KZ=15/EN=15, 882 messages. Preserve this derivative; it is not a team-generated expansion or an answer key. Full local DEV has these 60 plus five real RU calls, not 65 synthetic conversations. |
| [QA scenario library][scenarios] | 19 hand-authored AI-QA scenarios: EN=8/RU=7/KZ=4; four minimal counterfactual edit specifications over reviewed synthetic DEV. Together 25 unique conversation IDs; the harness emits 27 entries because shared bases repeat. Do not count those entries as independent conversations. |
| [Label registry][registry] and [frozen split][split] | 34 expected rows: 30 `proposed_unreviewed`, four `ambiguous`; origin `team_qa_synthetic`, never official GT. Split: 13 calibration / 12 holdout conversation IDs; bases and variants stay grouped. These are QA fixtures, separate from the proposed human DEV benchmark. |
| [QA fixtures][fixtures], [application fixtures](../tests/helpers.py) and [backend test fixtures](../tests/test_control_backend.py) | Small fictional structural/adversarial inputs and scripted outputs. Useful for reproducible gates, not a calibrated semantic corpus. |
| [Lab demo plans][demo] and saved replays | Two scripted plans over seven calibration cases demonstrate comparison mechanics; they do not add new reference conversations. [QA replay][replay] and [integration replay](../tests/fixtures/live_c379231.json) preserve historical synthetic model failures, not human labels. Generated run artifacts remain ignored. |

## How to propose a small scenario addition

1. **Check overlap first.** On a branch from `feature/cqa-independent-qa`, inspect
   the existing library, failure modes and registry. Propose the smallest missing
   case or metamorphic pair with a unique ID and a criterion-level hypothesis.
   Do not duplicate/rewrite DEV or generate a bulk corpus.
2. **Record provenance in the PR.** For each ID record author/date, manual versus
   AI generation (model/prompt version if used), language/channel, approved source
   identity/hash for derivatives, intended failure mode, checklist version and
   exact criterion/spec reference. Record reviewer and uncertainty separately.
   Current scenario JSON has no general author/model provenance schema; PR metadata
   is the proposed convention, not a claimed runtime field. Keep sensitive details
   in an ignored owner-held provenance record with only a nonsecret reference.
3. **Use the existing shapes.** A scenario has `id`, `failure_mode`, `language`,
   `turns` (speaker/text pairs) and `expect`. Each expected criterion has `accept`,
   `lock`, `why`. Use permitted source roles and response types. Counterfactuals
   have a unique ID, source `conversation_id`, canonical raw-record
   `source_record_sha256` (`cqa.io.digest(record)`), `edits` with zero-based `index`,
   `find`, `replace`, and `base_expect`/`expect`. The [harness][harness] deep-copies
   sources and requires each find to occur exactly once; never edit the source JSON.
4. **Submit labels as proposals.** Explain the permitted anchor/N/A condition and
   evidence; request a language-competent independent reviewer. Keep origin
   `team_qa_synthetic` and registry tier `proposed_unreviewed`; `lock: true` only
   enables comparison against a single proposal, not human verification. For
   ambiguity use `lock: false`, tier `ambiguous` and applicable open-item IDs.
   Preserve disagreement; do not guess or change labels to match a candidate.
   Actual DEV human labels use separate [Viewer JSON](../tools/dev_review/README.md)
   (`team_human`); the Viewer is tied to the 60-chat source. Arbitrary QA scenarios
   have no supported Viewer review/export path today. Human-review notes do not
   automatically promote a scenario to an imported `team_human` reference.
5. **Preserve frozen versions.** D reviews a new versioned scenario proposal and
   matching registry/split rather than editing frozen v1 labels. Classify every
   expected row, pin the exact scenario-file SHA256, and keep existing split history
   and exposure logs. Assign new groups using metadata before seeing model outputs;
   never split a base from any variant or silently rerank old groups to improve a
   result. Any intentionally changed holdout needs a new declared version; exposed
   cases cannot become a fresh hidden check simply by renaming them.
6. **Wire and verify explicitly with D.** The current harness can read an explicit
   file via `load_scenarios(path)` / `build_cases(spec)`, but Lab defaults, registry
   and split paths are pinned in code. A new `semantic_v2.json` is **not** discovered
   automatically. A future QA-only PR must agree version selection and test source
   hashes, unique IDs, registry completeness, exact edits and split separation;
   preserve existing adversarial assertions. Run the pinned-engine QA suite and
   offline Lab demo using onboarding instructions. No production change or model
   call is needed to review a scenario proposal.
7. **Review confidentiality before staging named files.** Only reviewed fictional
   text or permitted derivatives may enter a public QA PR only after public-sharing
   permission and content review; private-team approval alone is insufficient. Exclude real-call paraphrases, customer identifiers, signed URLs, keys,
   raw/control transcripts, reviewer evidence exports and generated run artifacts.
   Keep those outside Git; `.gitignore` is not a content review. Scenario approval
   does not grant external-provider export permission. Apply the separate
   [input/export policy](BACKEND_CONTRACT.md#content-authorization-for-supplied-input).

[lab]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/lab/README.md
[scenarios]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/scenarios/semantic_v1.json
[registry]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/lab/label_registry.json
[split]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/lab/splits/synthetic_v1.json
[fixtures]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/fixtures.py
[demo]: https://github.com/Gaziz121/data-challenge-2026/tree/3ff9c764aa941f71820462de806cd42d99a22c90/qa/lab/demo
[replay]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/replays/a94e48f7.json
[harness]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/harness.py
