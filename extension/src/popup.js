const DEFAULTS = { baseUrl: "http://localhost:8000", apiKey: "", enabled: true };

async function render() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  document.getElementById("state").textContent =
    cfg.apiKey ? `Connected to ${new URL(cfg.baseUrl).host}` : "Not configured — open Settings";
  document.getElementById("toggle").textContent = cfg.enabled ? "On" : "Off";
}

document.getElementById("toggle").addEventListener("click", async () => {
  const { enabled } = await chrome.storage.sync.get({ enabled: true });
  await chrome.storage.sync.set({ enabled: !enabled });
  render();
});

document.getElementById("opts").addEventListener("click", () => chrome.runtime.openOptionsPage());

render();
