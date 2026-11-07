/* Offline manual labels only. No network, scoring engine, or browser storage. */
(function () {
  "use strict";
  const schemaVersion = "dev-team-human-1";
  const originalId = m => m.message_id ?? m.id ?? null;
  const blank = () => ({response: null, justification: "", evidence_indexes: "", scope_note: ""});
  function indexes(raw, length) {
    if (!raw.trim()) return [];
    const parts = raw.split(",").map(x => x.trim());
    if (parts.some(x => !/^(0|[1-9][0-9]*)$/.test(x) || Number(x) >= length)) {
      throw new Error(`Evidence must be comma-separated message indexes from 0 to ${length - 1}.`);
    }
    return [...new Set(parts.map(Number))];
  }
  function evidence(record, index) {
    const m = record.transcript[index];
    return {transcript_index: index, original_message_id: originalId(m),
      timestamp: m.timestamp ?? null, speaker: m.speaker, text: m.text};
  }
  function newSession(reviewer) {
    if (!reviewer.trim()) throw new Error("Enter your reviewer name or ID first.");
    return {reviewer_id: reviewer.trim(), created_at: new Date().toISOString(), assessments: {}};
  }
  function bundle(data, session) {
    if (!session) throw new Error("Start your own blank review first.");
    const assessments = data.records.filter(r => session.assessments[r.conversation_id]).map(record => {
      const a = session.assessments[record.conversation_id];
      const criteria = data.rubric.criteria.map(c => {
        const v = a.criteria[c.id];
        if (v.response !== null && !c.responses.includes(v.response)) throw new Error(`Invalid response for ${c.id}.`);
        let refs;
        try { refs = indexes(v.evidence_indexes, record.transcript.length); }
        catch (err) { throw new Error(`${record.conversation_id}, criterion ${c.id}: ${err.message}`); }
        return {criterion_id: c.id, response: v.response, justification: v.justification,
          evidence: refs.map(i => evidence(record, i)), scope_note: v.scope_note};
      });
      const complete = criteria.every(c => c.response !== null && c.justification.trim() &&
        (c.evidence.length || c.scope_note.trim()));
      return {conversation_id: record.conversation_id, language: record.language, channel: record.channel,
        updated_at: a.updated_at, status: complete ? "complete" : "draft", criteria};
    });
    if (!assessments.length) throw new Error("No human entries to export yet.");
    return {schema_version: schemaVersion, label_source: "team_human", official_ground_truth: false,
      reviewer_id: session.reviewer_id, created_at: session.created_at, exported_at: new Date().toISOString(),
      dataset: data.source, rubric_version: data.rubric.version, rubric_sha256: data.rubric_sha256, assessments};
  }
  function importBundle(data, saved) {
    if (saved.schema_version !== schemaVersion || saved.label_source !== "team_human" ||
        saved.official_ground_truth !== false || saved.dataset?.sha256 !== data.source.sha256 ||
        saved.rubric_sha256 !== data.rubric_sha256 || saved.rubric_version !== data.rubric.version) {
      throw new Error("Resume requires this viewer's team_human JSON with matching dataset and rubric hashes.");
    }
    if (typeof saved.reviewer_id !== "string" || !saved.reviewer_id.trim() ||
        typeof saved.created_at !== "string" || !Number.isFinite(Date.parse(saved.created_at)) ||
        !Array.isArray(saved.assessments) || !saved.assessments.length) throw new Error("Invalid review file.");
    const session = newSession(saved.reviewer_id);
    session.created_at = saved.created_at;
    for (const a of saved.assessments) {
      const r = data.records.find(r => r.conversation_id === a.conversation_id);
      if (!r || Object.hasOwn(session.assessments, a.conversation_id) || !Array.isArray(a.criteria) ||
          a.criteria.length !== data.rubric.criteria.length || a.language !== r.language || a.channel !== r.channel ||
          typeof a.updated_at !== "string" || !Number.isFinite(Date.parse(a.updated_at))) throw new Error("Invalid or duplicate conversation.");
      const criteria = {};
      for (const c of data.rubric.criteria) {
        const matches = a.criteria.filter(v => v.criterion_id === c.id);
        const v = matches[0];
        if (matches.length !== 1 || (v.response !== null && !c.responses.includes(v.response)) ||
            typeof v.justification !== "string" || typeof v.scope_note !== "string" || !Array.isArray(v.evidence)) {
          throw new Error(`Invalid criterion ${c.id}.`);
        }
        const refs = v.evidence.map(ref => {
          const i = ref.transcript_index;
          if (!Number.isInteger(i) || i < 0 || i >= r.transcript.length) throw new Error("Invalid evidence index.");
          const expected = evidence(r, i);
          if (Object.keys(expected).some(k => ref[k] !== expected[k])) throw new Error("Evidence differs from source transcript.");
          return i;
        });
        criteria[c.id] = {response: v.response, justification: v.justification,
          evidence_indexes: refs.join(", "), scope_note: v.scope_note};
      }
      session.assessments[r.conversation_id] = {updated_at: a.updated_at, criteria};
    }
    return session;
  }
  function csvCell(value) {
    let s = value === null || value === undefined ? "" : String(value);
    // Prevent spreadsheet applications interpreting reviewer text as formulas.
    if (/^[\s]*[=+@-]/.test(s) || /^[\t\r\n]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  }
  function csv(saved) {
    const header = ["label_source", "official_ground_truth", "reviewer_id", "dataset_sha256", "dataset_path",
      "rubric_version", "rubric_sha256", "created_at", "exported_at", "conversation_id", "language", "channel",
      "updated_at", "status", "criterion_id", "response", "justification", "evidence_json", "scope_note"];
    const rows = [header];
    for (const a of saved.assessments) for (const c of a.criteria) rows.push([
      "team_human", false, saved.reviewer_id, saved.dataset.sha256, saved.dataset.path,
      saved.rubric_version, saved.rubric_sha256, saved.created_at, saved.exported_at,
      a.conversation_id, a.language, a.channel, a.updated_at, a.status, c.criterion_id,
      c.response, c.justification, JSON.stringify(c.evidence), c.scope_note]);
    return "\ufeff" + rows.map(row => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
  }
  const api = {blank, indexes, evidence, newSession, bundle, importBundle, csv};
  if (typeof module !== "undefined") module.exports = api;
  if (typeof document === "undefined") return;

  const data = JSON.parse(document.getElementById("review-data").textContent);
  const $ = id => document.getElementById(id);
  let current = data.records[0], filtered = data.records, session = null, dirty = false;
  function el(tag, text, cls) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }
  function status(message, error = false) {
    $("feedback").textContent = message;
    $("feedback").className = error ? "error" : "";
    $("assessment-count").textContent = session ? `${Object.keys(session.assessments).length} conversation(s) with human entries.` : "";
  }
  function showTranscript() {
    $("conversation-title").textContent = current.conversation_id;
    $("conversation-meta").textContent = `${current.language} · ${current.channel} · ${current.transcript.length} messages · source order`;
    const fragment = document.createDocumentFragment();
    current.transcript.forEach((m, index) => {
      const article = el("article", undefined, `message ${["client","operator","bot","system"].includes(m.speaker) ? m.speaker : ""}`);
      article.id = `message-${index}`;
      article.append(el("div", m.speaker, "speaker"), el("div",
        `Index ${index} · Original message ID: ${originalId(m) === null ? "not provided" : originalId(m)} · Timestamp: ${m.timestamp ?? "not provided"}`, "meta"),
        el("div", m.text, "message-text"));
      fragment.append(article);
    });
    $("transcript").replaceChildren(fragment);
    $("transcript").scrollTop = 0;
  }
  function showForm() {
    const form = $("review-form"); form.replaceChildren();
    const existing = session?.assessments[current.conversation_id];
    for (const c of data.rubric.criteria) {
      const value = existing?.criteria[c.id] || blank();
      const field = el("fieldset", undefined, "criterion"); field.disabled = !session;
      field.append(el("legend", `${c.id} · ${c.title}`),
        el("p", `${c.weight === null ? "Separate critical-error flag" : "Base weight: " + c.weight} · ${c.guidance}`),
        el("p", c.na_condition ? `N/A only when: ${c.na_condition}` : "N/A is not permitted."));
      const select = el("select"); select.id = `response-${c.id}`;
      select.append(new Option("— Unscored —", ""));
      for (const response of c.responses) select.append(new Option(
        response === "yes" ? (c.id === "08" ? "Yes — critical violation identified" : "Yes") :
        response === "no" ? (c.id === "08" ? "No — no listed violation identified" : "No") : String(response), String(response)));
      select.value = value.response === null ? "" : String(value.response);
      const justification = el("textarea"); justification.id = `justification-${c.id}`; justification.value = value.justification;
      const refs = el("input"); refs.id = `evidence-${c.id}`; refs.value = value.evidence_indexes; refs.placeholder = "e.g. 0, 9, 11 (zero-based)";
      const note = el("textarea"); note.id = `scope-${c.id}`; note.value = value.scope_note;
      note.placeholder = "Checked scope / omission range / external policy source / uncertainty";
      const links = el("div", undefined, "links"); links.id = `links-${c.id}`;
      for (const [text, input] of [["Your response / raw score", select], ["Your justification (including N/A reason)", justification],
        ["Evidence message indexes, separated by commas", refs], ["Scope / references / uncertainty", note]]) {
        const label = el("label", text); label.htmlFor = input.id; field.append(label, input);
      }
      field.append(links); form.append(field);
      function updateLinks() {
        links.replaceChildren();
        try {
          const selected = indexes(refs.value, current.transcript.length);
          refs.setCustomValidity("");
          for (const i of selected) {
            const a = el("a", `Message ${i}`); a.href = `#message-${i}`;
            a.onclick = event => {event.preventDefault(); const target = $(`message-${i}`);
              $("transcript").querySelectorAll(".highlight").forEach(x => x.classList.remove("highlight"));
              target.classList.add("highlight"); target.scrollIntoView({block: "nearest"});};
            links.append(a);
          }
        } catch (err) {refs.setCustomValidity(err.message); links.append(el("span", err.message, "error"));}
      }
      function update() {
        if (!session) return;
        if (!session.assessments[current.conversation_id]) session.assessments[current.conversation_id] = {
          criteria: Object.fromEntries(data.rubric.criteria.map(c => [c.id, blank()]))};
        const a = session.assessments[current.conversation_id];
        a.criteria[c.id] = {response: select.value === "" ? null : c.responses.find(r => String(r) === select.value),
          justification: justification.value, evidence_indexes: refs.value, scope_note: note.value};
        a.updated_at = new Date().toISOString(); dirty = true; updateLinks();
        status("Unsaved human entries — download JSON to keep a resumable copy.");
      }
      select.onchange = update; justification.oninput = update; refs.oninput = update; note.oninput = update;
      updateLinks();
    }
    form.scrollTop = 0;
  }
  function showCurrent() {
    $("conversation").value = current.conversation_id;
    const i = filtered.indexOf(current);
    $("previous").disabled = i <= 0; $("next").disabled = i >= filtered.length - 1;
    showTranscript(); showForm();
  }
  function filter() {
    filtered = data.records.filter(r => (!$("language").value || r.language === $("language").value) &&
      r.conversation_id.toLowerCase().includes($("search").value.toLowerCase()));
    $("conversation").replaceChildren(...filtered.map(r => new Option(`${r.conversation_id} · ${r.language}`, r.conversation_id)));
    if (!filtered.length) {
      $("conversation-title").textContent = "No matching conversations";
      $("conversation-meta").textContent = "Change the ID search or language filter.";
      $("transcript").replaceChildren(); $("review-form").replaceChildren();
      $("previous").disabled = true; $("next").disabled = true; return;
    }
    if (!filtered.includes(current)) current = filtered[0];
    showCurrent();
  }
  function lockReviewer() {$("reviewer").value = session.reviewer_id; $("reviewer").disabled = true; $("start").disabled = true;}
  $("start").onclick = () => {
    try {session = newSession($("reviewer").value); lockReviewer(); filter(); status("Blank review started. Only your entries will be exported.");}
    catch (err) {status(err.message, true);}
  };
  $("language").onchange = filter; $("search").oninput = filter;
  $("conversation").onchange = () => {current = filtered.find(r => r.conversation_id === $("conversation").value); showCurrent();};
  $("previous").onclick = () => {current = filtered[filtered.indexOf(current) - 1]; showCurrent();};
  $("next").onclick = () => {current = filtered[filtered.indexOf(current) + 1]; showCurrent();};
  function download(kind) {
    try {
      const saved = bundle(data, session);
      const body = kind === "json" ? JSON.stringify(saved, null, 2) + "\n" : csv(saved);
      const url = URL.createObjectURL(new Blob([body], {type: kind === "json" ? "application/json;charset=utf-8" : "text/csv;charset=utf-8"}));
      const a = el("a"); a.href = url;
      a.download = `team_human-${session.reviewer_id.replace(/[^a-z0-9_-]/gi, "_")}-${new Date().toISOString().replace(/[:.]/g, "-")}.${kind}`;
      document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (kind === "json") dirty = false;
      status(`Requested ${kind.toUpperCase()} download. Check your browser's Downloads.${kind === "csv" ? " Save JSON too if you want to resume." : ""}`);
    } catch (err) {status(err.message, true);}
  }
  $("export-json").onclick = () => download("json"); $("export-csv").onclick = () => download("csv");
  $("import-file").onchange = async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      const resumed = importBundle(data, JSON.parse(await file.text()));
      if (session && Object.keys(session.assessments).length && !window.confirm("Replace the current review with this saved JSON? Download your current JSON first if you need to keep it.")) return;
      session = resumed; dirty = false; lockReviewer();
      $("language").value = ""; $("search").value = "";
      current = data.records.find(r => r.conversation_id === Object.keys(session.assessments)[0]);
      filter(); status(`Resumed independent labels by ${session.reviewer_id}.`);
    } catch (err) {status(`Could not resume: ${err.message}`, true);}
    finally {event.target.value = "";}
  };
  window.addEventListener("beforeunload", event => {if (dirty) {event.preventDefault(); event.returnValue = "";}});
  $("source").textContent = `${data.source.path} · SHA256 ${data.source.sha256} · ${data.source.record_count} synthetic chats (partial DEV, no calls). Rubric: ${data.rubric.version} · ${data.rubric.source} · SHA256 ${data.rubric_sha256}. Original message IDs are absent in this dataset. No browser autosave; reload starts blank.`;
  filter();
})();
