/* Integration UI: consumes the existing EvaluationResult contract, never computes scores. */
(function () {
  "use strict";
  function responseText(decision, criterion) {
    if (decision.response === "N/A") return "N/A — not applicable";
    if (criterion.kind === "discrete") return `${decision.response} / ${Math.max(...criterion.levels)}`;
    if (criterion.kind === "critical") return decision.response === "yes" ? "Yes — critical violation flagged" : "No listed violation flagged";
    return decision.response === "yes" ? "Yes" : "No";
  }
  function renderResult(result, container, summary, onEvidence) {
    const doc = container.ownerDocument;
    function el(tag, text, cls) {
      const node = doc.createElement(tag);
      if (text !== undefined) node.textContent = text;
      if (cls) node.className = cls;
      return node;
    }
    const mock = result.run.is_mock;
    summary.textContent = `${mock ? "MOCK FIXTURE — not a quality judgment" : "LLM evaluation — semantic accuracy not independently verified"}\n` +
      `Total${mock ? " (fixture)" : ""}: ${result.score.total_score ?? "not calculated"} / 100 · Critical flag: ${result.score.critical_violation ? "yes" : "no"}\n` +
      `${result.run.provider} · ${result.run.model_returned} · ${result.run.latency_ms} ms · ${result.status}\n` +
      `Checklist: ${result.checklist.version} · Usage: ${JSON.stringify(result.run.usage)}`;
    container.replaceChildren();
    const scores = new Map(result.score.criteria.map(c => [c.criterion_id, c]));
    const definitions = new Map(result.checklist.criteria.map(c => [c.criterion_id, c]));
    function evidenceList(evidence, parent) {
      for (const reference of evidence) {
        const links = el("div", undefined, "evidence-links");
        const ids = reference.kind === "quote" ? [reference.message_id] : [reference.start_message_id, reference.end_message_id];
        const button = el("button", reference.kind === "quote" ? `Message ${ids[0]}` : `${reference.kind}: ${ids[0]}–${ids[1]}`);
        button.type = "button";
        button.dataset.startMessageId = ids[0];
        button.dataset.endMessageId = ids[ids.length - 1];
        button.onclick = () => onEvidence(reference);
        links.append(button); parent.append(links, el("p", reference.explanation, "notice"));
        if (reference.quote !== null) parent.append(el("blockquote", reference.quote));
      }
    }
    for (const decision of result.model_evaluation.decisions) {
      const criterion = definitions.get(decision.criterion_id), score = scores.get(decision.criterion_id);
      const card = el("article", undefined, "result-card"); card.dataset.criterionId = criterion.criterion_id;
      card.append(el("h3", `${criterion.criterion_id} · ${criterion.title}`), el("p", responseText(decision, criterion), "raw"));
      card.append(el("p", criterion.kind === "critical" ? "Separate flag — no numerical deduction" :
        `Base weight ${score.base_weight} · Effective weight ${score.effective_weight} · Points ${score.earned_points}`, "meta"));
      card.append(el("p", decision.rationale));
      if (decision.na_reason) card.append(el("p", `N/A reason: ${decision.na_reason}`, "na-reason"));
      card.append(el("p", criterion.na_condition ? `N/A allowed only when: ${criterion.na_condition}` : "N/A not permitted.", "notice"));
      if (decision.needs_review) card.append(el("p", `Needs review: ${decision.review_reason}`, "review"));
      evidenceList(decision.evidence, card);
      const atomic = el("details"); atomic.append(el("summary", `Atomic rubric checks (${decision.atomic_checks.length})`));
      const questions = new Map(criterion.questions.map(q => [q.question_id, q.question]));
      for (const check of decision.atomic_checks) {
        const item = el("div");
        item.append(el("p", `${questions.get(check.question_id)} — ${check.answer}`), el("p", check.rationale, "notice"));
        evidenceList(check.evidence, item); atomic.append(item);
      }
      card.append(atomic); container.append(card);
    }
    const audit = el("details", undefined, "audit"); audit.append(el("summary", "Run audit and review findings"));
    audit.append(el("pre", JSON.stringify({evaluation_id: result.evaluation_id, run: result.run,
      check_outcomes: result.check_outcomes, audit: result.audit, revision_history: result.revision_history}, null, 2)));
    container.append(audit);
  }
  if (typeof module !== "undefined" && module.exports) {module.exports = {responseText, renderResult}; return;}
  const $ = id => document.getElementById(id);
  let records = [], config, current = null, result = null, busy = false, sequence = 0;
  async function api(path, options) {
    const response = await fetch(path, options);
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Local request failed.");
    return value;
  }
  function feedback(text, error = false) {$("feedback").textContent = text; $("feedback").className = error ? "status error" : "status";}
  function updateMode() {
    const mock = $("provider").value === "mock";
    $("mode").className = mock ? "mode" : "mode live";
    $("mode").textContent = mock ? "MOCK mode — fixed test fixtures, not AI quality judgments." :
      "OpenAI selected — only a successful provider response is an LLM evaluation. Synthetic DEV only.";
    $("model").disabled = mock || busy;
    const ready = mock || (config?.openai_key_present && config?.external_synthetic_allowed && $("model").value.trim());
    $("evaluate").disabled = busy || !current || !ready;
    if (!mock && !ready) feedback("OpenAI requires authorized server credentials, --allow-external-synthetic and an explicit model. No request has been sent.");
  }
  function clearResult() {
    result = null; $("download").disabled = true;
    $("results").replaceChildren(); $("run-summary").textContent = "No evaluation for this selection yet.";
  }
  async function selectConversation() {
    const requestSequence = ++sequence;
    current = null; clearResult(); updateMode(); $("transcript").replaceChildren();
    const id = $("conversation").value;
    if (!id) return;
    try {
      const loaded = await api("/api/conversations/" + encodeURIComponent(id));
      if (requestSequence !== sequence) return;
      current = loaded;
      $("conversation-title").textContent = loaded.conversation_id;
      $("conversation-meta").textContent = `${loaded.language} · ${loaded.channel} · ${loaded.messages.length} messages · source order`;
      window.CqaTranscript.render($("transcript"), loaded);
      feedback("Transcript loaded. Evaluation has not run."); updateMode();
    } catch (error) {if (requestSequence === sequence) feedback(error.message, true);}
  }
  function filter() {
    const filtered = records.filter(r => !$("language").value || r.language === $("language").value);
    $("conversation").replaceChildren(...filtered.map(r => new Option(`${r.conversation_id} · ${r.language}`, r.conversation_id)));
    $("conversation").disabled = !filtered.length;
    selectConversation();
  }
  function jump(reference) {
    const start = reference.kind === "quote" ? reference.message_id : reference.start_message_id;
    const end = reference.kind === "quote" ? start : reference.end_message_id;
    const a = current.messages.findIndex(m => m.message_id === start), b = current.messages.findIndex(m => m.message_id === end);
    $("transcript").querySelectorAll(".highlight").forEach(node => node.classList.remove("highlight"));
    for (let i = a; i <= b; i++) $(`message-${i}`).classList.add("highlight");
    $(`message-${a}`).scrollIntoView({block: "nearest"});
  }
  $("evaluate").onclick = async () => {
    if (busy || !current) return;
    busy = true; clearResult(); updateMode();
    for (const id of ["conversation", "language", "provider"]) $(id).disabled = true;
    $("results").setAttribute("aria-busy", "true"); feedback("Evaluation running…");
    try {
      result = await api("/api/evaluations", {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({conversation_id: current.conversation_id, provider: $("provider").value,
          model: $("provider").value === "mock" ? null : $("model").value.trim()})});
      renderResult(result, $("results"), $("run-summary"), jump);
      $("download").disabled = false;
      feedback(result.run.is_mock ? "Mock fixture complete — no semantic quality assessment occurred." : "LLM evaluation complete — inspect evidence and review flags.");
    } catch (error) {feedback(error.message, true); $("run-summary").textContent = "Evaluation failed. No score returned.";}
    finally {
      busy = false; for (const id of ["conversation", "language", "provider"]) $(id).disabled = false;
      $("results").setAttribute("aria-busy", "false"); updateMode();
    }
  };
  $("download").onclick = () => {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + "\n"], {type: "application/json"}));
    const link = document.createElement("a"); link.href = url; link.download = `cqa-${result.run.is_mock ? "mock" : "llm"}-${result.evaluation_id}.json`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  $("language").onchange = filter; $("conversation").onchange = selectConversation;
  $("provider").onchange = () => {
    clearResult(); updateMode();
    if ($("provider").value === "mock") feedback("Mock fixture selected. Click Evaluate to test the pipeline; no semantic assessment occurs.");
  };
  $("model").oninput = () => {clearResult(); updateMode();};
  Promise.all([api("/api/config"), api("/api/conversations")]).then(([settings, data]) => {
    config = settings; records = data; $("model").value = settings.model; filter();
  }).catch(error => feedback(error.message, true));
})();
