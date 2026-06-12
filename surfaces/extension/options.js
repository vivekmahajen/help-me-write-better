const $ = (id) => document.getElementById(id);

async function init() {
  const cfg = await wbConfig();
  $("apiBase").value = cfg.apiBase;
  $("service").innerHTML = WB_SERVICES
    .map((s) => `<option${s === cfg.service ? " selected" : ""}>${s}</option>`)
    .join("");
}

async function save() {
  const apiBase = $("apiBase").value.trim().replace(/\/+$/, "");
  const service = $("service").value;
  let origin;
  try {
    origin = new URL(apiBase).origin + "/*";
  } catch (e) {
    $("status").textContent = "That doesn’t look like a valid URL.";
    return;
  }
  // Ask for host permission for the chosen origin so the worker can fetch it.
  const granted = await chrome.permissions.request({ origins: [origin] }).catch(() => false);
  if (!granted) {
    $("status").textContent = "Permission denied for " + origin;
    return;
  }
  await chrome.storage.sync.set({ apiBase, service });
  $("status").textContent = "Saved ✓";
}

$("save").addEventListener("click", save);
init();
