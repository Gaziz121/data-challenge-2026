# Architecture decisions

Checked against committed engine **`f4599f0`** (0.5.0 / `baseline-v4` / rubric v3)
and independent QA **`3ff9c76`**, November 7, 2026. Refreshed publication checkpoint:
**`6481390` / engine 0.6.1** adds the opt-in atomic path below; default v3 retains
the compatibility behavior. No active worktree was changed. This records the reasoning supported by code and existing
reports; it does not claim a complete historical design debate or proven accuracy.
Use [onboarding](../TEAM_START_HERE.md) for commands and ownership, the
[backend contract](BACKEND_CONTRACT.md) for HTTP details, and the
[experiment backlog](EXPERIMENT_BACKLOG.md) for proposed measurements.

## New published atomic path

[atomic.py][atomic] validates facts, evidence roles/chronology and derives configured
C01/C02/C03/C05/C08 responses; every criterion's applicability is backend-owned.
C04/C06 and applicable C07 retain model judgment. [atomic_prompt.py][atomic-prompt]
compiles the hand-authored rubric into wire 1.2 with explicit sources and scope
plans; it does not invent questions from arbitrary criterion prose. Raw wire
output, normalized decisions and review origins remain separate. Unsolicited
judgments conflict rather than being silently replaced. [Atomic tests][atomic-tests]
cover these boundaries, not semantic correctness. This advances the earlier
check-only design; it is not an independent Maker/Checker or accepted-appeal system.

## Implemented choices, rationale and trade-offs

| Choice | Reason and cost | Source / verification |
| --- | --- | --- |
| Preserve a normalized conversation and source provenance before evaluation | Keeps roles, message order, timestamps and evidence locators reproducible. Strict known-shape parsing rejects unfamiliar input instead of guessing; organizer control payloads need a verified adapter. | [loader.py](../src/cqa/loader.py), [loader tests](../tests/test_loader.py) |
| Keep checklist definitions as versioned data | Criteria/questions/weights/N/A rules can change without branches keyed to criterion IDs. Immutable ID/version snapshots preserve old results. Questions/rules are hand-authored; supported scales/categories remain constrained. | [checklists.py](../src/cqa/checklists.py), [schemas.py](../src/cqa/schemas.py), [save/select tests](../tests/test_control_backend.py) |
| Separate observable facts, atomic model judgments and score arithmetic | Facts locate agent turns; the provider answers atomic questions before choosing permitted raw anchors; Python computes totals. This makes failures inspectable, but atomics can still be wrong or mutually inconsistent. | [preprocessing.py](../src/cqa/preprocessing.py), [prompt.py](../src/cqa/prompt.py), [engine.py](../src/cqa/engine.py), [output-order tests](../tests/test_output_contract.py) |
| Validate and retain failures rather than repair scores | Strict types, applicability, roles, quotes and consistency gates stop invalid replies. Original output/usage/diagnostics survive; optional quote repair allows only traceable formatting equivalence. Rejection reduces usable-result coverage, which must be reported. | [validation.py](../src/cqa/validation.py), [evidence.py](../src/cqa/evidence.py), [repair/rejection tests](../tests/test_evidence_repairs.py) |
| Compare explicit conditional rules and prove cited source coverage | V3 C05 distinguishes complaint presence from an obligation to respond. C08 negative scopes must cover the dialogue, including each negative category atomic. Generic configured checks record disagreement; they never replace a model answer. Scope coverage proves locators, not attention or semantic truth. | [decision_rules.py](../src/cqa/decision_rules.py), [coverage.py](../src/cqa/coverage.py), [truth-table/coverage/replay tests](../tests/test_decision_coverage.py) |
| Use exact deterministic scoring outside the model | Rational arithmetic preserves N/A redistribution and avoids rounding drift. Critical C08 stays a separate flag without an invented penalty. HALF_UP is a documented local convention, not a newly confirmed organizer rule. | [scoring.py](../src/cqa/scoring.py), [independent Decimal/exhaustive tests](../tests/test_scoring.py), [scoring spec](../case/CQA_SCORING_SPEC.md) |
| Use small finding-only verification hooks | Pre/post checks receive private snapshots and return info/review/block findings. This leaves room for targeted verification while preserving the maker decision. A blocking pre-check prevents inference; post-validation hooks cannot inspect rejected replies through that hook. | [checks.py](../src/cqa/checks.py), [snapshot/advisory/block tests](../tests/test_pipeline.py) |
| Wrap the same core with a restricted local API | One engine serves CLI and browser; exact content grants and separate export permission prevent requests from authorizing themselves. Loopback, same-origin and one evaluation at a time simplify local safety; they are not a production deployment design. | [web.py](../src/cqa/web.py), [access.py](../src/cqa/access.py), [boundary tests](../tests/test_control_backend.py), [HTTP tests](../tests/test_web.py) |
| Keep human references and independent QA outside runtime scoring | Blank human reviews reduce anchoring on AI scores; Lab independently checks saved artifacts and compares identical cells. Multiple branches and version compatibility cost extra coordination. Human/QA proposals are not official Ground Truth. | [viewer workflow](../tools/dev_review/README.md), [viewer tests](../tests/test_dev_review.cjs), [Lab implementation][lab], [Lab tests][lab-tests] |

## Socrates-inspired concepts: actual status

“Socrates-inspired” is the team's design shorthand from the earlier
[concept inventory](CORE_READINESS_AUDIT.md#b4-requested-geminisocrates-concept-inventory),
not a claim that a particular external framework/paper was implemented. No separate
Socrates specification is available in this repository. This table updates that
older audit to the committed snapshot above.

| Idea | Implemented | Still proposed / unproven |
| --- | --- | --- |
| Atomic-first reasoning | Applicability/conditional triggers serialized first; `atomic_checks` precedes `response` in the actual model schema. | Automatic rubric-to-atomic compiler; controlled evidence that ordering improves semantic accuracy. |
| Rule-derived judgments | Compatibility checks plus opt-in v4 backend derivation from validated facts for configured atomic criteria and all applicability. | Discretionary anchors and semantic fact truth remain model/human work. No hardcoded QA rule map is imported; raw judgments are preserved and conflicts rejected. |
| Evidence-based verification | Exact quotes/roles/locators, traceable formatting resolution, source-ID coverage and retained diagnostics. | Semantic entailment, product-policy truth and independent proof that the model inspected every message. |
| Targeted Maker/Checker | Snapshot/finding hooks, audit and original-output preservation are foundations. | A second independent inference, risk routing, automatic correction or accepted reviewer-revision execution. The ordinary pipeline has one primary provider evaluation. |
| Adversarial counterfactual evaluation | Independent [scenario harness][harness] and offline [Accuracy Lab][lab], with grouped splits and proposed labels. | Measured real-model robustness, human-reviewed scenario references and independent v3/v4 wire, projection and coverage checks. Scripted demos demonstrate mechanics only. |

## Alternatives excluded or deferred

- **Excluded by the current contracts:** model-computed totals, ID-based answer
  lookup, silent score/response correction, treating a mock as an evaluator,
  treating the partial 60 chats as full DEV, or relabeling private/control data
  as synthetic to bypass export checks. These break scoring, provenance or privacy.
- **Deferred pending evidence:** a universal second LLM, recursive multi-agent
  orchestration, automatic checklist compilation and unrestricted rule/scale
  languages. Current seams allow focused trials; no experiment yet demonstrates
  that their added latency, cost and failure modes are justified. Start with the
  small [backlog](EXPERIMENT_BACKLOG.md), not a new runtime framework.
- **Deferred product/integration work:** organizer API mapping, full checklist UX,
  appeal/reviewer acceptance/recalculation and production persistence/access.
  Typed revision fields and internal grants are not those completed workflows.

Structural tests demonstrate these boundaries. They do not establish semantic
accuracy; the [repair history](VALIDATION_REPAIR_REPORT.md) records rejected live
responses, not an accepted live quality total.

[lab]: https://github.com/Gaziz121/data-challenge-2026/tree/3ff9c764aa941f71820462de806cd42d99a22c90/qa/lab
[lab-tests]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/test_lab.py
[harness]: https://github.com/Gaziz121/data-challenge-2026/blob/3ff9c764aa941f71820462de806cd42d99a22c90/qa/harness.py

[atomic]: https://github.com/Gaziz121/data-challenge-2026/blob/6481390de7f4bd1905b79168c54b600642dc7ef7/src/cqa/atomic.py
[atomic-prompt]: https://github.com/Gaziz121/data-challenge-2026/blob/6481390de7f4bd1905b79168c54b600642dc7ef7/src/cqa/atomic_prompt.py
[atomic-tests]: https://github.com/Gaziz121/data-challenge-2026/blob/6481390de7f4bd1905b79168c54b600642dc7ef7/tests/test_atomic_path.py
