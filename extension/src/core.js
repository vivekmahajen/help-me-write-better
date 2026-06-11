// Pure, DOM-light logic for the extension — shared by the content script and the
// unit tests. Loaded as a classic content script (it has no import/export, just
// sets globalThis.WBCore), and imported for side-effect by the Node tests.

function debounce(fn, wait) {
  let timer;
  const debounced = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
  debounced.cancel = () => clearTimeout(timer);
  return debounced;
}

// Works on a minimal element-like object so it's testable without a DOM.
function isEditableElement(el) {
  if (!el) return false;
  if (el.disabled || el.readOnly) return false;
  if (el.isContentEditable) return true;
  const tag = (el.tagName || "").toLowerCase();
  if (tag === "textarea") return true;
  if (tag === "input") {
    const type = (el.type || "text").toLowerCase();
    return ["text", "search", "email", "url", ""].includes(type);
  }
  return false;
}

function getText(el) {
  if (el == null) return "";
  return typeof el.value === "string" ? el.value : (el.textContent || "");
}

function setText(el, text) {
  if (typeof el.value === "string") {
    el.value = text;
  } else {
    el.textContent = text;
  }
}

// Apply one accepted suggestion to a string. Ranges are char offsets.
function applySuggestion(text, range, replacement) {
  return text.slice(0, range.start) + replacement + text.slice(range.end);
}

function severityClass(severity) {
  return `wb-sev-${["low", "medium", "high"].includes(severity) ? severity : "low"}`;
}

// Orchestrates debounced checking and tracks the previous text so the server can
// diff to only-changed sentences. `sendCheck(text, previous)` is injected (the
// content script wires it to the background worker; tests pass a fake).
class SuggestionEngine {
  constructor({ sendCheck, debounceMs = 500 }) {
    this.sendCheck = sendCheck;
    this.previous = null;
    this.suggestions = [];
    this._run = this._run.bind(this);
    this._debounced = debounce((text, cb) => this._run(text, cb), debounceMs);
  }

  onInput(text, cb) {
    this._debounced(text, cb);
  }

  async _run(text, cb) {
    let res;
    try {
      res = await this.sendCheck(text, this.previous);
    } catch (e) {
      if (cb) cb([], e);
      return;
    }
    this.previous = text;
    this.suggestions = (res && res.suggestions) || [];
    if (cb) cb(this.suggestions, null);
  }
}

const WBCore = {
  debounce, isEditableElement, getText, setText,
  applySuggestion, severityClass, SuggestionEngine,
};

if (typeof globalThis !== "undefined") globalThis.WBCore = WBCore;
