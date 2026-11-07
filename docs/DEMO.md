# Five-minute demonstration (only functions verified to work)

## Setup (once, before the defense; no API key or network needed)

```sh
git checkout integration/final-submission
# Optional, for minute 4b (supplied new conversation): approve the three FICTIONAL demo records locally.
PYTHONPATH=src python3 -B -m cqa_results.grants --data docs/demo/fictional_new_conversations.json \
  --data-class synthetic_test --reference demo-fictional-conversations \
  --expires 2030-01-01T00:00:00Z --output restricted/demo-approvals.json
CQA_REVIEWER_KEY=demo-reviewer-key PYTHONPATH=src python3 -m cqa.web --port 8765 \
  --checklist src/cqa/checklists/official-v7.json --live-call-limit 0 \
  --authorization-manifest restricted/demo-approvals.json
```

Open http://127.0.0.1:8765/. Rehearse once; delete `outputs/app/` beforehand if you want an empty history.
Print a paste-ready demo conversation (KZ voice transcript) for minute 4b:

```sh
python3 -c "import json;e=json.load(open('docs/demo/fictional_new_conversations.json'));print(json.dumps({'dataset_group_id':e['data']['dataset_group_id'],'record':e['data']['records'][1]},ensure_ascii=False))"
```

## Script

**Minute 1 — the problem.** Contact-centre QA is manual, slow and inconsistent. We evaluate every
conversation against the organizer's checklist (C01–C07 weighted 10/15/20/20/15/15/5, C08 critical flag)
in RU/KZ/EN, with evidence a reviewer can check in one click, and an appeal path.

**Minute 2 — load and evaluate.** Select `p1-ru-001` (RU) → the full transcript in original order with
timestamps and roles. Checklist `2026-11-07.v5`, provider **Replay recorded genuine reply**, Evaluate.
Say clearly: *this re-validates a real gpt-5.4-mini reply we recorded earlier; no new call is made.*
(With an approved key the same button runs OpenAI live; we keep it off in the demo.)

**Minute 3 — score, evidence, N/A.** Total 100.00, critical flag no. Open C01: click the evidence
button → the operator's greeting turn is highlighted (turn numbers = official `evidence_turns`).
C02/C03 are N/A: the backend derived N/A from atomic facts (clear request; no account action needed) and
redistributed their weights — effective weights are shown per card. Open "Atomic rubric checks" to show the
facts and quotes the decision is built from.

**Minute 4a — appeal and reviewer.** C07 says "yes", but the operator only said "you're welcome, good evening".
Under History and appeals: criterion C07, requested `no`, name *Operator*, explanation → Submit. As reviewer
(name *Reviewer*, key `demo-reviewer-key`): Change → `no`, reason → Record. The comparison shows
**original 100.00 → revised 92.31**; the stored evaluation is untouched; the appeal keeps its history.
Then open the Checklist editor: v6 is the same checklist with C07 wording clarified from the official text —
a new immutable version, selectable per evaluation. Edit a weight, save as a new version, evaluate again (mock)
to show the weights flow through (mock = wiring fixture, clearly labelled).

**Minute 4b (if time) — new conversation.** Paste the KZ voice transcript printed above → Show → Evaluate
(mock, legacy v3 checklist) → eight criteria with evidence over the supplied turns. Without the local approval
the server refuses with 403 — data governance by default.

**Minute 5 — architecture, reliability, readiness.** Engine: normalize → model reports *facts* with exact
quotes → deterministic validators (quote must exist in the transcript, role/order rules, full-scope proof
for "nothing happened" claims) → rule-derived decisions → exact rational scoring. Invalid output is rejected,
never patched; at most one bounded repair call. Submission: `cqa_results` batch → export → independent
validator → push → anonymous public-URL check, rehearsed offline end to end with fictional controls.
Limitations: one live-accepted conversation so far; semantic accuracy against official labels is unknown.

## Q&A preparation

- **Why this model?** gpt-5.4-mini supports strict JSON-schema output, RU/KZ/EN, and costs about
  USD 0.013–0.023 per conversation at ~14 s; all live evidence so far uses it. We did not claim it beats others.
- **Why atomic-first instead of a direct rubric answer?** Our first direct-rubric calls were rejected for
  self-contradictions (N/A reasons on applicable answers, applicability conflicts). Asking for observable facts
  with quotes lets the backend derive N/A and binary decisions deterministically and audit every step. A small
  paired comparison with a lean direct-rubric arm is planned (docs/EVALUATION_COMPARISON_PLAN.md) but not run.
- **Hallucination control?** Every quote must match the source turn (formatting-only normalization recorded);
  role and chronology rules; negative claims need full-dialogue scope; contradictions block scoring.
- **Citation grounding?** Message IDs map to original transcript positions; the exporter writes
  `evidence_turns` = original index + 1 and re-checks the quote against that turn.
- **New checklists?** Saved as immutable versions with content hashes; criteria, wording, weights, discrete
  scales, anchors and N/A rules are data, not code. The official export accepts only checklists matching the
  organizer's eight IDs/scales/weights and refuses others.
- **When evaluation fails?** The UI shows the rejected original output and per-criterion reasons with no score;
  the official file records `status: "error"` with the reason — never a zero score.
- **Appeals?** Separate append-only records: appellant, explanation, requested value, reviewer (different
  person, reviewer key), outcome and reason; the revised total uses the same official arithmetic.
- **Accuracy claims?** None against official Ground Truth: it is unavailable for development. We can claim
  structural validity, deterministic scoring verified against independent Decimal arithmetic, and test coverage.
