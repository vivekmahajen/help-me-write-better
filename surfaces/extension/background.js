// Service worker: a right-click "Improve" context menu, plus the popup's
// improve requests. Keeping all fetches here centralizes host permissions.

importScripts("config.js");

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "wb-improve",
    title: "Improve with Help Me Write Better",
    contexts: ["selection", "editable"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "wb-improve" || !tab || !tab.id) return;
  const text = (info.selectionText || "").trim();
  if (!text) return;
  try {
    const cfg = await wbConfig();
    const improved = await wbImprove(text, cfg.service, cfg.apiBase);
    chrome.tabs.sendMessage(tab.id, { type: "wb-replace", text: improved });
  } catch (e) {
    chrome.tabs.sendMessage(tab.id, { type: "wb-error", message: String(e.message || e) });
  }
});

// The popup delegates the fetch here so the request runs with the worker's
// host permissions (and the popup staying open isn't required).
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.type !== "wb-improve") return;
  (async () => {
    try {
      const cfg = await wbConfig();
      const text = await wbImprove(msg.text, msg.service || cfg.service, cfg.apiBase);
      sendResponse({ ok: true, text });
    } catch (e) {
      sendResponse({ ok: false, error: String(e.message || e) });
    }
  })();
  return true; // keep the message channel open for the async reply
});
