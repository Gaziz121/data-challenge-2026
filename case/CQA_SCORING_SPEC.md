# CQA scoring specification - initial official checklist

Version: 2026-11-07, updated with organizer clarifications supplied by the user.
Private-team specification; no conversations have been scored. The original Russian
PDFs govern the initial scoring contract, with explicit later clarifications as
recorded below. English descriptions below are faithful working translations.
Rules marked **Derived** follow mathematically from the sources;
**Convention** and **Open** are not additional official scoring requirements.

## 1. Sources and precedence

- **C**: [Official Chat Quality Checklist - team-safe copy](shared/CQA_Chat_Quality_Checklist_TEAM_SAFE.pdf),
  3 pages; original SHA256 `2f6908c3026b6221f169a0a4efe808f37cdc6d1f227ed95bfe1c6431ec597808`.
  **C1** = criteria, weights, applicability on p. 1; **C2** = scales/calculation
  and exclusions on p. 2; **C3** = interpretation/evidence guidance on p. 3.
- **G**: [Official Student Guide - team-safe copy](shared/CQA_Hackathon_Student_Guide_TEAM_SAFE.pdf), 4 pages,
  original SHA256 `8b2f79a685c6707749c780ee042d06c2bf4bff8741732698b4c8bac033ff1b5e`.
  **G1** = task/data on p. 1; **G2** = scoring, evidence and review on p. 2;
  **G3** = input/timestamps on p. 3; **G4** = submission/FAQ on p. 4.
- **O1-O7**: verified organizer/Freedom Broker clarifications dated November 7,
  2026, relayed by the user in this chat; numbered as the user's seven points.
  See [CQA_REQUIREMENTS.md](CQA_REQUIREMENTS.md) for provenance, confirmed
  requirements, outstanding decisions and the proposed human-reviewed benchmark.
  These are not independently retrieved messages or quotations from C/G.
- **D1-D5**: [Supplementary presentation - team-safe copy](shared/Data_2_TEAM_SAFE.pdf), five pages, original SHA256
  `57b51d5e1f8a31ee07387e44e57501d3526fb9303cba80ffc158f5e762af20e9`.
  Present, preserved unchanged and visually reviewed for O6. It provides event/company
  background, not conversation-specific Ground Truth or replacement scoring rules.

Authoritative originals remain LOCAL ONLY at `PROJECT_FILE_MAP.md` paths. Team-safe
PDFs preserve visible pages but remove embedded actions/metadata and the guide's
signed API link; derivative hashes are separate. A clone does not include originals.

All seven source pages were text-extracted and visually inspected. Originals are
unchanged. C supplies the scoring rules; G2 explicitly delegates weights, N/A,
and rounding to the supplied checklist. G1 calls C the initial configuration;
G2 requires editable criteria, weights, answer types, scales, and N/A settings.
This document specifies that initial configuration, not an immutable application
design. The eight items are operator-quality criteria, not eight hackathon judging
categories. No hackathon judging weights are inferred from them.

O1 confirms that top-50 selection prioritizes AI scoring accuracy against official
Ground Truth on 10 unseen transcripts; the exact metric and numerical selection
weights are unknown. This is separate from C's operator-score weights. Control
data arrive through an API and must be genuinely evaluated, never answered through
hardcoded results. No conversation-specific official development answers exist.
[O1-O2; O4]

## 2. Eight criteria and permitted responses

`Да` = Yes; `Нет` = No. For 01-07, Yes is good performance; for 08, Yes means a
critical violation was identified. The weighted criteria sum to 100. [C1-C2]

| ID | Official criterion | Allowed raw responses | Base weight | Exact permitted N/A condition |
| --- | --- | --- | --- | --- |
| 01 | Установление контакта / Establishing contact | Да, Нет | 10 | Not allowed |
| 02 | Выявление потребности / Identifying the need | Да, Нет, N/A | 15 | Enough information to answer was available from the outset |
| 03 | Идентификация / Identification | Да, Нет, N/A | 20 | The request did not require identification |
| 04 | Корректная и полная консультация / Correct and complete consultation | 0, 5, 10, 15, 20, N/A | 20 | The chat ended before the client formulated a request |
| 05 | Эмпатия и клиентоориентированность / Empathy and client orientation | Да, Нет | 15 | Not allowed |
| 06 | Управление диалогом, скорость и грамотность / Dialogue management, speed and language quality | 0, 4, 7, 10 | 15 | Not allowed |
| 07 | Завершение / Closing | Да, Нет, N/A | 5 | The chat broke off before there was an opportunity to close it |
| 08 | Грубые ошибки / Critical errors | Да, Нет | None; separate flag | Not allowed |

**01.** Yes requires greeting the client in the client's language and introducing
oneself in the first reply. Do not add an unstated company-name script or greeting
deadline. Evaluate the operator; bot replies are context, not operator actions.
First-operator-reply interpretation follows G2; handovers are Open A09. [C1; G2]

**02.** When information is missing, Yes requires considering known details and
clarifying what is missing before answering. If enough information existed from
the start, use the stated N/A condition, not a requirement to ask redundant
questions. What counts as sufficient depends on the actual request. [C1]

**03.** Yes requires confirmation of identity verification before disclosure of
data or a protected action. A general question about tariffs does not require
identification. If verification was required before a protected action and is not
confirmed in the chat, the source explicitly says No, not N/A. Do not assume
verification occurred outside the visible evidence. The exact protected-action
policy and voice/off-channel confirmation remain Open A03/A04. [C1; C3]

**04.** Score the correctness/completeness of the answer or next step using only
the five levels below. A correct next step can earn full marks; immediate final
resolution is not always required. N/A is only the pre-request termination case,
not uncertainty about correctness or a difficult request. O4 confirms that the
assessment examines whether substantive customer questions were addressed,
advice was factually correct, and necessary next steps were explained. Consider
all relevant dimensions without inventing subweights or replacing C2's discrete
anchors; C2's correct-next-step route to full credit remains. No conversation-
specific official Ground Truth answers are available for development. [C1-C2; O4]

**05.** Yes means the operator is polite and, if the client expressed dissatisfaction
or described an inconvenience, responds to that specific problem. A dissatisfied
client is not a prerequisite for applying this criterion. Do not invent a mandatory
apology phrase, sentiment threshold, or separate numerical empathy scale. [C1]

**06.** Use the four levels below to assess clarity, sequence and warning about
waiting. Correctness/completeness belongs to 04: an understandable answer that
addresses only part of a request can score well on 06 and partially on 04. The
three-minute first-response threshold, tags and attachments do not enter the
score in this task. No alternative time SLA or spelling-error count is supplied.
The phrase "explicit waiting" has no quantitative threshold. For voice calls,
consider conversational logic, clarity, appropriate wording and pause management;
audio-based speech-quality assessment is optional when useful. No different
initial weight, raw levels or pause-duration threshold was provided. [C1-C3; O3]

**07.** The source says: "оператор подвёл итог или предложил дальнейшую помощь и
попрощался". Working interpretation: (summary OR offer of further help) AND
farewell. Boolean scope is not explicitly formalized; see Open A08. A routine
operator closure without a farewell must not be excused as an interrupted chat:
C3 gives that omission as a No example. N/A requires the actual interruption
condition, with evidence. [C1; C3]

**08.** Yes means at least one of the three specified critical errors was identified;
No means none of those three was identified. See section 5. Do not invert this
flag into a positive-quality response or assign it a numeric weight. [C1-C3]

## 3. Exact discrete scales

Criterion 04 raw maximum is 20; weight is 20. [C2, heading 04]

| Raw score | Official Russian anchor | English interpretation |
| --- | --- | --- |
| 20 | Все существенные вопросы закрыты или дан корректный следующий шаг. | All material questions are addressed, or a correct next step is given. |
| 15 | Основной вопрос решён, пропущена второстепенная деталь. | Main question resolved; a secondary detail omitted. |
| 10 | Часть запроса закрыта, существенный вопрос остался открытым. | Part addressed; a material question remains open. |
| 5 | Есть общая подсказка, но клиенту всё ещё непонятно, как действовать. | General guidance given, but the client still lacks a clear course of action. |
| 0 | Ответа по существу нет или ключевая рекомендация ошибочна. | No substantive answer, or the key recommendation is incorrect. |

Criterion 06 raw maximum is 10; weight is 15. [C2, heading 06]

| Raw score | Official Russian anchor | English interpretation | Points before N/A redistribution |
| --- | --- | --- | --- |
| 10 | Ответы ясные и связные. Если было явное ожидание, оператор предупредил. | Clear, coherent replies; warning given if there was explicit waiting. | 15 |
| 7 | Один заметный сбой, но клиент может понять ответ и продолжить. | One noticeable lapse, but the client can understand and continue. | 10.5 |
| 4 | Клиенту приходится переспрашивать из-за формулировок или порядка ответов. | Wording or response order forces the client to ask again. | 6 |
| 0 | Из-за бессвязных или противоречивых реплик ход диалога непонятен. | Incoherent or contradictory replies make the dialogue unclear. | 0 |

The numeric ranges on C1 do not authorize arbitrary intermediate values: C2 says
to select one listed level. Do not use 06=5 or 04=17.5. The conversion column is
**Derived** from C2's proportional weighting rule, not an extra raw scale.
Borderline combinations not resolved by the anchors are reviewer calibration
questions, not permission to invent new levels. [C2; Open A07]

## 4. Weighting, N/A, and rounding

Official sequence: determine applicability, assign an allowed response/level,
convert scales proportionally to weight, exclude N/A and redistribute weights
proportionally across applicable criteria, then round the final total to two
decimal places. If no weighted criteria apply, do not calculate a total. Critical
errors are recorded separately. [C2, calculation steps 1-5; G2]

**Derived mathematical specification**, for weighted criteria 01-07:

- `A` = set of applicable weighted criteria; 08 never belongs to `A`.
- `w_i` = original weight; `W = sum(w_i for i in A)`.
- `r_i = 1` for Yes, `0` for No; for numeric criteria,
  `r_04 = raw_04 / 20` and `r_06 = raw_06 / 10`.
- Base earned points: `b_i = w_i * r_i` for applicable criteria only.
- Effective maximum weight: `e_i = 100 * w_i / W`.
- Effective earned points: `p_i = e_i * r_i`.
- If `W > 0`, unrounded total `T = sum(p_i) = 100 * sum(b_i) / W`.
- Final total is `T` rounded to two decimal places. If `W = 0`, total is absent
  / not calculated, not zero. A storage representation such as null is a local
  convention, not specified by the PDFs.

N/A is an applicability decision, not zero performance. Only 02, 03, 04 and 07
permit it, and only under their listed conditions. No remains an applicable zero
and retains its weight. Missing information, uncertainty, language, or the voice
channel alone does not create a new N/A exception. [C1-C3]

Keep full precision during weighting/redistribution and round the final total;
do not sum rounded displayed contributions. Two decimal places are specified,
but tie-breaking (half-up versus half-even), numeric representation, and display
rounding of criterion/section values are **Open A06**. Do not describe a chosen
programming-language default as an organizer rule. No scorer is implemented here.

With the unchanged initial checklist, 01, 05 and 06 are always applicable, so
`W >= 40`; the source's no-applicable-weight case is a general safeguard relevant
to later configuration. Section headings exist, and G2 requests section results
if sections are configured, but no separate section formula is supplied. [C1-C2;
G2; Open A10]

## 5. Critical errors

The three enumerated categories are: [C1, 08]

1. Insulting the client.
2. Offering a paid service that bypasses the company.
3. Disclosing confidential information.

For category 2, C3 explicitly includes proposing that the client transfer money
to the operator personally for investing, or asking for a personal telephone
number to provide paid private consultation. The offer itself is enough; client
agreement or a completed payment is not required. A telephone-number request
alone is not the whole stated example: its paid/private-service purpose matters.

Record Yes/No separately with category-specific evidence. Neither PDF specifies
an automatic zero, total-score cap, deduction, disqualification, or pass/fail
threshold for a critical flag. Do not invent one. A missing identity check (03)
is not automatically proof of an actual confidentiality disclosure (08); justify
each criterion independently. Criteria 04/05 may reflect their own evidenced
failures, but 08 does not mechanically overwrite them. [C1-C3; G2]

The exact confidentiality boundary and borderline insult/private-service cases
need policy/reviewer calibration where the supplied text does not resolve them.
Record the evidence and uncertainty rather than silently extending the list.

## 6. Evidence and review contract

**Official requirements:** each criterion needs its answer/score, short rationale,
and a supporting utterance/fragment; show points and weight. Cite a specific
utterance or system message and explain what it proves. For an omitted action,
identify the checked region/expected location; for N/A explain the satisfied
condition. Show the total and critical-error flag. Evidence links should reach
the actual message or call fragment. Evaluate the operator; bot/system entries
serve as context. Preserve original timestamps. [C3; G2-G3]

**Local reference conventions**, not new grading criteria:

- Identify the source by dataset hash, `conversation_id`, transcript array index
  (zero-based), original timestamp, speaker, and exact source excerpt. Timestamp
  alone is not a guaranteed unique locator. Preserve the original wording.
- For omissions, record the checked index range and boundary event, and why the
  action was due there. Never fabricate a quotation of a missing action.
- For N/A, cite the specific allowed condition and relevant context, not just the
  label N/A. For broad absence claims such as 08=No, record the inspected scope;
  do not pretend one benign utterance proves the whole conversation was checked.
- For consultation, identify the material client questions, operator answer/next
  step, and any authoritative product/process source used to establish correctness.
  The supplied PDFs are not a complete product-policy knowledge base. [Open A04]
- A voice reference needs the original ISO timestamp and transcript position;
  audio offsets require a verified mapping. Do not treat wall-clock timestamps as
  player offsets or assume the first transcript line is recording time zero.
  Keep signed audio URLs in ignored local data; no links were fetched for this task.
- Record checklist version/source, original response, validation state, and any
  reviewer change with reason and evidence. Recalculate the total if a weighted
  response/applicability changes; preserve original and final results. [G2]

An internal `needs_review`/uncertainty marker is **not** an extra official response
and must not be converted to N/A or an unsupported score. Do not present an
unresolved result as verified. The explicit missing-required-verification => No
instruction for chats still applies when its conditions are established. [C3]

## 7. Open questions and source-grounded boundaries

**Resolved scope:** O3 confirms that the same general eight criteria apply to
calls with spoken-communication adaptations. O5 confirms flexible, saved,
applicable checklists including call-specific configurations. General voice
applicability is no longer an open question; detailed mappings below are partly
resolved, not a reason to exclude calls. Audio assessment is optional, not a
mandatory additional criterion. The default weights, scales and N/A conditions
remain unchanged absent an explicitly configured change.

For an initial voice configuration, map greeting/introduction (01), clarification
(02), verification before protected action (03), substantive/factually correct
advice and necessary next steps (04), specific concern/politeness (05), logical
clear appropriate speech and pause management (06), closing opportunity/farewell
(07), and the same three critical-error categories (08) to spoken turns and
relevant context. Preserve exact raw levels; apply permitted pre-request ending
and interrupted-ending N/A conditions to the call equivalents, not to all calls.
This is the documented operational adaptation of O3, not a newly supplied
word-for-word voice rubric. Do not penalize transcript spelling as operator
speech quality or infer tone from text. Quantitative pause thresholds and other
edge cases remain open. A configuration change must be explicit and versioned,
not a silent channel-dependent formula change. [O3/O5; C1-C3]

| ID | Ambiguity / source | Boundary until resolved; question to confirm |
| --- | --- | --- |
| A01 | Partly resolved: same general checklist applies to voice, with spoken adaptations (O3/O5). | Use the eight criteria for calls; do not blanket-exclude calls or assign channel-wide N/A. Detailed greeting, closing, interruption and borderline spoken-anchor calibration remains open; do not claim an organizer-supplied verbatim voice rubric. |
| A02 | Resolved requirement: audio-based speech quality is optional when useful; C06 covers logic, clarity, appropriate wording and pauses (O3; G4). | Audio is not mandatory for every evaluation. Acoustic claims still need audio; no text-only tone/diction inference or spelling penalties for ASR artifacts. Exact acoustic/pausing severity anchors remain unspecified; no added default numeric criterion. |
| A03 | Chat verification rule versus phone/IVR/off-channel authentication (C3; G2 context roles). | What voice/system evidence counts as confirmed verification? What if it happened before the provided segment? Do not invent that it occurred or silently relax the chat rule for calls. |
| A04 | Partly resolved: C04 checks substantive questions, factual correctness and necessary next steps; no conversation-specific official development answers exist (O4). Protected-action/confidentiality policy remains incomplete (C1/C3). | Seek factual policy evidence, not a promised DEV answer key. Team labels are local judgments, never official Ground Truth. Do not substitute model confidence for evidence or N/A for missing policy. Data 2 is background, not a comprehensive answer/policy key. |
| A05 | Interrupted versus completed dialogue, partial transcripts, and call disconnection (C1, 04/07). | Confirm what evidence establishes no opportunity to close, particularly abrupt recording ends or truncated exports. No automatic N/A for a missing farewell; no new N/A for 01/05/06. |
| A06 | Round final to two decimals, but ties and display rounding unspecified (C2 step 5). | Confirm half-up/half-even and how displayed contributions are rounded. Preserve unrounded arithmetic; label any interim choice explicitly. |
| A07 | Mixed severity, repeated lapses, and undefined "explicit waiting" (C2, 06); no formal priority among overlapping 04 anchors. | Use only listed levels, ground the selected anchor in evidence, and seek reviewer calibration for borderline cases. Do not invent time thresholds, cumulative deductions, or new levels. |
| A08 | Closing phrase does not explicitly formalize AND/OR grouping (C1, 07; C3 example). | Working reading is (summary OR further-help offer) AND farewell. Confirm whether a summary without a farewell can ever be Yes; do not present this grouping as a quoted formal rule. |
| A09 | Client language switching, multiple human operators, first reply/"from the outset" scope (C1, 01/02; G2). | Confirm language choice and whether greeting/initial-information scope resets on handover. Do not create per-message or per-operator averaging without an agreed rule. |
| A10 | Section results are requested only if configured; section aggregation and per-language/channel portfolio aggregation unspecified (G2). | Show per-conversation total per C2. Confirm section scoring and any dataset-level aggregation rather than inventing weighted section totals or benchmark targets. |
| A11 | Some required facts may be unobservable due to missing context/audio; voice timestamps are absolute ISO times, while a player needs recording offsets (C3; G3-G4). | Missing evidence is not a general N/A category. Confirm recording-start/offset mapping and any missing context; do not invent fragment offsets or assume compliant conduct outside the transcript. Record review needs before treating a disputed result as final. |

Submission requirement is now confirmed by O7: the final repository must be public.
The existing repository remains PRIVATE development workspace; do not change its
visibility. Plan a separately reviewed public submission repository only after
later authorization and confidentiality review. No publication, application work,
or external AI/API use is authorized in this documentation pass. See requirements
R07 and the benchmark proposal; no human labels or evaluations have been created.

## 8. DEV integrity verification (not quality evaluation)

LOCAL ONLY original input: `../data/raw/DEV_conversations.json`, SHA256
`98d70ed5e21b7502bec01fd87daee43b6beb670791dfe63bfb469c3919dc29dd`.
The Downloads original and local copy are byte-identical.

Strict JSON parse passed, rejecting duplicate object keys and nonstandard numeric
constants. Envelope: `isSuccess=true`, empty error, `dataset_group_id=DEV`.
`data.total_records=65` equals actual `data.records` length 65. All 65
`conversation_id` values are nonempty, whitespace-clean, and unique; duplicates=0.
Exact language counts: RU=35, KZ=15, EN=15. Channels: `agent chat`=60,
`voice call`=5, matching the composition described in G1. Transcript containers
and required message fields are present. Chat audio fields are empty; all five
voice records contain HTTPS audio links. URL availability/audio content was not
tested. No quality scores, model outputs, or conversation interpretations were
generated. Uniqueness here refers to supplied conversation IDs, not independent
semantic deduplication of dialogue content.

The tracked shared derivative is `../data/shared/DEV_synthetic_60.json`: 60 unique
synthetic chats, RU=30/KZ=15/EN=15, with no real call content/links. It preserves
the original chat records but is not the authoritative full 65-record DEV.
Its `DEV_SYNTHETIC_ONLY` label is not an official API group. Full voice inspection
and the proposed 20-case benchmark require separately obtained LOCAL ONLY data.
