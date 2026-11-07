# Case understanding, deep analysis, and verification

Use this selectively. Official requirements take precedence. Add analytical
depth when it can change the decision, score, or credibility of a major result;
do not turn this document into a checklist of methods to run automatically.
Record live work only in `STATUS.md` and the actual calculations.

## 1. Reverse-engineer the case before coding

Extract the exact question, primary objective, available data, deliverables,
explicit judging criteria, deadline/timezone, submission format, technical
constraints, confidentiality, external-data permissions, and AI/attribution rules.
Record the source page/section and distinguish confirmed facts, interpretations,
and unresolved questions. Ask organizers about consequential ambiguity; continue
unaffected work. Do not invent weights or treat team preferences as hard rules.

For each official criterion, fill the criterion-to-evidence map in `STATUS.md`:
what quality must be demonstrated; evidence needed; calculation/method; assumptions;
validation; likely failure mode; owner and deliverable location. If no rubric is
provided, label the working objective as an interpretation, not an official rubric.

Where rules permit and a specific uncertainty justifies it, examine official
instructions, published prior cases/winning work, primary industry methodology,
or credible benchmarks. Verify the actual claim and applicability. Never infer
unpublished judging expectations or assume a previous winner's method fits.

Define a small set of competing hypotheses, including plausible alternatives.
For each, state why it matters, support and disproof evidence, method, effort,
validation cost, decision impact, and owner. Prioritize by relevance to criteria,
impact, evidence availability, feasibility, and time to a defensible result.
Rank qualitatively unless quantitative weights have a real justification.

## 2. Audit data and make analytical stages reproducible

Before interpreting results, establish the unit of observation, dictionary,
schema/types, row counts, unique IDs, duplicate definition, missingness, units,
time coverage, distributions, and plausible outliers. Separate missing, zero,
not applicable, and invalid values. Do not automatically remove outliers.

For each join, state its keys and expected relationship (one-to-one, many-to-one,
etc.). Check unmatched records, duplicate keys, row multiplication, and totals.
Inspect representative records and explain exclusions or changes in coverage.
Keep original inputs unchanged. Record filenames/version or hashes where useful,
code/cell/function references, input snapshot, parameters, and execution order.

For any claimed funnel, cohort selection, or filtering stage, save locally under
`data/processed/` the actual input and output membership IDs, input/output counts,
rule and parameters, and excluded IDs with explicit reasons. Create stable IDs
from documented source fields or a documented source-row mapping if none exist.
Declare row versus unique-entity counts. Reconcile kept + excluded membership to
the input and check that reported counts match the saved membership.
For overlapping exclusions, record flags or a documented reason precedence.
Never reconstruct a missing intermediate stage from its reported count.
Label unverifiable historical stages as unverifiable.

Describe validation coverage honestly: all records/stages, or which subset was
checked, how selected, and what remains unchecked. A few spot checks do not
constitute exhaustive validation.

## 3. Investigate consequential questions deeply

For each prioritized question:

1. State the decision and competing explanations; specify the population,
   outcome/metric, units, denominator, period, and relevant comparison.
2. Select appropriate data and the simplest credible baseline. Choose the method
   for the question and document assumptions before interpreting its output.
3. Execute calculations and inspect results. Check representative records,
   reconciliation, formula logic, and unexpected results before telling a story.
4. Challenge the result: selection effects, confounding, changing definitions,
   missingness, influential outliers, subgroup or time instability, and alternative
   explanations. Check uncertainty and sensitivity where they affect the decision.
5. Assess magnitude and practical relevance, not just statistical significance.
   State limitations, what the evidence does and does not establish, and what
   decision or recommendation follows. Record evidence and affected deliverables.

Use descriptive/distributional analysis first where appropriate. Confidence
intervals, tests, regression, interactions, segmentation, and time-series methods
are options, not requirements. Respect dependence and sampling assumptions;
avoid cherry-picking segments or significant tests. Mark exploratory testing and
address multiple comparisons when material. A full dataset is not automatically
representative of the population or future decisions. Observational association
does not establish causality without a defensible identification strategy.

### Conditional methods

- **Prediction:** define target, prediction time, available features, official
  metric and direction, and a simple benchmark. Use a split respecting time,
  repeated entities, and deployment conditions. Learn preprocessing and feature
  selection inside training folds. Compare models on the same valid splits;
  handle imbalance when relevant. Tune without final-test contamination, inspect
  errors and subgroup performance, and assess generalization and complexity.
  Repeated leaderboard feedback is not an independent final evaluation.
- **Optimization:** write objective, variables, units, domains, and constraints;
  start with a feasible baseline. Independently verify returned feasibility,
  tolerances, objective calculation, and sensitivity. Record solver termination,
  bounds/gap if available. Say "best feasible found" unless optimality is supported.
- **Business/financial analytics:** specify the decision and its drivers. Compare
  alternatives, operational constraints, implementation risks, and defensible
  impact ranges. Write the exact mathematical relationship, time basis, units,
  denominators, cash-flow timing, signs, and assumptions. Check duplicated costs
  or revenues, reconcile components, and verify thresholds by recomputation and
  sensitivity. If relevant, check an IRR against the NPV equation and possible
  nonunique solutions. A spreadsheet's displayed value is not validation.

## 4. Independent verification and authoritative evidence

Use the single ledger in `STATUS.md`:
**claim -> value/unit -> source -> calculation -> verification -> limitation ->
decision implication -> downstream artifact**.

Finding type and verification are separate: a correctly computed model estimate
is still an estimate. Types include observed result, model estimate, assumption,
exploratory hypothesis, unsupported claim, and rejected conclusion. Verification
states are unverified, partially verified, verified, failed, and stale.

For major findings, reproduce from source inputs with a separate calculation
method or independent reviewer where practical. Record the actual check, result,
coverage, reviewer, and source/calculation version. If independent verification
is impractical, disclose this and the remaining uncertainty; do not imply it ran.
Use appropriate checks: totals, row samples, formulas, units, denominator logic,
threshold substitutions, scenario consistency, sensitivity, outlier influence,
sampling/comparison validity, leakage, and causal interpretation.

For consequential external facts, record publisher, date/version, URL/page,
the precise supporting content, access/check date, and relevance. Track evidence
as verified, partially verified, inaccessible, or unsupported. Prefer primary
materials. An inaccessible source or an existing URL is not a verified claim.
Do not invent citations or claim to have inspected unseen content.

An evidence ID refers to an exact definition, input, calculation, and scenario.
Use stable IDs and version/review dates. When any dependency changes, mark the
entry stale and identify all consumers; rerun and reverify before release.
Store sensitive calculations/figures locally; Git sharing needs separate review.

## 5. Integrate actual deliverables and decide when to stop

Design the required deliverable structure early, then populate it from evidence.
Use current verified ledger entries for consequential final claims; label model
estimates and assumptions explicitly. Do not introduce new results in slides.
Export approved tables/charts directly from calculations where useful. A draft
outline, empty workbook, or saved filename is not a completed deliverable.

At release, review each major claim against its evidence ID and reconcile scope,
population, scenario, units, rounding, amounts, period, filters, selected options,
filenames, and actual sheet names across code, workbooks, charts, and presentation.
An upstream change marks affected artifacts stale until refreshed. Unsupported or
rejected claims do not become final recommendations. State material limitations.

Rerun the critical analytical path from original inputs. Open/recalculate/render
the actual final files using suitable available tools; check references, required
tabs/pages, file types, names, size limits, and submission format. Do not report
an opening/rendering check that was not performed. Humans approve the final
interpretation and submission. Keep a working fallback and verify receipt.

Timebox uncertain investigations (initially about 45–60 minutes, adaptable).
Continue only for a credible route to changing the decision/score, resolving
material uncertainty, or repairing a methodological weakness. Review the cost
of validation and integration as well as analysis. Reassess blocked tasks;
protect the finalization window in `README.md`. Deep analysis must improve an
existing candidate submission, not prevent having one.
