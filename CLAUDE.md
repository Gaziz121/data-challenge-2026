# Operating instructions

Team onboarding and work ownership: [TEAM_START_HERE.md](TEAM_START_HERE.md).
Use it as the single setup entry point; retain the discovery and safety protocol
below. Historical reports are evidence for their named snapshots, not live status.

Owner decision, November 7, 2026: the existing repository is intentionally PUBLIC.
Reviewed public-safe documentation publication is authorized. Do not change
visibility, permissions or rulesets; do not upload restricted data, secrets or
reviewer outputs. Earlier PRIVATE-only statements describe the prior sharing
scope and do not override this explicit owner decision.

## Mandatory Workspace Discovery and Source-of-Truth Protocol

- **Local workspace is not GitHub.** Git-tracked files are only a subset of files
  available locally. A file absent from GitHub may exist on this Mac. Never call
  a material missing solely because it is absent from Git, search results that
  respect `.gitignore`, or the shared 60-chat dataset.
- **At each session start and before material-dependent tasks:** verify the local
  project root; read `README.md`, `TEAM_STATUS.md`, `PROJECT_FILE_MAP.md`, and
  `STATUS.md` if present. Inspect relevant local directories including ignored
  `case/`, `data/`, `src/`, `notebooks/`, `outputs/` and `deliverables/`. Use actual
  filesystem enumeration (`Path.iterdir/rglob` or `ls -la`), not only `git ls-files`
  or default `rg --files`. List paths/metadata rather than confidential contents.
- Locate originals, datasets, specifications and prior outputs, then read the
  actual sources needed. Before declaring absence or requesting materials again,
  check the inventory, expected local locations, and applicable Downloads paths.
  Report which locations were checked. Do not dump transcript content, signed
  links, credentials or restricted material into logs or Git output.
- **Requirements:** original local organizer PDFs and official clarifications
  are authoritative. Tracked team-safe PDF copies preserve visible pages but
  omit embedded actions/metadata. Internal specs interpret those sources. Report
  conflicts; do not silently replace an official requirement with an assumption.
- **Data:** `data/raw/DEV_conversations.json` is the authoritative full 65-record
  original. `data/shared/DEV_synthetic_60.json` is a partial derivative containing
  60 synthetic chats and no real calls. Never substitute 60 for 65 or infer that
  the five calls do not exist because they are absent from GitHub.
- **Code:** the local working tree contains actual available files; GitHub holds
  the latest successfully synchronized commits. Neither is automatically newer.
  Check branch, dirty/untracked work, upstream, and successfully fetched refs.
- **Inventory maintenance:** whenever important materials are created, moved,
  replaced, or change sharing status, update `PROJECT_FILE_MAP.md` as needed.
  If it disagrees with disk/Git, inspect and correct it and report the discrepancy.
  Keep paths/status/purpose concise; never put secrets or personal data in it.
- A fresh clone intentionally lacks LOCAL ONLY materials and `STATUS.md`.
  Identify the exact missing local file and obtain it from the integration owner
  via an organizer-permitted handoff. Use tracked `TEAM_STATUS.md` as a sanitized
  snapshot, not a substitute evidence ledger. Do not fabricate missing originals
  or pretend every teammate has local-only files.

## Analysis, safety and collaboration

- Preserve current work. The case and organizer rules outrank generic methodology.
  Never invent case facts, datasets, results, judging metrics or weights.
- Run `python3 -B src/git_preflight.py`; follow `GIT_WORKFLOW.md`. Distinguish
  working files, local commits, cached remote refs, and actual GitHub state.
  Without a successful authorized fetch, do not claim remote freshness. A Git
  blocker must not block unrelated read-only analysis; label its input snapshot.
- Do not blindly pull, reset, clean, stash, rebase, merge divergent history,
  force-push, or overwrite work. Ask before consequential recovery operations.
  Remote creation/uploads require authorization for the destination and content.
  Current authorization permits reviewed public-safe documentation in the existing
  PUBLIC repository; do not ask again for that same approved scope. New sensitive
  material or additional publication scope needs a separate decision. Do not
  change repository visibility/settings or redistribute restricted private history.
- Before coding, use the reverse-engineering procedure in `ANALYSIS.md`. Confirm
  the objective, scoring, deliverables, deadline, AI rules, and confidentiality.
  Separate official requirements from justified analytical preferences. Prioritize
  consequential questions; do not apply invented exclusion gates.
- Use `ANALYSIS.md` for deep investigation and case-appropriate methods. Do not
  assume ML or add tools, dependencies, pipelines, or orchestration speculatively.
- Preserve raw inputs. Record versions, definitions, filters, units, and run steps.
  Verify keys, missingness, join cardinality, sample selection, and reconciled
  counts/totals. Never silently drop observations or double-count quantities.
- For any claimed filtering stage, save exact input/output IDs, counts, rules,
  and exclusion reasons locally. Report only stages actually executed. Label
  selective validation as selective, with its coverage and unchecked remainder.
- Verify consequential numbers from source inputs: exact formula, denominator,
  independent calculation or reviewer where practical, and relevant sensitivity.
  Plausible outputs, displayed spreadsheet values, and AI agreement are not proof.
- Prevent target/future-information leakage and invalid validation splits when
  prediction is relevant. Fit preprocessing on training data only; keep final
  test data out of selection. Do not confuse association with causation,
  significance with practical impact, or a feasible solution with a proven optimum.
- Verify consequential external facts against accessible primary evidence where
  permitted. Record claim-specific source verification; a URL alone is not proof.
- Maintain the local evidence ledger in `STATUS.md` where available; update the
  sanitized `TEAM_STATUS.md` snapshot when shared milestones materially change.
  Do not put restricted evidence in the snapshot. Separate finding type from
  verification status, record limitations, and connect evidence to decisions.
  If a calculation changes, invalidate affected evidence and downstream artifacts.
- Final claims must reference current verified evidence IDs and the actual
  source calculation. Reconcile scope, units, scenarios, figures, filenames, and
  sheet names across files. Verify actual files open/render and satisfy the brief.
- Use one owner per notebook/workstream and one integration owner. Parallel work
  needs shared definitions, distinct scope, expected outputs, and review. Do not
  create agents just because they are available; do not merge contradictions by
  consensus. Preserve unresolved uncertainty.
- Keep documentation in the existing linked files and persistent inventory. Record completed work,
  verified results, unresolved issues, authoritative files, and the next step in
  `STATUS.md`; distinguish executed work from plans and untested procedures.
- Protect finalization time. Humans review consequential decisions, conclusions,
  confidentiality, and submission. Report actual accomplishments and limitations.
