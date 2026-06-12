// Content script: replace the user's selection in-place with the improved text,
// or fall back to the clipboard when the field can't be edited.

function wbReplaceSelection(text) {
  const el = document.activeElement;
  // Plain inputs / textareas
  if (el && (el.tagName === "TEXTAREA"
      || (el.tagName === "INPUT" && /^(text|search|email|url|tel|)$/.test(el.type || "")))) {
    const s = el.selectionStart, e = el.selectionEnd;
    if (s != null && e != null && e > s) {
      el.value = el.value.slice(0, s) + text + el.value.slice(e);
      el.selectionStart = el.selectionEnd = s + text.length;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    }
  }
  // contenteditable / rich editors
  const sel = window.getSelection();
  if (sel && sel.rangeCount && !sel.isCollapsed) {
    const range = sel.getRangeAt(0);
    range.deleteContents();
    range.insertNode(document.createTextNode(text));
    sel.collapseToEnd();
    return true;
  }
  return false;
}

function wbToast(message, ok) {
  const d = document.createElement("div");
  d.textContent = message;
  d.style.cssText =
    "position:fixed;z-index:2147483647;bottom:16px;right:16px;max-width:340px;" +
    "padding:10px 14px;border-radius:8px;font:13px/1.4 system-ui,sans-serif;" +
    "color:#fff;box-shadow:0 6px 20px rgba(0,0,0,.35);background:" +
    (ok ? "#1f7a4d" : "#a33");
  document.body.appendChild(d);
  setTimeout(() => d.remove(), 4500);
}

chrome.runtime.onMessage.addListener((msg) => {
  if (!msg) return;
  if (msg.type === "wb-replace") {
    if (wbReplaceSelection(msg.text)) {
      wbToast("Improved ✓", true);
    } else {
      navigator.clipboard.writeText(msg.text).catch(() => {});
      wbToast("Improved text copied to clipboard (this field can’t be edited).", true);
    }
  } else if (msg.type === "wb-error") {
    wbToast("Error: " + msg.message, false);
  }
});
