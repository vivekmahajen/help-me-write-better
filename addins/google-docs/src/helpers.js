// Pure helpers for the Google Docs add-on. Plain function declarations (no
// import/export) so this file works both as an Apps Script project file (globals
// are shared across .gs/.js files) AND is importable for side-effect by the Node
// tests (which then read globalThis.WBDocs). The Google-specific code lives in
// Code.gs; this is the testable logic.

function wbBuildCheckBody(text, previous) {
  return previous != null ? { text: text, previous: previous } : { text: text };
}

var WB_SEV_ORDER = { high: 0, medium: 1, low: 2 };

function wbSortSuggestions(suggestions) {
  return suggestions.slice().sort(function (a, b) {
    return (WB_SEV_ORDER[a.severity] === undefined ? 3 : WB_SEV_ORDER[a.severity]) -
           (WB_SEV_ORDER[b.severity] === undefined ? 3 : WB_SEV_ORDER[b.severity]) ||
           a.range.start - b.range.start;
  });
}

function wbSliceForRange(text, range) {
  return text.slice(range.start, range.end);
}

function wbFormatSuggestion(s) {
  var fix = (s.replacements && s.replacements.length) ? " → " + (s.replacements[0] || "(delete)") : "";
  return "[" + s.severity + "] " + s.message + fix;
}

// Escape a literal string for Apps Script Body.replaceText (which takes a regex).
function wbEscapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

if (typeof globalThis !== "undefined") {
  globalThis.WBDocs = {
    wbBuildCheckBody: wbBuildCheckBody,
    wbSortSuggestions: wbSortSuggestions,
    wbSliceForRange: wbSliceForRange,
    wbFormatSuggestion: wbFormatSuggestion,
    wbEscapeRegex: wbEscapeRegex,
  };
}
