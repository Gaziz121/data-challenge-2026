# Operating instructions

- Inspect existing instructions, `README.md`, and the local `STATUS.md` before
  acting. Preserve current work. The case and organizer rules outrank generic
  methodology. Never invent case facts, datasets, results, or judging weights.
  If the status record is absent, obtain it from the integration owner through
  an approved handoff; do not fabricate progress or create a competing ledger.
- Run `python3 -B src/git_preflight.py`; follow `GIT_WORKFLOW.md`. Distinguish
  working files, local commits, cached remote refs, and actual GitHub state.
  Without a successful authorized fetch, do not claim remote freshness. A Git
  blocker must not block unrelated read-only analysis; label its input snapshot.
- Do not blindly pull, reset, clean, stash, rebase, merge divergent history,
  force-push, or overwrite work. Ask before consequential recovery operations.
  Remote creation and uploads require explicit approval of owner, visibility,
  and exact reviewed files. A private repository does not authorize data sharing.
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
- Maintain the single evidence ledger in `STATUS.md`. Separate finding type from
  verification status, record limitations, and connect evidence to decisions.
  If a calculation changes, invalidate affected evidence and downstream artifacts.
- Final claims must reference current verified evidence IDs and the actual
  source calculation. Reconcile scope, units, scenarios, figures, filenames, and
  sheet names across files. Verify actual files open/render and satisfy the brief.
- Use one owner per notebook/workstream and one integration owner. Parallel work
  needs shared definitions, distinct scope, expected outputs, and review. Do not
  create agents just because they are available; do not merge contradictions by
  consensus. Preserve unresolved uncertainty.
- Keep documentation in the existing linked files. Record completed work,
  verified results, unresolved issues, authoritative files, and the next step in
  `STATUS.md`; distinguish executed work from plans and untested procedures.
- Protect finalization time. Humans review consequential decisions, conclusions,
  confidentiality, and submission. Report actual accomplishments and limitations.
