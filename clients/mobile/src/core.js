// Portable core shared by the mobile app and the custom keyboard (iOS keyboard
// extension / Android IME). Pure JS, no React Native / native deps, so it's
// testable and reusable from a JS bridge. The actual gateway calls are injected
// (`check`/`improve`) — the app wires them to the SDK; server-side metering means
// plan caps are enforced regardless of surface.

export function debounce(fn, wait) {
  let timer;
  const debounced = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
  debounced.cancel = () => clearTimeout(timer);
  return debounced;
}

export function applyReplacement(text, range, replacement) {
  return text.slice(0, range.start) + replacement + text.slice(range.end);
}

export function severityColor(severity) {
  return { high: "#dc2626", medium: "#d97706", low: "#2563eb" }[severity] || "#2563eb";
}

// Debounced "as you type" controller. `check(text, previous)` and
// `improve(req)` are injected (SDK-backed). Tracks previous text for the
// server-side changed-sentence diff.
export class CheckController {
  constructor({ check, improve, debounceMs = 600 }) {
    this._check = check;
    this._improve = improve;
    this.previous = null;
    this.suggestions = [];
    this._debounced = debounce((text, cb) => this._run(text, cb), debounceMs);
  }

  onInput(text, cb) {
    this._debounced(text, cb);
  }

  async _run(text, cb) {
    let res;
    try {
      res = await this._check(text, this.previous);
    } catch (e) {
      if (cb) cb([], e);
      return;
    }
    this.previous = text;
    this.suggestions = (res && res.suggestions) || [];
    if (cb) cb(this.suggestions, null);
  }

  // Keyboard "rewrite" action — send text to the engine and return the result.
  async rewrite(text, service = "clarify") {
    const res = await this._improve({ text, services: service, format: "plain" });
    return res.text;
  }
}
