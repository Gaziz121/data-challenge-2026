# CQA requirements and DEV calibration plan

> This document preserves the requirements interpretation and proposed benchmark.
> Statements below that no application/configuration exists describe its initial
> planning snapshot. Current implementation and onboarding are tracked in
> [TEAM_START_HERE.md](../TEAM_START_HERE.md); requirements and official-source
> authority are unchanged.

Updated: 2026-11-07, Asia/Almaty. Reviewed for PRIVATE team sharing. No application,
benchmark labels or evaluation runs have been created. See `../PROJECT_FILE_MAP.md`
for local originals versus shared derivatives; private sharing is not public
redistribution permission.

## 1. Source register and interpretation

- **C1-C3**: [official checklist - team-safe copy](shared/CQA_Chat_Quality_Checklist_TEAM_SAFE.pdf), pp. 1-3;
  exact scoring contract in [CQA_SCORING_SPEC.md](CQA_SCORING_SPEC.md).
- **G1-G4**: [student guide - team-safe copy](shared/CQA_Hackathon_Student_Guide_TEAM_SAFE.pdf), pp. 1-4.
- **O1-O7**: additional official organizer/Freedom Broker clarifications dated
  November 7, 2026, supplied as verified information by the user in this chat.
  They are user-relayed clarifications, not quotations from the PDFs and not
  independently retrieved organizer messages. The numbered mapping below follows
  the user's seven points. Do not invent a source URL or an original message file.
- **D1-D5**: [supplementary presentation - team-safe copy](shared/Data_2_TEAM_SAFE.pdf), five pages; original located in Downloads
  and preserved unchanged under `case/`; SHA256
  `57b51d5e1f8a31ee07387e44e57501d3526fb9303cba80ffc158f5e762af20e9`.
  All five pages were visually inspected; text extraction alone misses three
  image-based pages. Contents: event cover (p. 1), corporate introduction (p. 2),
  ecosystem overview (p. 3), investment-business background (p. 4), social links
  (p. 5). It is present, not a missing material. It supplies background, not an
  eight-criterion replacement, accuracy formula, or conversation-level answer key.
  Its corporate figures are source statements, not independently verified current
  facts or a comprehensive consultation/identity/confidentiality policy.

Original PDFs remain unchanged at the LOCAL ONLY paths in the file map and are
authoritative. The shared derivatives preserve visible pages, omit embedded
actions/metadata, and have separate hashes in that map. The guide's signed API
button is removed; obtain approved API access separately. No explicit private-team
sharing prohibition was found in the supplied materials; this reviewed private
sharing is user-authorized, not a license to publish materials or real calls.

The later clarifications resolve the explicitly covered ambiguities. Retain the
checklist's exact weights, response levels, N/A rules and formula unless an
authorized checklist configuration changes them. Distinguish official selection
criteria from operator-quality criteria and from our own engineering priorities.

## 2. Confirmed requirements and planned acceptance evidence

These are requirements to implement later, not claims that the product works.

| ID / source | Confirmed requirement | Evidence to produce after implementation |
| --- | --- | --- |
| R01 / O1 | Top-50 selection prioritizes AI scoring accuracy against official Ground Truth on 10 previously unseen transcripts. Other considerations: functional completeness, UX, genuine evaluation of new conversations, and diversity of technical approaches. No numerical weights or exact accuracy metric were supplied. | Reproducible quality checks and an honest account of calibration; demonstrate actual inference on unseen input. Do not present an internal metric as the official selection formula. |
| R02 / O2; G1/G3 | Control transcripts arrive through an API, as DEV does. Evaluate new records without hardcoded conversation results. | Import/evaluate a newly retrieved dataset using the saved checklist and show its evidence. Record dataset identity/hash and run configuration. Do not fetch the control API in this documentation pass. |
| R03 / O3 | The same general eight-criterion checklist applies to voice calls, adapted to spoken communication. Criterion 06 considers conversational logic, clarity, appropriate wording, and pause management. Audio-based speech quality assessment is optional when useful. | Apply a documented voice configuration with traceable spoken-turn evidence. Do not require audio scoring for all calls or infer acoustic properties from text alone. |
| R04 / O4 | Criterion 04 assesses whether substantive customer questions were addressed, advice was factually correct, and necessary next steps were explained. Conversation-specific official Ground Truth answers are not available for development. | Evidence mapping from material questions to answers/next steps and defensible factual sources; disclose uncertainty. Team-created labels must be identified as such. |
| R05 / O5; G1/G2 | Create, save and apply flexible checklists, including call-specific configurations. Criteria, wording, weights, answer types, scales and N/A settings must be configurable; a replacement criterion must work through configuration. | Save a changed checklist, apply it to a new conversation, and retain the configuration version with the result. No live configuration has been built here. |
| R06 / O6 | Check the separate organizer file `Data 2 (1) 1.pdf`; never infer missing contents. | Present and inspected as documented above. Do not mislabel it as a scoring answer key. |
| R07 / O7; G4 | Final submission requires a public GitHub repository. Keep the existing private repository as development workspace and do not change its visibility. | Later prepare a separately reviewed public submission repository after authorization and confidentiality review; leave the current private development repository intact. No publication in this pass. |
| R08 / G1/G2 | Provide the evaluation-to-review workflow: checklist setup, dialogue input, operator evaluation, per-criterion evidence, results, appeal, reviewer decision, recalculated final result and preserved original decision. Support RU/KZ/EN; bot/system events are context. | A complete reproducible path through one conversation and its appeal, including a changed checklist. No screens or functions are implemented here. |
| R09 / G1/G4 | HTML/CSS/JavaScript interface, structure suitable for later Dynamics 365 adaptation; no demonstration login required. Five-minute defense; guide describes control release at hour 23 and code stop at hour 24. | Clear startup instructions and working demonstration on the frozen submission version; exact start/deadline and presentation logistics still need confirmation. |

R01 does not establish a strict tie-break ordering or guarantee that accuracy is
the only selection consideration. Technical diversity is an organizer consideration,
not a reason to sacrifice verified accuracy or build several approaches for show.

## 3. Work priorities once implementation is authorized

1. Make evaluation defensible: apply the exact rubric, correctly distinguish N/A,
   support factual judgments, and provide real evidence for each conclusion.
2. Make the full path work on genuinely new input: API import -> checklist version
   -> evaluation -> evidence/result -> appeal/review -> recomputed final result.
3. Make runs reproducible: input hash, model/prompt/configuration version, parameters,
   evidence pointers, exact arithmetic/rounding policy, failures and reviewer changes.
4. Provide usable UX for inspecting evidence, editing checklists and resolving
   appeals. Cosmetic polish follows accuracy and working required functions.

These are team priorities, not invented official judging weights or acceptance
thresholds. No target score, model/provider choice, or accuracy promise is implied.

## 4. Proposed lightweight human-reviewed DEV benchmark

**Proposal only.** No subset has been selected, no labels assigned, no predictions
generated, and no official Ground Truth recovered. Call the reference labels
`team_human`, not `official_gt`. DEV calibration cannot establish performance on
the organizer's 10 unseen conversations or reproduce an unknown official metric.

### A. Small stratified sample, then freeze

Propose 20 DEV conversations using metadata-only selection, without replacement:

| Stratum | Available in verified DEV | Calibration | Frozen internal holdout | Total proposed |
| --- | --- | --- | --- | --- |
| RU chat | 30 | 3 | 2 | 5 |
| KZ chat | 15 | 3 | 2 | 5 |
| EN chat | 15 | 3 | 2 | 5 |
| RU voice | 5 | 3 | 2 | 5 |
| Total | 65 | 12 | 8 | 20 |

The inspected DEV metadata has no KZ/EN voice records. Do not claim coverage of
those combinations. This deliberately balances languages/channels rather than
matching the dataset's natural proportions; report stratum counts with metrics.
Do not extrapolate voice reliability from five calls or stable accuracy from eight
holdout conversations. The remaining 45 DEV records remain outside this core plan.

This proposal requires the LOCAL ONLY full original for its five-call component.
The tracked `data/shared/DEV_synthetic_60.json` deliberately lacks all calls.
A teammate with only a clone can work on chats, but must obtain permitted local
voice access before claiming the full benchmark coverage above.

When authorized, record the chosen IDs, dataset SHA256, deterministic sampling
method/seed, split, and checklist version in one ignored local benchmark manifest.
Do not select on model errors. If inspecting calibration conversations reveals
missing N/A/critical-error patterns, add explicitly marked calibration challenge
cases from remaining DEV; do not cherry-pick or move holdout examples. Record
the actual support for rare cases rather than manufacturing positive labels.

### B. Human labels, uncertainty, and independent review

One language-competent primary reviewer labels the proposed 20 conversations on
all eight criteria (160 criterion decisions). A second reviewer independently
labels the eight holdout conversations and all five voice calls; overlapping
cases are reviewed once. This covers 11 distinct conversations before extra
dispute review. Reviewers work before seeing model predictions. Use competent
RU/KZ/EN reviewers; flag language limitations rather than pretending certainty.

Keep reference labels outside the runtime evaluator's inputs. Never return a
stored label by conversation ID, transcript hash, or audio URL; the benchmark
checks genuine evaluation rather than supplying answers to the application.

For each criterion record the permitted raw response, applicability/N/A reason,
rationale, exact transcript evidence/range, factual source where needed,
uncertainty, reviewer, checklist version and `label_origin=team_human`. Keep
independent labels and the adjudicated decision distinct. Record disagreement
and the reason for resolution. Review all C03/C04/C08 uncertainties and any
disputed calibration decision; do not use the model under test as the adjudicator.

Where a factual/identity/confidentiality question cannot be established from
available evidence, retain an internal unresolved marker rather than guessing an
official answer or assigning N/A without its allowed condition. Exclude unresolved
cells from scored agreement denominators and report them separately with coverage.
This uncertainty marker is not a new permissible answer in the official checklist.

The coding/prompt owner may use the 12 calibration cases. A designated reviewer
keeps the eight holdout labels out of tuning, freezes/adjudicates them before a
candidate evaluation, and records any unavoidable prior exposure. Holdout data
are still DEV, not organizer control data. Once holdout results inform a change,
the set is no longer an untouched check; declare the exposure and use a newly
held-out DEV subset if another independent check is needed and available.

### C. Internal diagnostics, not the organizer's metric

Report numerator/denominator, unresolved coverage and relevant stratum counts:

- Exact permitted-response match by criterion; N/A is a distinct response, and
  numeric criteria match their raw discrete level, not just a nearby total.
- N/A applicability confusion counts and critical-error Yes/No confusion counts;
  include positive support, misses and false alarms. Do not hide rare errors
  behind an overall mostly-No rate. Precision/recall only when denominators exist.
- Total-score mean absolute error as a secondary diagnostic only for conversations
  with complete adjudicated weighted labels; use the source formula and record
  whether totals are unrounded or rounded. Until rounding ties are resolved, use
  exact unrounded totals for this internal comparison and flag display policy.
- Evidence audit: valid source pointer, faithful excerpt/checked range, and whether
  it actually supports the decision. No fabricated automatic evidence-quality
  score. Log errors by applicability, factual correctness, role attribution,
  rubric anchor, evidence, language/channel and arithmetic.

No combined weighted benchmark score, pass threshold, official-metric name, or
claim of official Ground Truth accuracy is introduced. Before each future run,
freeze labels and record input/configuration hashes, model/prompt version,
parameters, run ID, predictions and actual cost/latency if measured. Compare
candidates on identical adjudicated cells; retain failed/unresolved cases in
coverage reports. Store labels, transcripts, signed links and predictions locally.

## 5. Remaining requirements and decisions

- **Selection metric:** exact accuracy definition, criterion-versus-total unit,
  tolerances, aggregation, N/A/critical-error treatment, ties, and any numerical
  weights remain unspecified. No official numerical target is known. [O1]
- **Control API:** exact endpoint/group ID, authorization, release time/access,
  payload guarantees, retry/rate limits and required result format are not newly
  specified. Use G3's DEV envelope as known input documentation, not proof that
  every future payload detail is identical. The 10-control composition is unknown.
- **Voice calibration:** general applicability, spoken C06 dimensions and optional
  audio are resolved; precise pause severity thresholds, off-channel identity
  evidence, interruption/partial-transcript handling, and audio offset mapping
  still need calibration/clarification. No new default weights or raw scales
  were supplied. See scoring-spec A01-A11.
- **Factual reference:** no conversation-specific development Ground Truth will
  be available. Approved product/process facts and identity/confidentiality
  boundaries are still needed where the transcript and supplied sources cannot
  establish them. Data 2 is background, not a comprehensive policy answer key.
- **Remaining score details:** rounding tie-breaking, closing AND/OR wording,
  handover/language-switch scope, section aggregation and anchor borderline
  cases remain unresolved unless separately confirmed.
- **Submission:** public repository requirement is confirmed, not a visibility
  ambiguity. A separate sanitized submission repository, publishable file scope,
  organizer access and exact submission logistics remain to be agreed. Keep
  private development and restricted material unchanged; publish nothing now.
- **Execution:** benchmark reviewers, actual split IDs, versioned human labels,
  adjudication and evaluation remain proposed work. No missing official DEV
  answer key is promised. No application/provider/API work is authorized here.
