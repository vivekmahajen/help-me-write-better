// API helper + config for the Word task pane. Mirrors the engine's POST /
// contract. The engine URL is stored in localStorage (set in the task pane).

const WB_SERVICES = [
  "clarify", "correct", "tighten", "retone", "paraphrase",
  "summarize", "reply", "send-check", "dictate", "confidential",
];

function wbApiBase() {
  return (localStorage.getItem("wbApiBase") || "http://localhost:8000").replace(/\/+$/, "");
}

function wbSetApiBase(value) {
  localStorage.setItem("wbApiBase", (value || "").trim().replace(/\/+$/, ""));
  return wbApiBase();
}

async function wbImprove(text, service, apiBase) {
  const res = await fetch(apiBase + "/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, services: [service], format: "plain" }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
  return data.text;
}
