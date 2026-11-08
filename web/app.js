/* Integration UI: consumes the backend contracts and never computes scores itself. */
(function () {
  "use strict";
  // Russian display labels for backend enum tokens. Display only: the values themselves are never changed.
  const ANSWERS = {yes: "да", no: "нет", unknown: "неизвестно", not_applicable: "неприменимо"};
  const STATUSES = {mock_only: "тест / повтор — не для сдачи", needs_review: "требует проверки",
    structurally_valid: "прошла все проверки", rejected: "отклонена проверкой"};
  const EVIDENCE_KINDS = {scope: "участок", omission: "пропуск"};
  // Russian titles of the eight official criteria (organizer PDF). Shown only when the checklist keeps the official
  // English title; titles changed in the editor are shown exactly as saved.
  const RU_TITLES = {"Establishing contact": "Установление контакта", "Identifying the need": "Выявление потребности",
    "Identification": "Идентификация", "Correct and complete consultation": "Корректная и полная консультация",
    "Empathy and client orientation": "Эмпатия и клиентоориентированность",
    "Dialogue management, speed and language quality": "Управление диалогом, скорость и грамотность",
    "Closing": "Завершение", "Critical errors": "Грубые ошибки"};
  function titleOf(criterion) {return criterion ? RU_TITLES[criterion.title] ?? criterion.title : "";}
  function answerLabel(value) {return ANSWERS[value] ?? String(value);}
  function statusLabel(value) {return STATUSES[value] ?? String(value);}
  function responseText(decision, criterion) {
    if (decision.response === "N/A") return "N/A — неприменимо";
    if (criterion.kind === "discrete") return `${decision.response} / ${Math.max(...criterion.levels)}`;
    if (criterion.kind === "critical") return decision.response === "yes" ? "Да — грубое нарушение выявлено" : "Нет — грубых нарушений не выявлено";
    return decision.response === "yes" ? "Да" : "Нет";
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
    if (run.provider === "replay") return "ПОВТОР записанного ответа модели — нового вызова нет; помечен как тестовый, в сдачу не идёт";
    return run.is_mock ? "ТЕСТОВАЯ ЗАГЛУШКА — это не оценка качества" : "Оценка LLM — смысловая точность независимо не проверена";
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
    total.append(el("span", score.total_score ?? "не рассчитан", "cqa-hero-value"), el("span", "/ 100", "cqa-hero-scale"));
    const status = el("span", statusLabel(result.status), "cqa-pill"); status.dataset.status = result.status; status.title = `status: ${result.status}`;
    const flag = el("span", `${score.critical_violation ? "Грубое нарушение выявлено" : "Грубых нарушений нет"}${critical ? " · " + critical.criterion_id : ""}`, "cqa-pill");
    flag.dataset.critical = String(Boolean(score.critical_violation));
    const kind = el("span", run.provider === "replay" ? "Повтор" : run.is_mock ? "Заглушка" : "LLM", "cqa-pill");
    kind.dataset.status = run.is_mock ? "mock_only" : "live";
    const badges = el("div", undefined, "cqa-hero-badges"); badges.append(status, flag, kind);
    hero.append(el("p", "Итоговый балл", "cqa-hero-label"), total, badges,
      el("p", `${run.provider} · ${run.model_returned} · ${run.latency_ms} мс · чек-лист ${result.checklist.version}`, "cqa-hero-run"));
    return hero;
  }
  // Base → effective weight; "redistributed" comes from the backend applicability flags, not from comparing numbers.
  function weightsRow(score, redistributed, el) {
    const row = el("p", undefined, "meta cqa-weights");
    row.append(el("span", `Базовый вес ${score.base_weight}`), el("span", undefined, "cqa-arrow"),
      el("span", `Итоговый вес ${score.effective_weight}`), el("span", `Баллы ${score.earned_points}`));
    if (score.applicable === false) row.append(el("span", "неприменимо — вес перераспределён", "cqa-tag"));
    else if (redistributed) row.append(el("span", "вес перераспределён", "cqa-tag"));
    return row;
  }
  function renderResult(result, container, summary, onEvidence) {
    const el = factory(container);
    const mock = result.run.is_mock;
    summary.textContent = `${runLabel(result.run)}\n` +
      `Итог${mock ? " (заглушка/повтор)" : ""}: ${result.score.total_score ?? "не рассчитан"} / 100 · Грубое нарушение: ${result.score.critical_violation ? "да" : "нет"}\n` +
      `${result.run.provider} · ${result.run.model_returned} · ${result.run.latency_ms} мс · ${result.status}\n` +
      `Чек-лист: ${result.checklist.version} · Токены: ${JSON.stringify(result.run.usage)}`;
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
          target.append(el("p", reference.kind === "omission" ? "Проверенный участок разговора — ожидаемое действие не найдено" :
            "Проверенный участок разговора", "cqa-block-label"));
          parent.append(target);
        }
        const links = el("div", undefined, "evidence-links");
        const ids = reference.kind === "quote" ? [reference.message_id] : [reference.start_message_id, reference.end_message_id];
        const label = ids.map(id => turns.has(id) ? `№${turns.get(id)}` : id).join("–");
        const button = el("button", reference.kind === "quote" ? `Реплика ${ids[0]}${turns.has(ids[0]) ? " · " + label : ""}` :
          `${EVIDENCE_KINDS[reference.kind] ?? reference.kind}: ${ids[0]}–${ids[1]}${turns.size ? " · реплики " + label : ""}`);
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
      card.append(el("h3", `${criterion.criterion_id} · ${titleOf(criterion)}`), el("p", responseText(decision, criterion), "raw"));
      card.append(criterion.kind === "critical" ? el("p", "Отдельный флаг — баллы не снимаются", "meta") : weightsRow(score, redistributed, el));
      card.append(el("p", decision.rationale));
      if (decision.violation_categories?.length) card.append(el("p", `Категории нарушений: ${decision.violation_categories.join(", ")}`, "cqa-violations"));
      if (decision.na_reason) card.append(el("p", `Причина N/A: ${decision.na_reason}`, "na-reason"));
      card.append(el("p", criterion.na_condition ? `N/A допускается, только если: ${criterion.na_condition}` : "N/A для этого критерия не допускается.", "notice"));
      if (decision.needs_review) card.append(el("p", `Требует проверки: ${decision.review_reason}`, "review"));
      evidenceList(decision.evidence, card);
      if (["na", "no", "clear"].includes(card.dataset.verdict) && !decision.evidence.some(e => e.kind !== "quote"))
        evidenceList(decision.atomic_checks.flatMap(check => check.evidence).filter(e => e.kind !== "quote"), card);
      const atomic = el("details"); atomic.append(el("summary", `Атомарные проверки (${decision.atomic_checks.length})`));
      const questions = new Map(criterion.questions.map(q => [q.question_id, q.question]));
      for (const check of decision.atomic_checks) {
        const item = el("div");
        item.append(el("p", `${questions.get(check.question_id)} — ${answerLabel(check.answer)}`), el("p", check.rationale, "notice"));
        evidenceList(check.evidence, item); atomic.append(item);
      }
      card.append(atomic); container.append(card);
    }
    if (result.evidence_repairs?.length) container.append(el("p",
      `Исправлений форматирования цитат: ${result.evidence_repairs.length} (с точными позициями в источнике). Исходный текст ИИ сохранён в JSON и аудите.`, "notice"));
    const audit = el("details", undefined, "audit"); audit.append(el("summary", "Аудит запуска и проверок (JSON)"));
    audit.append(el("pre", JSON.stringify({evaluation_id: result.evaluation_id, run: result.run,
      check_outcomes: result.check_outcomes, audit: result.audit, revision_history: result.revision_history,
      evidence_repairs: result.evidence_repairs, original_model_evaluation: result.model_evaluation}, null, 2)));
    container.append(audit);
  }
  function renderFailure(diagnostic, container, summary) {
    const el = factory(container);
    summary.textContent = `${diagnostic.run.is_mock ? "ЗАГЛУШКА" : "НАСТОЯЩИЙ ОТВЕТ OPENAI"} — ПРОВЕРКА НЕ ПРОЙДЕНА\n` +
      `Принятой оценки и итога нет. Исходные решения ИИ ниже не проверены.\n` +
      `${diagnostic.run.provider} · ${diagnostic.run.model_returned} · ${diagnostic.run.provider_latency_ms} мс\n` +
      `Токены: ${JSON.stringify(diagnostic.run.usage)} · Чек-лист: ${diagnostic.checklist.version}`;
    container.replaceChildren();
    const report = el("section", undefined, "cqa-failure-report"), issues = el("ul", undefined, "cqa-issues");
    for (const issue of diagnostic.issues) issues.append(el("li", `${issue.criterion_id || "Схема"}: ${issue.message}`, "error"));
    report.append(el("h3", "Проверка не пройдена — оценка не выставлена"),
      el("p", "Почему: движок не выставляет баллы, если факты, доказательства или правила в ответе модели не проходят проверку. " +
        "В официальном экспорте такой диалог получит status=error с причиной ниже — никогда не нулевую оценку.", "notice"),
      issues, el("p", diagnostic.run.is_mock && diagnostic.checklist.decision_path === "atomic_first" ?
        "Что делать: тестовая заглушка не умеет отвечать на атомарные факты этого чек-листа (так задумано). Для оценки с баллами выберите повтор записанного ответа (p1-ru-001 + чек-лист 2026-11-07.v5), заглушку с чек-листом v2/v3 или OpenAI." :
        "Что делать: посмотрите исходные решения ниже или скачайте JSON с диагностикой и запустите оценку снова. Отклонённый ответ никогда не исправляется молча и не оценивается.", "cqa-next-step"));
    container.append(report);
    const raw = diagnostic.original_model_output;
    const legacy = raw && typeof raw === "object" && Array.isArray(raw.decisions) ? raw.decisions : [];
    const atomic = raw && typeof raw === "object" && Array.isArray(raw.criteria) ? raw.criteria : [];
    const states = new Map((diagnostic.criterion_reviews || []).map(r => [r.criterion_id, r.state]));
    for (const decision of legacy.length ? legacy : atomic) {
      const card = el("article", undefined, "result-card rejected-card");
      card.dataset.criterionId = decision.criterion_id; card.dataset.verdict = "rejected";
      const definition = diagnostic.checklist.criteria.find(c => c.criterion_id === decision.criterion_id);
      const response = legacy.length ? answerLabel(decision.response) : decision.judgment ? answerLabel(decision.judgment.response) : "выводится из атомарных фактов";
      card.append(el("h3", `${decision.criterion_id} · ${titleOf(definition) || "Исходное решение ИИ"}`),
        el("p", `Исходный ответ: ${String(response)} — оценка не принята${states.has(decision.criterion_id) ? " · состояние " + states.get(decision.criterion_id) : ""}`, "raw"),
        el("p", String(decision.rationale || decision.judgment?.rationale || "")));
      if (decision.na_reason) card.append(el("p", `Исходная причина N/A: ${decision.na_reason}`));
      const details = doc(container).createElement("details");
      details.append(el("summary", "Исходные атомарные проверки и доказательства (не проверены)"), el("pre", JSON.stringify(decision, null, 2)));
      card.append(details); container.append(card);
    }
  }
  function doc(container) {return container.ownerDocument;}
  function renderComparison(view, checklist, container) {
    const el = factory(container);
    container.replaceChildren();
    const original = view.original_score, revised = view.revised_score;
    const totals = el("div", undefined, "cqa-compare-totals");
    totals.append(el("p", `Исходный итог: ${original.total_score ?? "не рассчитан"} · грубое нарушение: ${original.critical_violation ? "да" : "нет"}`, "raw"));
    if (revised) totals.append(el("span", undefined, "cqa-arrow"),
      el("p", `Пересмотренный итог: ${revised.total_score ?? "не рассчитан"} · грубое нарушение: ${revised.critical_violation ? "да" : "нет"}`, "raw cqa-revised"));
    else totals.append(el("p", "Проверяющий ничего не менял — действует исходный итог.", "notice"));
    container.append(totals);
    const table = el("table", undefined, "comparison");
    const head = el("tr"); for (const h of ["Критерий", "Исходно", "После пересмотра", "Вес"]) head.append(el("th", h));
    table.append(head);
    for (const criterion of checklist.criteria) {
      const row = el("tr");
      const a = view.original_responses[criterion.criterion_id], b = view.revised_responses[criterion.criterion_id];
      if (a !== b) row.dataset.changed = "true";
      row.append(el("td", `${criterion.criterion_id} · ${titleOf(criterion)}`), el("td", answerLabel(a)),
        el("td", answerLabel(b), a === b ? undefined : "changed"), el("td", criterion.kind === "critical" ? "флаг" : String(criterion.weight)));
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
  const APPEAL_STATES = {open: "открыта", upheld: "оценка подтверждена", revised: "оценка изменена"};
  const KIND_LABELS = {binary: "да / нет", discrete: "шкала", critical: "грубая ошибка"};
  const FIELD_LABELS = {title: "название", instructions: "формулировка", weight: "вес", levels: "уровни шкалы", anchors: "описания уровней",
    na_condition: "условие N/A", "questions.0.question": "первый атомарный вопрос"};
  async function api(path, options) {
    let response;
    try {response = await fetch(path, options);}
    catch (_) {throw new Error("Локальный сервер CQA недоступен. Запустите его (см. README), обновите страницу и повторите.");}
    const value = await response.json().catch(() => ({}));
    if (!response.ok) {const error = new Error(value.error || "Запрос к локальному серверу не выполнен."); error.details = value; error.status = response.status; throw error;}
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
    $("mode").textContent = provider === "mock" ? "ТЕСТОВАЯ ЗАГЛУШКА — фиксированные ответы без ИИ, это не оценка качества. Работает только с чек-листами v2/v3." :
      provider === "replay" ? "ПОВТОР — заново проверяет записанный настоящий ответ модели (p1-ru-001, чек-лист v5). Нового вызова нет." :
      "OpenAI — настоящая оценка ИИ; результат будет только при успешном ответе модели.";
    $("model").disabled = mock || busy;
    const ready = mock || (config?.openai_key_present && (config?.external_synthetic_allowed || config?.external_authorized_allowed) &&
      config?.live_calls_remaining !== 0 && $("model").value.trim());
    $("evaluate").disabled = busy || !(current || pasted) || !ready;
    if (!mock && !ready) feedback(config?.live_calls_remaining === 0 ? "Лимит живых вызовов исчерпан — новый платный запрос отправить нельзя." :
      "Для OpenAI серверу нужны ключ, разрешение на внешние вызовы и явно указанная модель. Запрос не отправлялся.");
    renderHint();
  }
  // Which provider × checklist × conversation combinations can produce a score — explained before Evaluate is clicked.
  const decisionPaths = new Map(); // "checklist_id\0version" → "legacy" | "atomic_first"
  function liveReady() {
    return Boolean(config?.openai_key_present && (config?.external_synthetic_allowed || config?.external_authorized_allowed) && config?.live_calls_remaining !== 0);
  }
  function checklistValue(version) {return `${config.checklist.checklist_id}\u0000${version}`;}
  function useRecording(recording) {
    $("provider").value = "replay"; $("language").value = "";
    $("checklist").value = checklistValue(recording.checklist_version);
    filter(recording.conversation_id);
  }
  function compatibility() {
    const provider = $("provider").value, path = decisionPaths.get($("checklist").value);
    const recordings = config?.replay_recordings || [];
    if (provider === "mock" && path === "atomic_first") {
      const legacyList = checklists.filter(c => decisionPaths.get(`${c.checklist_id}\u0000${c.version}`) === "legacy");
      const legacy = legacyList.find(c => /\.v3$/.test(c.version)) || legacyList[0];
      return {text: "Тестовая заглушка не умеет отвечать на атомарные факты чек-листов v4–v7, поэтому оценка будет отклонена (так задумано). " +
        "Для проверки интерфейса возьмите чек-лист v2/v3, для настоящей оценки — OpenAI.",
        fix: legacy && `Взять ${legacy.version}`, apply: legacy && (() => {$("checklist").value = `${legacy.checklist_id}\u0000${legacy.version}`; clearResult(); updateMode();})};
    }
    if (provider === "replay" && !recordings.some(r => !pasted && r.conversation_id === $("conversation").value && $("checklist").value === checklistValue(r.checklist_version))) {
      const first = recordings[0];
      return {text: "Повтор есть только для записанной пары диалог + чек-лист" + (first ? ` (${first.conversation_id} + ${first.checklist_version}). ` : ". ") +
        "Для других диалогов нужен OpenAI.", fix: first && !pasted && `Перейти на ${first.conversation_id} + ${first.checklist_version}`, apply: first && !pasted && (() => useRecording(first))};
    }
    if (provider === "openai" && !liveReady()) {
      return {text: "OpenAI на этом сервере не настроен (нет ключа, разрешения или лимит живых вызовов 0). Настоящая оценка невозможна, пока сервер не запущен в живом режиме.",
        fix: recordings[0] && "Показать повтор записанного ответа", apply: recordings[0] && (() => useRecording(recordings[0]))};
    }
    return null;
  }
  function renderHint() {
    const box = $("cqa-hint"), hint = config ? compatibility() : null;
    box.hidden = !hint;
    if (!hint) return box.replaceChildren();
    box.replaceChildren(el("span", hint.text));
    if (hint.apply) {const fix = el("button", hint.fix, "cqa-link-button"); fix.type = "button"; fix.onclick = hint.apply; box.append(" ", fix);}
  }
  function clearResult() {
    result = null; rejected = null; $("download").disabled = true;
    $("results").replaceChildren(); $("run-summary").textContent = "Для этого выбора оценки ещё нет.";
    renderAppealsPanel(null);
  }
  function showConversation(conversation) {
    current = conversation; pasted = null;
    $("conversation-title").textContent = conversation.conversation_id;
    $("conversation-meta").textContent = `${conversation.language} · ${conversation.channel} · реплик: ${conversation.messages.length} · исходный порядок`;
    recordingLink(conversation.channel, conversation.audio_url);
    window.CqaTranscript.render($("transcript"), conversation);
    localizeTranscript(conversation.messages);
  }
  // The shared renderer (also used by human review) writes an English meta line; here it is shown in Russian.
  // Turn numbers are 1-based, as in the evidence buttons and the official evidence_turns.
  function localizeTranscript(messages) {
    $("transcript").querySelectorAll(".message").forEach((node, index) => {
      const m = messages[index] || {}, meta = node.querySelector(".meta");
      const original = "source_message_id" in m ? m.source_message_id : (m.message_id ?? null);
      if (meta) meta.textContent = `№${index + 1} · время ${m.timestamp ?? "не указано"}${original === null || original === undefined ? "" : " · ID в источнике: " + original}`;
    });
  }
  // Call recording: a plain link in the transcript header (no <audio>: the CSP has no media-src). Shown only for a
  // voice conversation with an https audio_url, from the backend response or a pasted voice record. The signed URL
  // itself is never printed, logged or sent anywhere by the UI.
  function recordingLink(channel, url) {
    let safe = false;
    try {safe = (channel === "voice" || channel === "voice call") && typeof url === "string" && new URL(url).protocol === "https:";}
    catch (_) {safe = false;}
    if (!safe) return;
    const link = document.createElement("a"); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer";
    link.textContent = "Открыть запись"; link.className = "cqa-recording-link";
    $("conversation-meta").append(" · ", link);
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
      feedback("Транскрипт загружен. Оценка ещё не запускалась."); updateMode(); loadHistory();
    } catch (error) {if (requestSequence === sequence) feedback(error.message, true);}
  }
  function filter(selectId) {
    const filtered = records.filter(r => !$("language").value || r.language === $("language").value);
    $("conversation").replaceChildren(...filtered.map(r => new Option(`${r.conversation_id} · ${r.language}`, r.conversation_id)));
    $("conversation").disabled = !filtered.length;
    if (typeof selectId === "string" && filtered.some(r => r.conversation_id === selectId)) $("conversation").value = selectId;
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
    for (const card of $("results").querySelectorAll(".result-card")) addAppealShortcut(card);
    $("download").disabled = false;
    loadAppeals();
  }
  // Card shortcut to the existing appeal form: switch tab, preselect the criterion, focus the comment.
  function addAppealShortcut(card) {
    const button = el("button", "Оспорить", "cqa-appeal-shortcut"); button.type = "button";
    button.setAttribute("aria-label", `Оспорить критерий ${card.dataset.criterionId}`);
    button.onclick = () => {
      showTab("history-appeals");
      $("appeal-criterion").value = card.dataset.criterionId; fillRequested();
      $("appeal-explanation").focus();
    };
    card.append(button);
  }
  function showRejected(diagnostic) {
    rejected = diagnostic; result = null;
    if (!current || current.conversation_id !== diagnostic.conversation.conversation_id) showConversation(diagnostic.conversation);
    renderFailure(diagnostic, $("results"), $("run-summary")); $("download").disabled = false;
    renderAppealsPanel(null);
  }
  function errorCard(error) {
    const card = el("article", undefined, "cqa-error-card");
    card.append(el("h3", `Оценка не выполнена${error.status ? " · HTTP " + error.status : ""}`), el("p", error.message),
      el("p", error.status === 403 ? "Что делать: для вставленного диалога нужно локальное разрешение владельца (файл approvals, см. TEAM_START_HERE.md). Сервер отказал до вызова модели — ничего не оценено и не сохранено." :
        error.status === 409 ? "Что делать: уже идёт другая оценка или версия чек-листа конфликтует. Подождите и повторите." :
          "Что делать: проверьте выбор выше и повторите. Оценка не выставлена.", "notice"));
    return card;
  }
  $("evaluate").onclick = async () => {
    if (busy || !(current || pasted)) return;
    busy = true; clearResult(); updateMode();
    for (const id of ["conversation", "language", "provider", "checklist"]) $(id).disabled = true;
    $("results").setAttribute("aria-busy", "true"); feedback("Идёт оценка…");
    try {
      const body = {provider: $("provider").value, model: $("provider").value === "openai" ? $("model").value.trim() : null};
      if (pasted) body.conversation = pasted; else body.conversation_id = current.conversation_id;
      const checklist = selectedChecklist(); if (checklist) body.checklist = checklist;
      showResult(await post("/api/evaluations", body));
      feedback(result.run.provider === "replay" ? "Записанный настоящий ответ модели перепроверен и оценён — нового вызова нет." :
        result.run.is_mock ? "Заглушка отработала — смысловой оценки качества не было." : "Оценка LLM готова — проверьте доказательства и пометки «требует проверки».");
    } catch (error) {
      feedback(error.status === 403 ? `${error.message} — для вставленного диалога нужно разрешение владельца (см. TEAM_START_HERE.md).` : error.message, true);
      $("run-summary").textContent = "Оценка не удалась. Баллов нет.";
      if (!error.details?.diagnostic_id) $("results").replaceChildren(errorCard(error));
      if (error.details?.diagnostic_id) {
        try {showRejected(await api("/api/diagnostics/" + error.details.diagnostic_id));}
        catch (_) {feedback("Оценка не удалась; диагностика сохранена на сервере.", true);}
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
      if (!value?.record?.transcript?.length) throw new Error("В JSON нужен record.transcript хотя бы с одной репликой.");
      clearResult(); current = null; pasted = value;
      $("conversation-title").textContent = `${value.record.conversation_id} (вставлен)`;
      $("conversation-meta").textContent = `${value.record.language} · ${value.record.channel} · реплик: ${value.record.transcript.length} · ещё не нормализован`;
      recordingLink(value.record.channel, value.record.audio_url);
      window.CqaTranscript.render($("transcript"), value.record);
      localizeTranscript(value.record.transcript);
      feedback("Вставленный транскрипт показан. Нажмите «Оценить» — сервер сначала проверит разрешение владельца."); updateMode();
    } catch (error) {feedback(`Некорректный JSON диалога: ${error.message}`, true);}
  };

  // History
  async function loadHistory() {
    const all = $("history-all").checked, id = current?.conversation_id;
    try {
      const rows = await api("/api/evaluations" + (!all && id ? "?conversation_id=" + encodeURIComponent(id) : ""));
      $("history").replaceChildren(...(rows.length ? rows.map(historyRow) : [emptyRow("Сохранённых оценок пока нет.")]));
    } catch (error) {$("history").replaceChildren(emptyRow(error.message));}
  }
  function emptyRow(text) {const tr = el("tr"); const td = el("td", text, "empty"); td.colSpan = 8; tr.append(td); return tr;}
  function historyRow(row) {
    const tr = el("tr");
    const status = row.kind === "rejected" ? `${statusLabel("rejected")} (замечаний: ${row.issues})` : statusLabel(row.status);
    const appeals = row.kind === "rejected" ? "—" : `открыто ${row.appeals_open} · пересмотрено ${row.appeals_revised}`;
    const pill = el("span", status, "cqa-pill"), statusCell = el("td");
    pill.dataset.status = row.kind === "rejected" ? "rejected" : row.status; pill.title = `status: ${pill.dataset.status}`; statusCell.append(pill);
    tr.append(el("td", (row.started_at || "").replace("T", " ").slice(0, 19)), el("td", row.conversation_id),
      el("td", row.checklist_version), el("td", `${row.provider} · ${row.model}`), statusCell,
      el("td", row.total_score ?? "—"), el("td", appeals));
    const td = el("td"), open = el("button", "Открыть"); open.type = "button";
    open.onclick = async () => {
      try {
        if (row.kind === "rejected") showRejected(await api("/api/diagnostics/" + row.evaluation_id));
        else showResult(await api("/api/evaluations/" + row.evaluation_id));
        showTab("evaluation"); $("results").scrollTop = 0;
        feedback(`Открыта сохранённая ${row.kind === "rejected" ? "отклонённая оценка" : "оценка"} ${row.evaluation_id}. Новая оценка не запускалась.`);
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
      $("comparison").replaceChildren(el("p", rejected ? "У отклонённой оценки нет принятых баллов — оспаривать нечего, запустите оценку заново." :
        "Откройте принятую оценку, чтобы увидеть апелляции.", "empty"));
      $("appeals").replaceChildren(el("p", "Апелляций нет.", "empty"));
      $("appeal-criterion").replaceChildren(); $("appeal-requested").replaceChildren();
      return;
    }
    const keep = $("appeal-criterion").value;
    $("appeal-criterion").replaceChildren(...result.checklist.criteria.map(c => new Option(`${c.criterion_id} · ${titleOf(c)}`, c.criterion_id)));
    if (keep && result.checklist.criteria.some(c => c.criterion_id === keep)) $("appeal-criterion").value = keep;
    fillRequested();
    if (!view) return;
    renderComparison(view, result.checklist, $("comparison"));
    $("appeals").replaceChildren(...(view.appeals.length ? view.appeals.map(appealCard) : [el("p", "Апелляций нет.", "empty")]));
    markAppeals(view);
  }
  // The evaluation card also shows the appeal outcome: original stays, decision and final result are added.
  function markAppeals(view) {
    const hero = $("results").querySelector(".cqa-score-hero");
    hero?.querySelector(".cqa-hero-revised")?.remove();
    if (hero && view.revised_score) hero.append(el("p", `После апелляции: ${view.revised_score.total_score ?? "не рассчитан"} / 100 · грубое нарушение: ${
      view.revised_score.critical_violation ? "да" : "нет"} · исходный итог ${view.original_score.total_score ?? "не рассчитан"} сохранён`, "cqa-hero-revised"));
    for (const card of $("results").querySelectorAll(".result-card[data-criterion-id]")) {
      card.querySelector(".cqa-appeal-note")?.remove();
      const appeal = [...view.appeals].reverse().find(a => a.criterion_id === card.dataset.criterionId);
      if (!appeal) continue;
      const note = el("p", appeal.decision ? `Апелляция: оценка ${appeal.decision.outcome === "change" ? "изменена" : "подтверждена"} (проверяющий ${appeal.decision.reviewer}): ` +
        `${answerLabel(appeal.original_response)} → итог ${answerLabel(appeal.decision.final_response)}. Причина: ${appeal.decision.reason}` :
        `Апелляция открыта (запрошено: ${appeal.requested_response === null ? "пересмотр" : answerLabel(appeal.requested_response)}): ${appeal.explanation}`, "cqa-appeal-note");
      note.dataset.state = appeal.state; card.querySelector("h3").after(note);
    }
  }
  // What the reviewer needs next to the appeal: the disputed score, its rationale and the cited dialogue fragment.
  function appealFragment(appeal) {
    const box = el("div", undefined, "cqa-fragment");
    const decision = (result.validated_evaluation || result.model_evaluation).decisions.find(d => d.criterion_id === appeal.criterion_id);
    const criterion = criterionOf(appeal.criterion_id), score = result.score.criteria.find(c => c.criterion_id === appeal.criterion_id);
    if (!decision || !criterion) return box;
    box.append(el("p", `Спорная оценка: ${responseText(decision, criterion)}${criterion.kind === "critical" ? " (отдельный флаг)" :
      ` · баллы ${score.earned_points} из итогового веса ${score.effective_weight}`}`, "cqa-disputed"), el("p", decision.rationale, "notice"),
      el("p", "Фрагмент диалога, на который ссылается оценка", "cqa-block-label"));
    const messages = new Map(result.conversation.messages.map(m => [m.message_id, m]));
    for (const reference of decision.evidence.slice(0, 3)) {
      const first = messages.get(reference.kind === "quote" ? reference.message_id : reference.start_message_id);
      const last = messages.get(reference.kind === "quote" ? reference.message_id : reference.end_message_id);
      const show = el("button", "Показать в транскрипте", "cqa-link-button"); show.type = "button";
      show.onclick = () => {showTab("evaluation"); jump(reference);};
      const label = el("p", reference.kind === "quote" ? `Реплика №${first ? first.source_index + 1 : "?"} · ${first?.source_speaker ?? ""} ` :
        `Проверенные реплики №${first ? first.source_index + 1 : "?"}–${last ? last.source_index + 1 : "?"} (${EVIDENCE_KINDS[reference.kind] ?? reference.kind}) `, "meta");
      label.append(show);
      box.append(label, reference.kind === "quote" ? el("blockquote", reference.quote) : el("p", reference.explanation, "notice"));
    }
    return box;
  }
  function criterionOf(id) {return result.checklist.criteria.find(c => c.criterion_id === id);}
  function responseOptions(select, criterion, blankLabel) {
    const options = permittedResponses(criterion).map(v => new Option(answerLabel(v), JSON.stringify(v)));
    if (blankLabel) options.unshift(new Option(blankLabel, ""));
    select.replaceChildren(...options);
  }
  function fillRequested() {
    const criterion = criterionOf($("appeal-criterion").value);
    if (criterion) responseOptions($("appeal-requested"), criterion, "(без конкретного запроса)");
  }
  $("appeal-criterion").onchange = fillRequested;
  function appealCard(appeal) {
    const card = el("article", undefined, `result-card appeal ${appeal.state}`);
    card.append(el("h3", `${appeal.criterion_id} · ${(APPEAL_STATES[appeal.state] ?? appeal.state).toUpperCase()}`),
      el("p", `Исходный ответ: ${answerLabel(appeal.original_response)} · запрошено: ${appeal.requested_response === null ? "—" : answerLabel(appeal.requested_response)} · автор: ${appeal.submitted_by} · ${appeal.submitted_at}`, "meta"),
      el("p", `Комментарий заявителя: ${appeal.explanation}`), appealFragment(appeal));
    if (appeal.decision) {
      card.append(el("p", `Проверяющий ${appeal.decision.reviewer}: ${appeal.decision.outcome === "change" ? "изменить" : "подтвердить"} → итог ${answerLabel(appeal.decision.final_response)} (${appeal.decision.decided_at})`, "raw"),
        el("p", `Причина проверяющего: ${appeal.decision.reason}`, "notice"));
    } else {
      const form = el("div", undefined, "form-grid");
      const outcome = el("select"); outcome.append(new Option("Подтвердить исходную оценку", "confirm"), new Option("Изменить оценку", "change"));
      const value = el("select"); responseOptions(value, criterionOf(appeal.criterion_id));
      const reason = el("textarea"); reason.placeholder = "Причина решения (обязательно)"; reason.maxLength = 4000;
      const submit = el("button", "Сохранить решение"); submit.type = "button";
      submit.onclick = async () => {
        const missing = !$("reviewer-name").value.trim() ? $("reviewer-name") : !$("reviewer-key").value ? $("reviewer-key") : !reason.value.trim() ? reason : null;
        if (missing) {
          feedback(missing === reason ? "Укажите причину решения." : missing.id === "reviewer-name" ? "Укажите имя проверяющего." : "Введите ключ проверяющего.", true);
          missing.focus(); return;
        }
        try {
          const body = {reviewer: $("reviewer-name").value.trim(), outcome: outcome.value, reason: reason.value.trim(),
            new_response: outcome.value === "change" ? JSON.parse(value.value) : null};
          const out = await post(`/api/appeals/${appeal.appeal_id}/decision`, body, {"X-CQA-Reviewer-Key": $("reviewer-key").value});
          renderAppealsPanel(out.view); loadHistory();
          feedback(out.view.revised_score ? `Решение сохранено. Новый итог ${out.view.revised_score.total_score}; исходный ${out.view.original_score.total_score} сохранён.` :
            "Решение сохранено: исходная оценка подтверждена.");
        } catch (error) {feedback(error.message, true);}
      };
      const l1 = el("label", "Решение"), l2 = el("label", "Новая оценка (если меняется)"), l3 = el("label", "Причина");
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
    const missing = !$("appeal-name").value.trim() ? $("appeal-name") : !$("appeal-explanation").value.trim() ? $("appeal-explanation") : null;
    if (missing) {
      feedback(missing.id === "appeal-name" ? "Укажите своё имя, чтобы подать апелляцию." : "Напишите комментарий, чтобы подать апелляцию.", true);
      missing.focus(); return;
    }
    try {
      const requested = $("appeal-requested").value;
      const out = await post(`/api/evaluations/${result.evaluation_id}/appeals`, {criterion_id: $("appeal-criterion").value,
        submitted_by: $("appeal-name").value.trim(), explanation: $("appeal-explanation").value.trim(),
        requested_response: requested ? JSON.parse(requested) : null});
      $("appeal-explanation").value = ""; renderAppealsPanel(out.view); loadHistory();
      feedback("Апелляция подана. Её подтверждает или меняет проверяющий — другой человек с ключом проверяющего.");
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
    await Promise.all(checklists.filter(c => !decisionPaths.has(`${c.checklist_id}\u0000${c.version}`)).map(c =>
      api("/api/checklists/" + c.sha256).then(full => decisionPaths.set(`${c.checklist_id}\u0000${c.version}`, full.decision_path || "legacy"))));
  }
  function versionExists(version) {return checklists.some(c => c.checklist_id === editing?.checklist_id && c.version === version);}
  async function loadEditor() {
    try {
      editing = await api("/api/checklists/" + $("editor-base").value);
      let suggestion = editing.version + "-edit";
      for (let n = 2; versionExists(suggestion); n++) suggestion = `${editing.version}-edit${n}`;
      $("editor-version").value = suggestion;
      syncJson(); renderEditor(); $("editor-save").disabled = false; $("editor-feedback").textContent = "";
    } catch (error) {$("editor-feedback").textContent = error.message;}
  }
  function syncJson() {$("editor-json").value = JSON.stringify(editing, null, 2);}
  function field(label, input, wide) {const l = el("label", label); if (wide) l.className = "wide"; l.append(input); return l;}
  // Structural edits keep the saved checklist valid for the backend validators: rules that only make
  // sense for the old answer type / N/A setting are removed together with the change.
  function setKind(criterion, kind) {
    criterion.kind = kind; criterion.consistency_rules = []; delete criterion.decision_rule;
    criterion.levels = kind === "discrete" ? [0, 5, 10] : [];
    criterion.anchors = kind === "discrete" ? {"0": "", "5": "", "10": ""} : {};
  }
  function setNa(criterion, allowed) {
    if (allowed) {
      const id = `${criterion.criterion_id}.na`;
      if (!criterion.questions.some(q => q.question_id === id)) criterion.questions.unshift({question_id: id, question: "Does the N/A condition hold for this conversation?"});
      criterion.applicability_rule = {question_id: id, na_when: "yes"}; criterion.na_condition = "";
    } else {
      criterion.na_condition = null; criterion.applicability_rule = null;
      criterion.consistency_rules = (criterion.consistency_rules || []).map(r => ({...r, permitted_responses: r.permitted_responses.filter(p => p !== "N/A")}))
        .filter(r => r.permitted_responses.length);
    }
  }
  function addCriterion() {
    const used = new Set(editing.criteria.map(c => c.criterion_id));
    let n = editing.criteria.length + 1; while (used.has(String(n).padStart(2, "0"))) n++;
    const id = String(n).padStart(2, "0");
    editing.criteria.push({criterion_id: id, title: "", instructions: "", kind: "binary", weight: 10, levels: [], anchors: {},
      na_condition: null, questions: [{question_id: `${id}.q1`, question: ""}], applicability_rule: null});
    syncJson(); renderEditor();
    $("editor-criteria").lastElementChild.querySelector("input")?.focus();
  }
  function ruleText(rule) {
    return `Правило решения: «да», только если ${rule.all_of.join(", ")} = да` + (rule.conditional ?
      `, и ${rule.conditional.requirement_question_id} = да, когда ${rule.conditional.trigger_question_id} = ${answerLabel(rule.conditional.required_when)}` : "") + ".";
  }
  function renderEditor() {
    const blocks = editing.criteria.map((criterion, index) => {
      const box = el("fieldset", undefined, "criterion");
      const atomicOutput = criterion.output_source === "atomic";
      box.append(el("legend", `${criterion.criterion_id} · ${KIND_LABELS[criterion.kind] ?? criterion.kind}${atomicOutput ? " · выводится из атомарных фактов" : ""}`));
      const tools = el("div", undefined, "cqa-criterion-tools");
      const kind = el("select"); kind.disabled = criterion.kind === "critical" || atomicOutput;
      kind.append(...(criterion.kind === "critical" ? [new Option("Флаг грубой ошибки (да/нет, без веса)", "critical")] :
        [new Option("Да / Нет", "binary"), new Option("Числовая шкала", "discrete")]));
      kind.value = criterion.kind;
      kind.onchange = () => {setKind(criterion, kind.value); syncJson(); renderEditor();};
      const na = el("input"); na.type = "checkbox"; na.checked = criterion.na_condition !== null; na.disabled = criterion.kind === "critical";
      na.onchange = () => {setNa(criterion, na.checked); syncJson(); renderEditor();};
      const naLabel = el("label", undefined, "inline"); naLabel.append(na, " N/A допускается");
      const remove = el("button", "Удалить критерий", "cqa-remove"); remove.type = "button";
      remove.onclick = () => {editing.criteria.splice(index, 1); syncJson(); renderEditor();};
      tools.append(field("Тип ответа", kind), naLabel, remove);
      box.append(tools);
      const title = el("input"); title.value = criterion.title; title.placeholder = "Название критерия (обязательно)";
      title.oninput = () => {criterion.title = title.value; syncJson();};
      const weight = el("input"); weight.type = "number"; weight.min = 0; weight.value = criterion.weight;
      weight.disabled = criterion.kind === "critical";
      weight.oninput = () => {criterion.weight = Number(weight.value); syncJson();};
      const instructions = el("textarea"); instructions.value = criterion.instructions; instructions.placeholder = "Формулировка: когда ответ «да» или какой уровень ставить (обязательно)";
      instructions.oninput = () => {criterion.instructions = instructions.value; syncJson();};
      const grid = el("div", undefined, "form-grid");
      grid.append(field("Название", title), field(criterion.kind === "critical" ? "Вес (у флага грубой ошибки веса нет)" : "Вес", weight),
        field("Формулировка (инструкция для оценки)", instructions, true));
      if (criterion.kind === "discrete") {
        const levels = el("input"); levels.value = criterion.levels.join(", ");
        levels.onchange = () => {
          const parsed = levels.value.split(",").map(v => Number(v.trim())).filter(v => Number.isInteger(v));
          criterion.levels = [...new Set(parsed)].sort((a, b) => a - b);
          const anchors = {}; for (const level of criterion.levels) anchors[String(level)] = criterion.anchors[String(level)] ?? "";
          criterion.anchors = anchors; syncJson(); renderEditor();
        };
        grid.append(field("Уровни шкалы через запятую (обязательно 0)", levels, true));
        for (const level of criterion.levels) {
          const anchor = el("textarea"); anchor.value = criterion.anchors[String(level)] ?? "";
          anchor.oninput = () => {criterion.anchors[String(level)] = anchor.value; syncJson();};
          grid.append(field(`Описание уровня ${level}`, anchor, true));
        }
      }
      if (criterion.na_condition !== null) {
        const na = el("textarea"); na.value = criterion.na_condition; na.placeholder = "Когда допускается N/A (обязательно)";
        na.oninput = () => {criterion.na_condition = na.value; syncJson();};
        grid.append(field(`N/A допускается, только если (вопрос применимости ${criterion.applicability_rule?.question_id})`, na, true));
      } else grid.append(el("p", criterion.kind === "critical" ? "Флаг грубой ошибки не может быть N/A." : "N/A для этого критерия не допускается.", "notice"));
      if (criterion.decision_rule) {
        const rule = el("p", ruleText(criterion.decision_rule), "notice cqa-rule");
        if (!atomicOutput) {
          const drop = el("button", "Убрать правило", "cqa-link-button"); drop.type = "button";
          drop.onclick = () => {delete criterion.decision_rule; syncJson(); renderEditor();};
          rule.append(" ", drop);
        }
        grid.append(rule);
      }
      for (const question of criterion.questions) {
        const q = el("textarea"); q.value = question.question; q.placeholder = "Атомарный вопрос, на который отвечает оценщик (обязательно)";
        q.oninput = () => {question.question = q.value; syncJson();};
        grid.append(field(`Атомарный вопрос ${question.question_id}`, q, true));
      }
      box.append(grid); box.dataset.index = index; return box;
    });
    const add = el("button", "Добавить критерий", "cqa-add-criterion"); add.type = "button"; add.onclick = addCriterion;
    const head = el("div", undefined, "cqa-editor-summary");
    head.append(el("p", `Критериев: ${editing.criteria.length} · путь решения: ${editing.decision_path || "legacy"} · источник: ${editing.source}`, "notice"), add);
    $("editor-criteria").replaceChildren(head, ...blocks);
  }
  // "criteria.4.weight" → "criterion 05 · weight": server field paths in terms the editor shows.
  function fieldLabel(path) {
    const [root, index, ...rest] = path.split(".");
    const id = root === "criteria" ? editing?.criteria?.[index]?.criterion_id : undefined;
    return id ? `критерий ${id}${rest.length ? " · " + (FIELD_LABELS[rest.join(".")] ?? rest.join(".")) : ""}` : path;
  }
  $("editor-base").onchange = loadEditor;
  $("editor-apply").onclick = () => {
    try {editing = JSON.parse($("editor-json").value); renderEditor(); $("editor-feedback").textContent = "Форма обновлена из JSON.";}
    catch (error) {$("editor-feedback").textContent = `Некорректный JSON: ${error.message}`;}
  };
  $("editor-save").onclick = async () => {
    try {
      const body = JSON.parse($("editor-json").value);
      body.version = $("editor-version").value.trim();
      if (versionExists(body.version)) throw new Error(`версия «${body.version}» уже существует (сохранённые версии не меняются) — введите новое имя версии`);
      const saved = await post("/api/checklists", body);
      await loadChecklists(`${saved.checklist_id}\u0000${saved.version}`);
      $("editor-base").value = saved.sha256;
      $("editor-feedback").textContent = `Сохранено: ${saved.checklist_id} · ${saved.version} (sha256 ${saved.sha256.slice(0, 12)}…). Версия выбрана в поле «Чек-лист» для следующей оценки. `;
      const go = el("button", "Оценить с этой версией →", "cqa-link-button"); go.type = "button";
      go.onclick = () => {showTab("evaluation"); $("evaluate").focus();};
      $("editor-feedback").append(go);
      clearResult(); updateMode(); go.focus();
    } catch (error) {
      $("editor-feedback").textContent = `Не сохранено: ${error.message}${error.details?.fields ? " — проверьте: " + error.details.fields.map(fieldLabel).join(", ") : ""}`;
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
    if ($("provider").value === "replay") feedback("Повтор работает только для записанной пары: диалог p1-ru-001 и чек-лист 2026-11-07.v5.");
  };
  $("model").oninput = () => {clearResult(); updateMode();};
  Promise.all([api("/api/config"), api("/api/conversations")]).then(async ([settings, data]) => {
    config = settings; records = data; $("model").value = settings.model;
    await loadChecklists(); await loadEditor();
    // First click should produce a score: real OpenAI when this server is configured for it, otherwise the
    // recorded genuine reply (Replay). Mock with the production (atomic) checklist is always refused by design.
    const recording = (config.replay_recordings || [])[0];
    if (liveReady()) {$("provider").value = "openai"; filter();}
    else if (recording && records.some(r => r.conversation_id === recording.conversation_id)) useRecording(recording);
    else filter();
    const diagnosticId = new URL(window.location.href).searchParams.get("diagnostic");
    if (diagnosticId) {
      showRejected(await api("/api/diagnostics/" + encodeURIComponent(diagnosticId)));
      feedback("Сохранённый ответ отклонён проверкой. Итога нет, новый запрос к модели не отправлялся.", true);
    }
  }).catch(error => feedback(error.message, true));
})();
