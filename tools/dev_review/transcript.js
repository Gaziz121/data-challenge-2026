/* Shared read-only renderer. No labels, scores, storage, requests or engine imports. */
(function (root) {
  "use strict";
  function render(container, record) {
    const doc = container.ownerDocument;
    const fragment = doc.createDocumentFragment();
    const messages = record.transcript || record.messages;
    function el(tag, text, cls) {
      const node = doc.createElement(tag);
      if (text !== undefined) node.textContent = text;
      if (cls) node.className = cls;
      return node;
    }
    messages.forEach((m, index) => {
      const speaker = m.speaker ?? m.source_speaker;
      const originalId = "source_message_id" in m ? m.source_message_id : (m.message_id ?? m.id ?? null);
      const article = el("article", undefined,
        `message ${["client", "operator", "bot", "system"].includes(speaker) ? speaker : ""}`);
      article.id = `message-${index}`;
      if (m.source_index !== undefined) article.dataset.messageId = m.message_id;
      article.append(el("div", speaker, "speaker"), el("div",
        `Index ${index} · Original message ID: ${originalId === null ? "not provided" : originalId} · Timestamp: ${m.timestamp ?? "not provided"}`, "meta"),
        el("div", m.text, "message-text"));
      fragment.append(article);
    });
    container.replaceChildren(fragment);
    container.scrollTop = 0;
  }
  const api = {render};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CqaTranscript = api;
})(typeof window !== "undefined" ? window : globalThis);
