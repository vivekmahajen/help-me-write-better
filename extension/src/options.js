const DEFAULTS = { baseUrl: "http://localhost:8000", apiKey: "", enabled: true };

async function load() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  document.getElementById("baseUrl").value = cfg.baseUrl;
  document.getElementById("apiKey").value = cfg.apiKey;
}

document.getElementById("save").addEventListener("click", async () => {
  const baseUrl = document.getElementById("baseUrl").value.trim();
  const apiKey = document.getElementById("apiKey").value.trim();
  await chrome.storage.sync.set({ baseUrl, apiKey });
  const status = document.getElementById("status");
  status.textContent = "Saved.";
  setTimeout(() => (status.textContent = ""), 1500);
});

load();
