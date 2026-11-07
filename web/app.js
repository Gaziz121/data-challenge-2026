/* Integration UI: consumes the backend contracts and never computes scores itself. */
(function () {
  "use strict";
  function responseText(decision, criterion) {
    if (decision.response === "N/A") return "N/A — not applicable";
    if (criterion.kind === "discrete") return `${decision.response} / ${Math.max(...criterion.levels)}`;
    if (criterion.kind === "critical") return decision.response === "yes" ? "Yes — critical violation flagged" : "No listed violation flagged";
    return decision.response === "yes" ? "Yes" : "No";
  }
  // Display category for data-verdict only (equality checks on the raw response; no score arithmetic).
  function verdictOf(decision, criterion) {
    if (decision.response === "N/A") return "na";
    if (criterion.kind === "critical") return decision.response === "yes" ? "flag" : "clear";
    if (criterion.kind === "discrete") return decision.response === 0 ? "no" : decision.response === Math.max(...criterion.levels) ? "yes" : "partial";
    return decision.response === "yes" ? "yes" : "no";
  }
  function permittedResponses(criterion) {
    const values = criterion.kind === "discrete" ? criterion.levels.slice() : ["yes", "no"];
    if (criterion.na_condition !== null && criterion.na_condition !== undefined) values.push("N/A");
    return values;
  }
  function turnNumbers(conversation) {
    const map = new Map();
    for (const m of conversation?.messages || []) map.set(m.message_id, m.source_index + 1);
    return map;
  }
  function runLabel(run) {
    if (run.provider === "replay") return "REPLAY of a recorded genuine model reply — no new model call; mock-flagged, never submittable";
    return run.is_mock ? "MOCK FIXTURE — not a quality judgment" : "LLM evaluation — semantic accuracy not independently verified";
  }
  function factory(container) {
    const doc = container.ownerDocument;
    return function el(tag, text, cls) {
      const node = doc.createElement(tag);
      if (text !== undefined) node.textContent = text;
      if (cls) node.className = cls;
      return node;
    };
  }
  // Score hero: backend strings shown as-is (score.total_score, status, critical flag, run metadata).
  function scoreHero(result, el) {
    const score = result.score, run = result.run, critical = result.checklist.criteria.find(c => c.kind === "critical");
    const hero = el("section", undefined, "cqa-score-hero");
    hero.dataset.critical = String(Boolean(score.critical_violation));
    const total = el("p", undefined, "cqa-hero-total");
    total.append(el("span", score.total_score ?? "not calculated", "cqa-hero-value"), el("span", "/ 100", "cqa-hero-scale"));
    const status = el("span", result.status, "cqa-pill"); status.dataset.status = result.status;
    const flag = el("span", `${score.critical_violation ? "Critical violation flagged" : "No critical violation"}${critical ? " · " + critical.criterion_id : ""}`, "cqa-pill");
    flag.dataset.critical = String(Boolean(score.critical_violation));
    const kind = el("span", run.provider === "replay" ? "Replay" : run.is_mock ? "Mock fixture" : "LLM", "cqa-pill");
    kind.dataset.status = run.is_mock ? "mock_only" : "live";
    const badges = el("div", undefined, "cqa-hero-badges"); badges.append(status, flag, kind);
    hero.append(el("p", "Total score", "cqa-hero-label"), total, badges,
      el("p", `${run.provider} · ${run.model_returned} · ${run.latency_ms} ms · checklist ${result.checklist.version}`, "cqa-hero-run"));
    return hero;
  }
  // Base → effective weight; "redistributed" comes from the backend applicability flags, not from comparing numbers.
  function weightsRow(score, redistributed, el) {
    const row = el("p", undefined, "meta cqa-weights");
    row.append(el("span", `Base weight ${score.base_weight}`), el("span", undefined, "cqa-arrow"),
      el("span", `Effective weight ${score.effective_weight}`), el("span", `Points ${score.earned_points}`));
    if (score.applicable === false) row.append(el("span", "not applicable — weight redistributed", "cqa-tag"));
    else if (redistributed) row.append(el("span", "redistributed", "cqa-tag"));
    return row;
  }
  function renderResult(result, container, summary, onEvidence) {
    const el = factory(container);
    const mock = result.run.is_mock;
    summary.textContent = `${runLabel(result.run)}\n` +
      `Total${mock ? " (fixture/replay)" : ""}: ${result.score.total_score ?? "not calculated"} / 100 · Critical flag: ${result.score.critical_violation ? "yes" : "no"}\n` +
      `${result.run.provider} · ${result.run.model_returned} · ${result.run.latency_ms} ms · ${result.status}\n` +
      `Checklist: ${result.checklist.version} · Usage: ${JSON.stringify(result.run.usage)}`;
    container.replaceChildren(scoreHero(result, el));
    const scores = new Map(result.score.criteria.map(c => [c.criterion_id, c]));
    const definitions = new Map(result.checklist.criteria.map(c => [c.criterion_id, c]));
    const turns = turnNumbers(result.conversation);
    const redistributed = result.score.criteria.some(c => c.applicable === false);
    function evidenceList(evidence, parent) {
      for (const reference of evidence) {
        let target = parent;
        if (reference.kind !== "quote") {
          target = el("div", undefined, "cqa-checked"); target.dataset.kind = reference.kind;
          target.append(el("p", reference.kind === "omission" ? "Checked part of the conversation — expected action not found" :
            "Checked part of the conversation", "cqa-block-label"));
          parent.append(target);
        }
        const links = el("div", undefined, "evidence-links");
        const ids = reference.kind === "quote" ? [reference.message_id] : [reference.start_message_id, reference.end_message_id];
        const label = ids.map(id => turns.has(id) ? `turn ${turns.get(id)}` : id).join("–");
        const button = el("button", reference.kind === "quote" ? `Message ${ids[0]}${turns.has(ids[0]) ? " · " + label : ""}` :
          `${reference.kind}: ${ids[0]}–${ids[1]}${turns.size ? " · " + label : ""}`);
        button.type = "button";
        button.dataset.startMessageId = ids[0];
        button.dataset.endMessageId = ids[ids.length - 1];
        button.onclick = () => onEvidence(reference);
        links.append(button); target.append(links, el("p", reference.explanation, "notice"));
        if (reference.quote !== null) target.append(el("blockquote", reference.quote));
      }
    }
    for (const decision of (result.validated_evaluation || result.model_evaluation).decisions) {
      const criterion = definitions.get(decision.criterion_id), score = scores.get(decision.criterion_id);
      const card = el("article", undefined, "result-card"); card.dataset.criterionId = criterion.criterion_id;
      card.dataset.verdict = verdictOf(decision, criterion); card.dataset.kind = criterion.kind;
      card.dataset.needsReview = String(Boolean(decision.needs_review));
      card.dataset.critical = String(criterion.kind === "critical" && decision.response === "yes");
      card.append(el("h3", `${criterion.criterion_id} · ${criterion.title}`), el("p", responseText(decision, criterion), "raw"));
      card.append(criterion.kind === "critical" ? el("p", "Separate flag — no numerical deduction", "meta") : weightsRow(score, redistributed, el));
      card.append(el("p", decision.rationale));
      if (decision.violation_categories?.length) card.append(el("p", `Violation categories: ${decision.violation_categories.join(", ")}`, "cqa-violations"));
      if (decision.na_reason) card.append(el("p", `N/A reason: ${decision.na_reason}`, "na-reason"));
      card.append(el("p", criterion.na_condition ? `N/A allowed only when: ${criterion.na_condition}` : "N/A not permitted.", "notice"));
      if (decision.needs_review) card.append(el("p", `Needs review: ${decision.review_reason}`, "review"));
      evidenceList(decision.evidence, card);
      if (["na", "no", "clear"].includes(card.dataset.verdict) && !decision.evidence.some(e => e.kind !== "quote"))
        evidenceList(decision.atomic_checks.flatMap(check => check.evidence).filter(e => e.kind !== "quote"), card);
      const atomic = el("details"); atomic.append(el("summary", `Atomic rubric checks (${decision.atomic_checks.length})`));
      const questions = new Map(criterion.questions.map(q => [q.question_id, q.question]));
      for (const check of decision.atomic_checks) {
        const item = el("div");
        item.append(el("p", `${questions.get(check.question_id)} — ${check.answer}`), el("p", check.rationale, "notice"));
        evidenceList(check.evidence, item); atomic.append(item);
      }
      card.append(atomic); container.append(card);
    }
    if (result.evidence_repairs?.length) container.append(el("p",
      `${result.evidence_repairs.length} citation formatting repairs are recorded with exact source spans. Original AI wording is preserved in the JSON/audit.`, "notice"));
    const audit = el("details", undefined, "audit"); audit.append(el("summary", "Run audit and review findings"));
    audit.append(el("pre", JSON.stringify({evaluation_id: result.evaluation_id, run: result.run,
      check_outcomes: result.check_outcomes, audit: result.audit, revision_history: result.revision_history,
      evidence_repairs: result.evidence_repairs, original_model_evaluation: result.model_evaluation}, null, 2)));
    container.append(audit);
  }
  function renderFailure(diagnostic, container, summary) {
    const el = factory(container);
    summary.textContent = `${diagnostic.run.is_mock ? "MOCK" : "REAL OPENAI RESPONSE"} — VALIDATION FAILED\n` +
      `No accepted score or total. Original AI decisions below are unvalidated.\n` +
      `${diagnostic.run.provider} · ${diagnostic.run.model_returned} · ${diagnostic.run.provider_latency_ms} ms\n` +
      `Usage: ${JSON.stringify(diagnostic.run.usage)} · Checklist: ${diagnostic.checklist.version}`;
    container.replaceChildren();
    const report = el("section", undefined, "cqa-failure-report"), issues = el("ul", undefined, "cqa-issues");
    for (const issue of diagnostic.issues) issues.append(el("li", `${issue.criterion_id || "Schema"}: ${issue.message}`, "error"));
    report.append(el("h3", "Validation failed — no score was produced"),
      el("p", "Why: the engine refuses to score output whose facts, evidence or rules do not validate. " +
        "In the official export this conversation becomes status=error with the reason below — never a zero score.", "notice"),
      issues, el("p", diagnostic.run.is_mock && diagnostic.checklist.decision_path === "atomic_first" ?
        "Next step: mock fixtures cannot supply the atomic facts this checklist requires (by design). For a scored run choose Replay (recorded reply: p1-ru-001 with checklist 2026-11-07.v5) or a legacy checklist (v2/v3) with Mock." :
        "Next step: inspect the original decisions below or download the diagnostic JSON, then re-evaluate. Rejected output is never repaired silently or scored.", "cqa-next-step"));
    container.append(report);
    const raw = diagnostic.original_model_output;
    const legacy = raw && typeof raw === "object" && Array.isArray(raw.decisions) ? raw.decisions : [];
    const atomic = raw && typeof raw === "object" && Array.isArray(raw.criteria) ? raw.criteria : [];
    const states = new Map((diagnostic.criterion_reviews || []).map(r => [r.criterion_id, r.state]));
    for (const decision of legacy.length ? legacy : atomic) {
      const card = el("article", undefined, "result-card rejected-card");
      card.dataset.criterionId = decision.criterion_id; card.dataset.verdict = "rejected";
      const definition = diagnostic.checklist.criteria.find(c => c.criterion_id === decision.criterion_id);
      const response = legacy.length ? decision.response : decision.judgment?.response ?? "derived from atomic facts";
      card.append(el("h3", `${decision.criterion_id} · ${definition?.title || "Original AI decision"}`),
        el("p", `Original response: ${String(response)} — no accepted score${states.has(decision.criterion_id) ? " · state " + states.get(decision.criterion_id) : ""}`, "raw"),
        el("p", String(decision.rationale || decision.judgment?.rationale || "")));
      if (decision.na_reason) card.append(el("p", `Original N/A reason: ${decision.na_reason}`));
      const details = doc(container).createElement("details");
      details.append(el("summary", "Original atomic checks and evidence (unvalidated)"), el("pre", JSON.stringify(decision, null, 2)));
      card.append(details); container.append(card);
    }
  }
  function doc(container) {return container.ownerDocument;}
  function renderComparison(view, checklist, container) {
    const el = factory(container);
    container.replaceChildren();
    const original = view.original_score, revised = view.revised_score;
    const totals = el("div", undefined, "cqa-compare-totals");
    totals.append(el("p", `Original total: ${original.total_score ?? "not calculated"} · critical ${original.critical_violation ? "yes" : "no"}`, "raw"));
    if (revised) totals.append(el("span", undefined, "cqa-arrow"),
      el("p", `Revised total: ${revised.total_score ?? "not calculated"} · critical ${revised.critical_violation ? "yes" : "no"}`, "raw cqa-revised"));
    else totals.append(el("p", "No reviewer change applied; the original total stands.", "notice"));
    container.append(totals);
    const table = el("table", undefined, "comparison");
    const head = el("tr"); for (const h of ["Criterion", "Original", "Revised", "Weight"]) head.append(el("th", h));
    table.append(head);
    for (const criterion of checklist.criteria) {
      const row = el("tr");
      const a = view.original_responses[criterion.criterion_id], b = view.revised_responses[criterion.criterion_id];
      if (a !== b) row.dataset.changed = "true";
      row.append(el("td", `${criterion.criterion_id} · ${criterion.title}`), el("td", String(a)),
        el("td", String(b), a === b ? undefined : "changed"), el("td", criterion.kind === "critical" ? "flag" : String(criterion.weight)));
      table.append(row);
    }
    container.append(table);
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {responseText, renderResult, renderFailure, permittedResponses, renderComparison, runLabel};
    return;
  }

  const $ = id => document.getElementById(id);
  const el = factory(document.body);
  let records = [], config, checklists = [], current = null, pasted = null, result = null, rejected = null;
  let busy = false, sequence = 0, editing = null;
  async function api(path, options) {
    const response = await fetch(path, options);
    const value = await response.json();
    if (!response.ok) {const error = new Error(value.error || "Local request failed."); error.details = value; error.status = response.status; throw error;}
    return value;
  }
  function post(path, body, headers = {}) {
    return api(path, {method: "POST", headers: {"Content-Type": "application/json", ...headers}, body: JSON.stringify(body)});
  }
  function feedback(text, error = false) {$("feedback").textContent = text; $("feedback").className = error ? "status error" : "status";}
  function selectedChecklist() {
    const [checklist_id, version] = $("checklist").value.split("\u0000");
    return checklist_id ? {checklist_id, version} : null;
  }
  function updateMode() {
    const provider = $("provider").value, mock = provider !== "openai";
    $("mode").className = mock ? "mode" : "mode live";
    $("mode").textContent = provider === "mock" ? "MOCK mode — fixed test fixtures, not AI quality judgments. Atomic checklists (v4–v6) reject mock facts by design." :
      provider === "replay" ? "REPLAY — re-validates a recorded genuine reply (p1-ru-001, checklist v5). No new model call." :
      "OpenAI selected — only a successful provider response is an LLM evaluation.";
    $("model").disabled = mock || busy;
    const ready = mock || (config?.openai_key_present && (config?.external_synthetic_allowed || config?.external_authorized_allowed) &&
      config?.live_calls_remaining !== 0 && $("model").value.trim());
    $("evaluate").disabled = busy || !(current || pasted) || !ready;
    if (!mock && !ready) feedback(config?.live_calls_remaining === 0 ? "Live request budget is exhausted. No additional paid request can be sent." :
      "OpenAI requires authorized server credentials, an external-export opt-in and an explicit model. No request has been sent.");
  }
  function clearResult() {
    result = null; rejected = null; $("download").disabled = true;
    $("results").replaceChildren(); $("run-summary").textContent = "No evaluation for this selection yet.";
    renderAppealsPanel(null);
  }
  function showConversation(conversation) {
    current = conversation; pasted = null;
    $("conversation-title").textContent = conversation.conversation_id;
    $("conversation-meta").textContent = `${conversation.language} · ${conversation.channel} · ${conversation.messages.length} messages · source order`;
    window.CqaTranscript.render($("transcript"), conversation);
  }
  async function selectConversation() {
    const requestSequence = ++sequence;
    current = null; pasted = null; clearResult(); updateMode(); $("transcript").replaceChildren();
    const id = $("conversation").value;
    if (!id) return;
    try {
      const loaded = await api("/api/conversations/" + encodeURIComponent(id));
      if (requestSequence !== sequence) return;
      showConversation(loaded);
      feedback("Transcript loaded. Evaluation has not run."); updateMode(); loadHistory();
    } catch (error) {if (requestSequence === sequence) feedback(error.message, true);}
  }
  function filter() {
    const filtered = records.filter(r => !$("language").value || r.language === $("language").value);
    $("conversation").replaceChildren(...filtered.map(r => new Option(`${r.conversation_id} · ${r.language}`, r.conversation_id)));
    $("conversation").disabled = !filtered.length;
    selectConversation();
  }
  function jump(reference) {
    if (!current) return;
    const start = reference.kind === "quote" ? reference.message_id : reference.start_message_id;
    const end = reference.kind === "quote" ? start : reference.end_message_id;
    const a = current.messages.findIndex(m => m.message_id === start), b = current.messages.findIndex(m => m.message_id === end);
    $("transcript").querySelectorAll(".highlight").forEach(node => node.classList.remove("highlight"));
    for (let i = a; i <= b; i++) $(`message-${i}`)?.classList.add("highlight");
    $(`message-${a}`)?.scrollIntoView({block: "nearest"});
  }
  function showResult(value) {
    result = value; rejected = null;
    if (!current || current.conversation_id !== value.conversation.conversation_id || pasted) showConversation(value.conversation);
    renderResult(value, $("results"), $("run-summary"), jump);
    $("download").disabled = false;
    loadAppeals();
  }
  function showRejected(diagnostic) {
    rejected = diagnostic; result = null;
    if (!current || current.conversation_id !== diagnostic.conversation.conversation_id) showConversation(diagnostic.conversation);
    renderFailure(diagnostic, $("results"), $("run-summary")); $("download").disabled = false;
    renderAppealsPanel(null);
  }
  function errorCard(error) {
    const card = el("article", undefined, "cqa-error-card");
    card.append(el("h3", `Evaluation not run${error.status ? " · HTTP " + error.status : ""}`), el("p", error.message),
      el("p", error.status === 403 ? "Next step: supplied input needs a matching local owner approval (authorization manifest, see TEAM_START_HERE.md). The server refused it before any provider call; nothing was scored or stored." :
        error.status === 409 ? "Next step: another evaluation is running or the checklist version conflicts. Wait, then try again." :
          "Next step: check the selection above and try again. No score was produced.", "notice"));
    return card;
  }
  $("evaluate").onclick = async () => {
    if (busy || !(current || pasted)) return;
    busy = true; clearResult(); updateMode();
    for (const id of ["conversation", "language", "provider", "checklist"]) $(id).disabled = true;
    $("results").setAttribute("aria-busy", "true"); feedback("Evaluation running…");
    try {
      const body = {provider: $("provider").value, model: $("provider").value === "openai" ? $("model").value.trim() : null};
      if (pasted) body.conversation = pasted; else body.conversation_id = current.conversation_id;
      const checklist = selectedChecklist(); if (checklist) body.checklist = checklist;
      showResult(await post("/api/evaluations", body));
      feedback(result.run.provider === "replay" ? "Recorded genuine reply re-validated and scored — no new model call." :
        result.run.is_mock ? "Mock fixture complete — no semantic quality assessment occurred." : "LLM evaluation complete — inspect evidence and review flags.");
    } catch (error) {
      feedback(error.status === 403 ? `${error.message} — supplied input needs an owner approval manifest (see TEAM_START_HERE.md).` : error.message, true);
      $("run-summary").textContent = "Evaluation failed. No score returned.";
      if (!error.details?.diagnostic_id) $("results").replaceChildren(errorCard(error));
      if (error.details?.diagnostic_id) {
        try {showRejected(await api("/api/diagnostics/" + error.details.diagnostic_id));}
        catch (_) {feedback("Evaluation failed; diagnostic remains saved on the server.", true);}
      }
    }
    finally {
      busy = false; for (const id of ["conversation", "language", "provider", "checklist"]) $(id).disabled = false;
      $("results").setAttribute("aria-busy", "false"); updateMode(); loadHistory();
    }
  };
  $("download").onclick = () => {
    const saved = result || rejected; if (!saved) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(saved, null, 2) + "\n"], {type: "application/json"}));
    const link = document.createElement("a"); link.href = url;
    link.download = `cqa-${rejected ? "rejected" : saved.run.provider}-${saved.evaluation_id || saved.diagnostic_id}.json`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  $("paste-load").onclick = () => {
    try {
      const value = JSON.parse($("paste-json").value);
      if (!value?.record?.transcript?.length) throw new Error("JSON needs record.transcript with at least one turn.");
      clearResult(); current = null; pasted = value;
      $("conversation-title").textContent = `${value.record.conversation_id} (supplied)`;
      $("conversation-meta").textContent = `${value.record.language} · ${value.record.channel} · ${value.record.transcript.length} turns · not yet normalized`;
      window.CqaTranscript.render($("transcript"), value.record);
      feedback("Supplied transcript shown. Click Evaluate; the server checks the owner approval first."); updateMode();
    } catch (error) {feedback(`Invalid conversation JSON: ${error.message}`, true);}
  };

  // History
  async function loadHistory() {
    const all = $("history-all").checked, id = current?.conversation_id;
    try {
      const rows = await api("/api/evaluations" + (!all && id ? "?conversation_id=" + encodeURIComponent(id) : ""));
      $("history").replaceChildren(...(rows.length ? rows.map(historyRow) : [emptyRow("No saved evaluations yet.")]));
    } catch (error) {$("history").replaceChildren(emptyRow(error.message));}
  }
  function emptyRow(text) {const tr = el("tr"); const td = el("td", text, "empty"); td.colSpan = 8; tr.append(td); return tr;}
  function historyRow(row) {
    const tr = el("tr");
    const status = row.kind === "rejected" ? `rejected (${row.issues} issues)` : row.status;
    const appeals = row.kind === "rejected" ? "—" : `${row.appeals_open} open · ${row.appeals_revised} revised`;
    const pill = el("span", status, "cqa-pill"), statusCell = el("td");
    pill.dataset.status = row.kind === "rejected" ? "rejected" : row.status; statusCell.append(pill);
    tr.append(el("td", (row.started_at || "").replace("T", " ").slice(0, 19)), el("td", row.conversation_id),
      el("td", row.checklist_version), el("td", `${row.provider} · ${row.model}`), statusCell,
      el("td", row.total_score ?? "—"), el("td", appeals));
    const td = el("td"), open = el("button", "Open"); open.type = "button";
    open.onclick = async () => {
      try {
        if (row.kind === "rejected") showRejected(await api("/api/diagnostics/" + row.evaluation_id));
        else showResult(await api("/api/evaluations/" + row.evaluation_id));
        feedback(`Loaded saved ${row.kind} ${row.evaluation_id}. No new evaluation was run.`);
      } catch (error) {feedback(error.message, true);}
    };
    td.append(open); tr.append(td); return tr;
  }
  $("history-refresh").onclick = loadHistory; $("history-all").onchange = loadHistory;

  // Appeals
  function renderAppealsPanel(view) {
    const enabled = Boolean(result);
    for (const id of ["appeal-criterion", "appeal-requested", "appeal-submit"]) $(id).disabled = !enabled;
    if (!enabled) {
      $("comparison").replaceChildren(el("p", rejected ? "Rejected evaluations have no accepted score to appeal; re-evaluate instead." :
        "Open an accepted evaluation to see appeals.", "empty"));
      $("appeals").replaceChildren(el("p", "No appeals.", "empty"));
      $("appeal-criterion").replaceChildren(); $("appeal-requested").replaceChildren();
      return;
    }
    const keep = $("appeal-criterion").value;
    $("appeal-criterion").replaceChildren(...result.checklist.criteria.map(c => new Option(`${c.criterion_id} · ${c.title}`, c.criterion_id)));
    if (keep && result.checklist.criteria.some(c => c.criterion_id === keep)) $("appeal-criterion").value = keep;
    fillRequested();
    if (!view) return;
    renderComparison(view, result.checklist, $("comparison"));
    $("appeals").replaceChildren(...(view.appeals.length ? view.appeals.map(appealCard) : [el("p", "No appeals.", "empty")]));
  }
  function criterionOf(id) {return result.checklist.criteria.find(c => c.criterion_id === id);}
  function responseOptions(select, criterion, blankLabel) {
    const options = permittedResponses(criterion).map(v => new Option(String(v), JSON.stringify(v)));
    if (blankLabel) options.unshift(new Option(blankLabel, ""));
    select.replaceChildren(...options);
  }
  function fillRequested() {
    const criterion = criterionOf($("appeal-criterion").value);
    if (criterion) responseOptions($("appeal-requested"), criterion, "(no specific request)");
  }
  $("appeal-criterion").onchange = fillRequested;
  function appealCard(appeal) {
    const card = el("article", undefined, `result-card appeal ${appeal.state}`);
    card.append(el("h3", `${appeal.criterion_id} · ${appeal.state.toUpperCase()}`),
      el("p", `Original response: ${appeal.original_response} · requested: ${appeal.requested_response ?? "—"} · by ${appeal.submitted_by} at ${appeal.submitted_at}`, "meta"),
      el("p", appeal.explanation));
    if (appeal.decision) {
      card.append(el("p", `Reviewer ${appeal.decision.reviewer}: ${appeal.decision.outcome} → final ${appeal.decision.final_response} (${appeal.decision.decided_at})`, "raw"),
        el("p", appeal.decision.reason, "notice"));
    } else {
      const form = el("div", undefined, "form-grid");
      const outcome = el("select"); outcome.append(new Option("Confirm original", "confirm"), new Option("Change decision", "change"));
      const value = el("select"); responseOptions(value, criterionOf(appeal.criterion_id));
      const reason = el("textarea"); reason.placeholder = "Reviewer reason (required)"; reason.maxLength = 4000;
      const submit = el("button", "Record reviewer decision"); submit.type = "button";
      submit.onclick = async () => {
        try {
          const body = {reviewer: $("reviewer-name").value.trim(), outcome: outcome.value, reason: reason.value.trim(),
            new_response: outcome.value === "change" ? JSON.parse(value.value) : null};
          const out = await post(`/api/appeals/${appeal.appeal_id}/decision`, body, {"X-CQA-Reviewer-Key": $("reviewer-key").value});
          renderAppealsPanel(out.view); loadHistory();
          feedback(out.view.revised_score ? `Reviewer decision recorded. Revised total ${out.view.revised_score.total_score}; original ${out.view.original_score.total_score} kept.` :
            "Reviewer confirmed the original decision.");
        } catch (error) {feedback(error.message, true);}
      };
      const l1 = el("label", "Outcome"), l2 = el("label", "New response (if changed)"), l3 = el("label", "Reason");
      l1.append(outcome); l2.append(value); l3.append(reason); l3.className = "wide";
      form.append(l1, l2, l3, submit); card.append(form);
    }
    return card;
  }
  async function loadAppeals() {
    if (!result) return renderAppealsPanel(null);
    try {renderAppealsPanel(await api(`/api/evaluations/${result.evaluation_id}/appeals`));}
    catch (error) {feedback(error.message, true);}
  }
  $("appeal-form").onsubmit = async event => {
    event.preventDefault();
    if (!result) return;
    try {
      const requested = $("appeal-requested").value;
      const out = await post(`/api/evaluations/${result.evaluation_id}/appeals`, {criterion_id: $("appeal-criterion").value,
        submitted_by: $("appeal-name").value.trim(), explanation: $("appeal-explanation").value.trim(),
        requested_response: requested ? JSON.parse(requested) : null});
      $("appeal-explanation").value = ""; renderAppealsPanel(out.view); loadHistory();
      feedback("Appeal submitted. A reviewer (different person, with the reviewer key) must confirm or change it.");
    } catch (error) {feedback(error.message, true);}
  };

  // Checklists
  async function loadChecklists(select) {
    checklists = await api("/api/checklists");
    const option = c => new Option(`${c.checklist_id} · ${c.version}`, `${c.checklist_id}\u0000${c.version}`);
    const keep = $("checklist").value || `${config.checklist.checklist_id}\u0000${config.checklist.version}`;
    $("checklist").replaceChildren(...checklists.map(option));
    $("checklist").value = select || keep;
    const base = $("editor-base").value;
    $("editor-base").replaceChildren(...checklists.map(c => new Option(`${c.checklist_id} · ${c.version}`, c.sha256)));
    if (base) $("editor-base").value = base;
  }
  async function loadEditor() {
    try {
      editing = await api("/api/checklists/" + $("editor-base").value);
      $("editor-version").value = editing.version + "-edit";
      syncJson(); renderEditor(); $("editor-save").disabled = false; $("editor-feedback").textContent = "";
    } catch (error) {$("editor-feedback").textContent = error.message;}
  }
  function syncJson() {$("editor-json").value = JSON.stringify(editing, null, 2);}
  function field(label, input, wide) {const l = el("label", label); if (wide) l.className = "wide"; l.append(input); return l;}
  function renderEditor() {
    const blocks = editing.criteria.map((criterion, index) => {
      const box = el("fieldset", undefined, "criterion");
      box.append(el("legend", `${criterion.criterion_id} · ${criterion.kind}${criterion.output_source === "atomic" ? " · derived from atomic facts" : ""}`));
      const title = el("input"); title.value = criterion.title; title.oninput = () => {criterion.title = title.value; syncJson();};
      const weight = el("input"); weight.type = "number"; weight.min = 0; weight.value = criterion.weight;
      weight.disabled = criterion.kind === "critical";
      weight.oninput = () => {criterion.weight = Number(weight.value); syncJson();};
      const instructions = el("textarea"); instructions.value = criterion.instructions;
      instructions.oninput = () => {criterion.instructions = instructions.value; syncJson();};
      const grid = el("div", undefined, "form-grid");
      grid.append(field("Title", title), field(criterion.kind === "critical" ? "Weight (critical flags are unweighted)" : "Weight", weight),
        field("Instructions", instructions, true));
      if (criterion.kind === "discrete") {
        const levels = el("input"); levels.value = criterion.levels.join(", ");
        levels.onchange = () => {
          const parsed = levels.value.split(",").map(v => Number(v.trim())).filter(v => Number.isInteger(v));
          criterion.levels = [...new Set(parsed)].sort((a, b) => a - b);
          const anchors = {}; for (const level of criterion.levels) anchors[String(level)] = criterion.anchors[String(level)] ?? "";
          criterion.anchors = anchors; syncJson(); renderEditor();
        };
        grid.append(field("Scale levels (must include 0)", levels, true));
        for (const level of criterion.levels) {
          const anchor = el("textarea"); anchor.value = criterion.anchors[String(level)] ?? "";
          anchor.oninput = () => {criterion.anchors[String(level)] = anchor.value; syncJson();};
          grid.append(field(`Anchor for ${level}`, anchor, true));
        }
      }
      if (criterion.na_condition !== null) {
        const na = el("textarea"); na.value = criterion.na_condition;
        na.oninput = () => {criterion.na_condition = na.value; syncJson();};
        grid.append(field(`N/A allowed only when (applicability question ${criterion.applicability_rule?.question_id})`, na, true));
      } else grid.append(el("p", "N/A not permitted for this criterion (add an applicability rule in the JSON to allow it).", "notice"));
      for (const question of criterion.questions) {
        const q = el("textarea"); q.value = question.question;
        q.oninput = () => {question.question = q.value; syncJson();};
        grid.append(field(`Atomic question ${question.question_id}`, q, true));
      }
      box.append(grid); box.dataset.index = index; return box;
    });
    $("editor-criteria").replaceChildren(el("p", `${editing.criteria.length} criteria · decision path ${editing.decision_path || "legacy"} · source: ${editing.source}`, "notice"), ...blocks);
  }
  $("editor-base").onchange = loadEditor;
  $("editor-apply").onclick = () => {
    try {editing = JSON.parse($("editor-json").value); renderEditor(); $("editor-feedback").textContent = "Form reloaded from JSON.";}
    catch (error) {$("editor-feedback").textContent = `Invalid JSON: ${error.message}`;}
  };
  $("editor-save").onclick = async () => {
    try {
      const body = JSON.parse($("editor-json").value);
      body.version = $("editor-version").value.trim();
      const saved = await post("/api/checklists", body);
      await loadChecklists(`${saved.checklist_id}\u0000${saved.version}`);
      $("editor-base").value = saved.sha256;
      $("editor-feedback").textContent = `Saved ${saved.checklist_id} · ${saved.version} (sha256 ${saved.sha256.slice(0, 12)}…). It is now selected for the next evaluation.`;
      clearResult(); updateMode();
    } catch (error) {
      $("editor-feedback").textContent = `Not saved: ${error.message}${error.details?.fields ? " — fields: " + error.details.fields.join(", ") : ""}`;
    }
  };

  // Tabs: every panel stays in the DOM; the root's data-tab attribute selects the visible one in CSS,
  // so switching never resets a result or typed input. State lives in location.hash.
  const tabNames = ["evaluation", "history-appeals", "checklists"];
  function showTab(name, focus) {
    if (!tabNames.includes(name)) name = tabNames[0];
    $("cqa-app").dataset.tab = name;
    for (const other of tabNames) {
      const tab = $("cqa-tab-" + other), selected = other === name;
      tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1;
    }
    if (focus) $("cqa-tab-" + name).focus();
    const hash = name === tabNames[0] && !window.location.hash ? "" : "#" + name;
    if (hash && window.location.hash !== hash) window.history.replaceState(null, "", hash);
  }
  for (const name of tabNames) $("cqa-tab-" + name).onclick = () => showTab(name);
  $("cqa-tabs").onkeydown = event => {
    const index = tabNames.indexOf($("cqa-app").dataset.tab);
    const next = {ArrowRight: index + 1, ArrowLeft: index + tabNames.length - 1, Home: 0, End: tabNames.length - 1}[event.key];
    if (next === undefined) return;
    event.preventDefault(); showTab(tabNames[next % tabNames.length], true);
  };
  window.onhashchange = () => showTab(window.location.hash.slice(1));
  showTab(window.location.hash.slice(1));

  $("language").onchange = filter; $("conversation").onchange = selectConversation;
  $("checklist").onchange = () => {clearResult(); updateMode();};
  $("provider").onchange = () => {
    clearResult(); updateMode();
    if ($("provider").value === "replay") feedback("Replay needs conversation p1-ru-001 and checklist 2026-11-07.v5 (the recorded pair).");
  };
  $("model").oninput = () => {clearResult(); updateMode();};
  Promise.all([api("/api/config"), api("/api/conversations")]).then(async ([settings, data]) => {
    config = settings; records = data; $("model").value = settings.model;
    await loadChecklists(); await loadEditor(); filter();
    const diagnosticId = new URL(window.location.href).searchParams.get("diagnostic");
    if (diagnosticId) {
      showRejected(await api("/api/diagnostics/" + encodeURIComponent(diagnosticId)));
      feedback("Saved response rejected by validation. No total and no new model request.", true);
    }
  }).catch(error => feedback(error.message, true));
})();
