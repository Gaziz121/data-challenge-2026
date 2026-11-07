# Offline DEV conversation review

A read-only transcript viewer and separate manual-label form. Python 3.9+ builds
one self-contained HTML file using only the standard library. The generated page
has no external assets, APIs, server, browser autosave, or evaluation-engine imports.
It is a calibration aid, separate from `src/cqa/` and its outputs.

The integrated localhost application serves this same independent page at
`/human-review/`. Its only shared UI source is `transcript.js`, a read-only renderer
with no labels, scoring, storage, network or engine imports. The builder still
embeds everything into one offline HTML file. AI evaluation results never enter
this page or its `team_human` exports.

From the repository root:

```sh
python3 -B tools/dev_review/build.py
open outputs/dev_review/index.html
```

On other systems, double-click `outputs/dev_review/index.html` or open it with a
modern browser. No server is required. Rebuild when the dataset or viewer changes;
the generated page contains a snapshot of the dataset. Generated HTML and human
label exports belong under the ignored `outputs/dev_review/` directory. The HTML
includes the synthetic transcripts; treat it with the same sharing rules as the
source dataset. The builder's output is restricted to HTML under that directory.

## Review and save independent assessments

1. Filter by RU/KZ/EN, search conversation IDs, or use the selector and Previous /
   Next. The transcript pane includes every message, including bot and system
   context. Its text is read-only; original order and wording are preserved.
2. Enter your reviewer name or ID and click **Start blank review**. All eight
   criteria start unscored. Each reviewer should start with a fresh page, use their
   own ID, and save their own files. No other reviewer's labels are loaded unless
   you explicitly choose their JSON file. The reviewer ID locks for that session.
3. Enter your own allowed response/raw score, justification, and comma-separated
   zero-based evidence indexes (for example, `0, 9, 11`). Click the generated
   **Message** links to jump to those turns. Use the scope/reference field for
   checked index ranges, omissions, external policy sources, and uncertainty.
   Explain the stated applicability condition when selecting N/A. No N/A option
   is offered for criteria 01, 05, 06, or 08. For 08, Yes means a critical violation.
4. Click **Save JSON / resume file** regularly and check your browser's Downloads.
   Move the downloaded `team_human-<reviewer>-<timestamp>.json` to your chosen local
   labels folder, such as `outputs/dev_review/labels/`. Downloads do not write to
   the dataset. **Resume your saved JSON** restores that review and its reviewer ID
   after checking dataset/rubric hashes and exact evidence. It replaces the current
   session only after a warning if that session already has entries.
5. **Export CSV** produces one row per criterion per touched conversation, suitable
   for side-by-side human comparison. CSV cannot be resumed; keep the JSON too.
   Start another independent review by reopening/reloading the page without
   importing labels. Nothing is stored automatically between page loads.

Navigation keeps drafts within the current tab. Closing/reloading without saving
can lose them; the browser shows an unsaved-work prompt when supported. Download
buttons request files from the browser; verify they actually reached Downloads.
The viewer has no accounts, central collection, automatic merging, or scoring.

## Inspected source schema and provenance

`data/shared/DEV_synthetic_60.json` uses the envelope
`{error, isSuccess, data: {dataset_group_id, source_dataset_group_id, total_records,
records}}`. Each record contains `conversation_id`, `channel`, `language`,
`transcript`, and `audio_url`. Each of its 882 messages contains exactly
`timestamp`, `speaker`, and `text`. There are 60 unique synthetic chats: RU=30,
KZ=15, EN=15; channel is `agent chat`. This partial dataset contains no calls.

There are **no original message IDs**. The UI says “not provided” and exposes
zero-based transcript indexes as local locators, never invented original IDs.
Timestamps such as `00:00` remain verbatim; they are not converted to dates or
audio offsets. Speaker labels and color distinguish client/operator/bot/system.
The dataset SHA256 is
`836b1cd80a70f4fb901f3d7a8aacfc227ecc523a8a4d29631ff91bf88a399c17`.

`rubric.json` is a small, separately versioned human-review reference drawn from
`case/CQA_SCORING_SPEC.md` sections 2–3. It preserves the eight allowed response
sets, base weights, discrete anchors, N/A conditions, and the distinction for 08.
It documents the team's closing-rule interpretation. It is not an answer key and
does not run or import the production engine's checklist or scoring code. No
aggregate score, suggestion, AI judgment, or prefilled human label is generated.

## Export contract

JSON uses schema `dev-team-human-1`, `label_source: "team_human"`, and
`official_ground_truth: false`. It records reviewer ID, creation/export times,
dataset path/hash/group, and rubric version/hash. Only conversations with manual
entries are exported; each includes all eight criteria. Unscored responses are
`null`, distinct from a raw numeric zero and from `"N/A"`. Binary values are
`"yes"` / `"no"`. Each criterion includes justification, scope note, and evidence
objects with conversation-local `transcript_index`, original ID (`null` here),
exact timestamp, speaker, and text. The assessment carries its conversation ID,
language/channel, and last-edit timestamp.

An assessment is marked `complete` only when every response, justification, and
either evidence or scope note is present; otherwise it remains `draft`. This is a
form-completeness check, not verification of a reviewer's judgment. Malformed
message indexes block export. JSON resume rejects other sources, invalid response
levels/N/A, duplicate conversations, changed hashes, and altered evidence.

CSV repeats provenance and reviewer identity on every row, with `evidence_json`
for structured references. It uses UTF-8 with BOM, quoted cells and CRLF row
endings. Formula-like free text gets a leading apostrophe for safe spreadsheet
opening; the JSON keeps exact reviewer text. Blank scores remain empty CSV cells.
Files are team judgments, **never official Ground Truth**.

## Verification

```sh
python3 -B -m unittest discover -s tests -p test_dev_review.py
node tests/test_dev_review.cjs
```

Python checks all 60 records / 882 messages against the original, safe JSON
embedding, and output isolation. Node (only needed to run these checks) tests
blank independent reviews, JSON resume, validation, zero versus unscored, and CSV
escaping with fictional fixtures, never real-conversation quality labels.

Browser-tested on November 7, 2026: `p1-ru-001`, `p1-kz-001`, `p1-en-001`
(12 turns each), with exact rendered text/order/timestamps, all four roles, and
blank responses. Also checked navigation, draft separation, evidence jumps,
actual JSON/CSV downloads, reload starting blank, and JSON resume. A clearly
marked UI-test note was used with every response left unscored; it is not a human
assessment. All tests leave the dataset unchanged. No quality/accuracy evaluation
was performed.

Browser QA used a temporary loopback-only static server. The browser tool's URL
policy blocks `file://` navigation, so direct-file opening was not browser-tested;
the page has no fetches or external resources. If your browser restricts local
files, this optional local fallback serves only the generated viewer directory:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory outputs/dev_review
```

Open `http://127.0.0.1:8766/` and stop the temporary server with Ctrl+C when done.
