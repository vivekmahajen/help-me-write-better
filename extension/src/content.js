// Content script. Detects editable fields (Gmail compose, generic textareas /
// contenteditable), debounces input, asks the background worker to check the
// text, and renders the shared suggestion model as a floating card with
// Fix / Dismiss actions.
//
// NOTE: Google Docs renders to <canvas>, so DOM injection does not work there —
// that surface is the Docs add-on (Phase 3). This targets Gmail + standard web
// fields, where DOM access works.

(() => {
  const { isEditableElement, getText, setText, applySuggestion, severityClass,
          SuggestionEngine } = globalThis.WBCore;

  const sendCheck = (text, previous) =>
    new Promise((resolve) =>
      chrome.runtime.sendMessage({ type: "check", text, previous }, resolve));

  const engines = new WeakMap();   // element -> SuggestionEngine
  let card = null;
  let activeEl = null;

  function engineFor(el) {
    if (!engines.has(el)) {
      engines.set(el, new SuggestionEngine({ sendCheck, debounceMs: 600 }));
    }
    return engines.get(el);
  }

  function onInput(ev) {
    const el = ev.target;
    if (!isEditableElement(el)) return;
    activeEl = el;
    engineFor(el).onInput(getText(el), (suggestions, err) => {
      if (err) return;
      renderCard(el, suggestions);
    });
  }

  function renderCard(el, suggestions) {
    if (!card) {
      card = document.createElement("div");
      card.className = "wb-card";
      document.body.appendChild(card);
    }
    if (!suggestions.length || el !== activeEl) {
      card.style.display = "none";
      return;
    }
    card.innerHTML = "";
    const header = document.createElement("div");
    header.className = "wb-card-header";
    header.textContent = `${suggestions.length} suggestion${suggestions.length > 1 ? "s" : ""}`;
    card.appendChild(header);

    for (const s of suggestions.slice(0, 8)) {
      const row = document.createElement("div");
      row.className = `wb-item ${severityClass(s.severity)}`;
      const msg = document.createElement("span");
      msg.className = "wb-msg";
      msg.textContent = s.message;
      row.appendChild(msg);
      if (s.replacements && s.replacements.length) {
        const fix = document.createElement("button");
        fix.className = "wb-fix";
        fix.textContent = `Fix → ${s.replacements[0] || "delete"}`;
        fix.addEventListener("click", () => applyFix(el, s));
        row.appendChild(fix);
      }
      const dismiss = document.createElement("button");
      dismiss.className = "wb-dismiss";
      dismiss.textContent = "✕";
      dismiss.title = "Dismiss";
      dismiss.addEventListener("click", () => {
        row.remove();
        if (!card.querySelector(".wb-item")) card.style.display = "none";
      });
      row.appendChild(dismiss);
      card.appendChild(row);
    }

    const rect = el.getBoundingClientRect();
    card.style.display = "block";
    card.style.top = `${window.scrollY + rect.bottom + 6}px`;
    card.style.left = `${window.scrollX + rect.left}px`;
  }

  function applyFix(el, suggestion) {
    const text = getText(el);
    const next = applySuggestion(text, suggestion.range, suggestion.replacements[0] || "");
    setText(el, next);
    el.dispatchEvent(new Event("input", { bubbles: true }));  // re-check from fresh text
  }

  document.addEventListener("input", onInput, true);
  document.addEventListener("focusin", (ev) => {
    if (isEditableElement(ev.target)) activeEl = ev.target;
  }, true);
  // Hide the card when focus leaves an editable field.
  document.addEventListener("focusout", () => {
    if (card) setTimeout(() => { if (card) card.style.display = "none"; }, 150);
  }, true);
})();
