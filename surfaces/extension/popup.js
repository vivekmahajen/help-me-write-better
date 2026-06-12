const $ = (id) => document.getElementById(id);

function fillServices(selected) {
  $("service").innerHTML = WB_SERVICES
    .map((s) => `<option${s === selected ? " selected" : ""}>${s}</option>`)
    .join("");
}

async function init() {
  const cfg = await wbConfig();
  fillServices(cfg.service);
}

function improve() {
  const text = $("text").value.trim();
  if (!text) { $("meta").textContent = "Enter some text."; return; }
  $("go").disabled = true; $("meta").textContent = "Polishing…"; $("copy").hidden = true;
  chrome.runtime.sendMessage({ type: "wb-improve", text, service: $("service").value }, (resp) => {
    $("go").disabled = false;
    if (chrome.runtime.lastError || !resp) {
      $("meta").textContent = "No response from the engine.";
      return;
    }
    if (resp.ok) {
      $("out").value = resp.text; $("meta").textContent = ""; $("copy").hidden = false;
    } else {
      $("meta").textContent = "Error: " + resp.error;
    }
  });
}

$("go").addEventListener("click", improve);
$("copy").addEventListener("click", () => navigator.clipboard.writeText($("out").value));
$("opts").addEventListener("click", () => chrome.runtime.openOptionsPage());
init();
