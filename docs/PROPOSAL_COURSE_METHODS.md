# Proposal: accuracy priorities and course-method additions

**Status: PROPOSAL ONLY.** Nothing below is implemented. No model calls were made,
no labels were created and no production file was changed with this document.
Author: Aibek (prepared with Claude). Reviewed snapshot:
`codex/local-mvp-integration` at `6481390` (2026-11-07 18:21 +05).
Course source: ECON 434 *Introduction to Big Data Analytics* lecture slides
(lectures 1-11) and the *Valence Shifters in sentimentr* notes. These are kept
locally by Aibek and are not in Git. Lecture numbers below refer to that set.

Integration owner decides what to adopt. Each item states what is observed,
what is proposed and what remains unverified.

## 1. Why accuracy and "always produce a result" come first

- **Official objective:** top-50 selection prioritizes AI scoring accuracy against
  official Ground Truth on 10 unseen transcripts (`case/CQA_REQUIREMENTS.md`, R01/O1).
- **Observed:** the repository records four genuine provider responses: three
  single-pass and one atomic-path. All four were rejected without a total. The
  documented runs used synthetic `p1-ru-001` only (`TEAM_STATUS.md`,
  `docs/VALIDATION_REPAIR_REPORT.md`, `tests/fixtures/live_*.json`).
- **Observed:** the recorded rejection reasons are mostly team-defined format and
  evidence gates: an N/A reason on an applicable criterion, a missing whole-dialogue
  scope, an omitted judgment. They are not documented as wrong official responses.
  In the atomic run, five of eight criteria were individually validated.
- **Implication (unverified):** if the same rejection rate occurs on control data,
  those transcripts get no score. A missing score is unlikely to match Ground Truth.
  The current evidence is a single conversation, so the real rejection rate is unknown.

## 2. Engineering proposals, highest priority first

| ID | Proposal | Why | Cost / risk |
| --- | --- | --- | --- |
| P1 | **Bounded repair loop.** On validation failure, re-send the same request plus the machine-readable diagnostics and ask for a complete corrected output. Limit: 1-2 attempts. Keep every raw attempt in the audit; nothing is mutated silently. | Most recorded failures are fixable format/scope omissions that the model can correct when told exactly what failed. | One extra call only when needed. Adds attempt history to the result contract. |
| P2 | **Labeled provisional result for control runs.** If output is still invalid after P1, emit a clearly separated `provisional / needs_review` result: validated criteria as accepted, the model's raw response for the failed ones, plus the failure list. | For the competition, "no score" is probably worse than a reviewed provisional score. Accepted and provisional results stay distinguishable. | Policy decision for the integration owner: it relaxes "never score partial output" for control runs only. |
| P3 | **Multi-conversation live smoke before control.** Run at least about 10 DEV chats (RU/KZ/EN, N/A cases, critical-error cases) under the current rubric to measure the actual rejection rate. | One conversation cannot estimate how often the gates reject. | About USD 0.02 per call at recorded usage (estimate from the repo's own usage records). |
| P4 | **Self-consistency (not from the course).** Run three independent evaluations and take the per-criterion majority. Disagreement means `needs_review`. | Reduces run-to-run variance and gives a free uncertainty signal for the reviewer and for appeals. | About three times the cost per transcript. Needs a tie rule for scale criteria (e.g. the median level). |

## 3. Course methods mapped to the pipeline

### 3.1 Cross-validation and leakage (lecture 3)

- **Observed in plan:** `CQA_REQUIREMENTS.md` §4 proposes one 12-calibration / 8-holdout
  split. Lecture 3 shows that a single validation split has high variance. Eight
  holdout conversations give a very noisy accuracy estimate.
- **Proposal:** compare prompt/rubric candidates with grouped K-fold or
  leave-one-group-out cross-validation over all team-labeled conversations, and
  report the spread across folds, not only the mean.
- **Leakage risk (observed by manual reading and a keyword check, not exhaustive):**
  many KZ/EN chats are the same scenario as an RU chat, adapted to another language.
  If one language version is used for calibration and another in holdout, the
  holdout overstates accuracy. Examples:

  | Scenario | Conversations |
  | --- | --- |
  | Tariff name in «Кабинет» | p1-ru-001, p1-kz-001, p1-en-003 |
  | Old login stays reserved | p1-ru-015, p1-kz-007, p1-en-001 |
  | Form 1042-S language | p1-ru-012, p1-kz-014, p1-en-011 |
  | D-account cannot buy securities | p1-ru-024, p1-kz-011, p1-en-010 |
  | Untick margin in order settings | p1-ru-020, p1-kz-010, p1-en-009 |
  | Paid private offer (C08) | p1-ru-022, p1-kz-013, p1-en-013 |
  | Withdrawal restriction / disclosure | p1-ru-009, p1-kz-015, p1-en-014 |
  | Transfer not shown on account | p1-kz-003, p1-en-006 |
  | Freedom Holding investor reports | p1-ru-013, p1-en-012 |

  The group key should be the scenario, not the conversation and not the language.
  Timestamp templates are reused across *different* content (e.g. p1-kz-015 vs
  p1-en-015), so timing must not be used as the scenario key.
  The mapping above needs human confirmation before use.

### 3.2 Error types, thresholds and asymmetric cost (lectures 4-5)

- Report per-criterion confusion counts. For C08 (critical errors) and for every
  N/A decision, report the **false negative rate** separately. Most C08 answers are
  "no", so overall accuracy hides missed violations.
- Treat costs as asymmetric: a missed insult, bypass offer or disclosure is worse
  than a false alarm that a reviewer clears. Lower the threshold: route to review
  when *any* signal flags a violation (the model, a P4 run or a lexical rule).
- This extends the diagnostics already listed in `CQA_REQUIREMENTS.md` §4C with an
  explicit threshold/cost decision. It does not invent an official metric.

### 3.3 Decision trees (lecture 9)

- Already implemented: rubric v4 / atomic path. The model answers atomic questions
  and the backend derives the decision, which is effectively a shallow decision tree.
- **Proposal (pruning analogue):** after P3, list atomic questions that never change
  the derived decision across the DEV runs. Each one adds tokens and a way to fail
  validation without improving accuracy. Remove or merge them, as cost-complexity
  pruning removes branches that do not pay for themselves.

### 3.4 Nearest-neighbour examples (lecture 6)

- **Proposal:** for each new transcript, retrieve the k most similar labeled
  conversations (team_human labels and accepted appeal decisions) and include their
  criterion decisions as calibration examples in the prompt.
- A character n-gram cosine similarity works across RU/KZ/EN and needs no new
  dependency.
- During cross-validation, exclude examples from the same scenario group (§3.1),
  otherwise retrieval leaks the answer.
- This also gives appeals a purpose beyond one conversation: reviewer decisions
  become reusable calibration examples without editing the rubric.

### 3.5 Clustering and PCA (lectures 8, 11)

- Cluster conversations by topic (e.g. TF-IDF or character n-grams + k-means).
  The result is used for three things:
  1. stratified selection of conversations for human labeling, covering every
     topic, not only every language;
  2. cross-validation groups (§3.1);
  3. a 2-D PCA map for the defense, showing the topics and where errors concentrate.
- The manual scenario table in §3.1 can seed or check the clusters.

### 3.6 Client sentiment with valence shifters (course notes)

- **Proposal:** compute a sentence-level client sentiment score with the notes'
  rules: a context window of 5 words before and 2 after, cut at commas, colons and
  semicolons; negator parity; amplifiers turning into de-amplifiers under negation;
  a floor at zero; and division by √n.
- **Use 1, review signal:** cross-check the C05 trigger (05.q3, "did the client
  express dissatisfaction?"). Strongly negative client sentiment combined with a
  model answer of "no complaint" goes to review.
- **Use 2, UI:** show the client's mood at the start and at the end of each
  conversation. This is most useful for the voice calls.
- **Limitations:**
  - RU/KZ/EN lexicons have to be written and reviewed.
  - Kazakh negation is often a suffix (-ма/-ме/-ба/-бе/-па/-пе) or «емес»/«жоқ»,
    so word-level negators miss part of it.
  - The score is a signal, never a scored criterion.

### 3.7 Logistic regression with lasso (lectures 4, 7): deferred

Stacking atomic answers and simple features into a per-criterion logit, with a lasso
to select features, is only reasonable with substantially more team_human labels
than the proposed 20. With 20 labels it would overfit. Revisit only if labeling
scales up.

### 3.8 Not applicable

Linear regression (lecture 2) and splines/GAM (lecture 10) have no clear role in
this pipeline. Do not add them to make the method list longer.

## 4. Interpretation notes

- **3-minute first-response threshold:** agree with the current rubric that it is
  excluded from scoring. In the checklist footnote it is listed together with tags
  and attachments as not entering the evaluation.
- **Closing (scoring spec A08):** many DEV chats end with thanks plus a farewell
  and no summary or offer of further help (e.g. p1-ru-001, p1-ru-004, p1-en-004).
  Under the strict AND reading these become "no". Because the choice moves a
  noticeable share of C07 decisions, it is worth asking the organizers.

## 5. Suggested order

1. P1 repair loop, then P3 multi-chat live smoke to measure the rejection rate.
2. Human labels on 20-30 DEV chats selected by scenario group/cluster (§3.1, §3.5).
   Grouped cross-validation as the comparison method.
3. P4 self-consistency, k-NN examples (§3.4), sentiment review signal (§3.6).
4. P2 decision before the control window.
5. Checklist editor and appeal workflow in the UI (still missing per `TEAM_STATUS.md`).

## 6. Parallel experimental model

As agreed with Gaziz, Aibek will build a separate experimental evaluator locally.
To keep comparison fair:

- use the same team_human labels and the same scenario-grouped folds;
- emit results in, or convertible to, the existing result contract, so the paired
  baseline/candidate comparison in `qa/lab` (branch `feature/cqa-independent-qa`)
  can be reused.

No results from that model exist yet.
