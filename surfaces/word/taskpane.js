const $ = (id) => document.getElementById(id);

function status(msg) { $("status").textContent = msg; }

Office.onReady((info) => {
  if (info.host !== Office.HostType.Word) {
    status("This add-in runs in Microsoft Word.");
    return;
  }
  $("service").innerHTML = WB_SERVICES.map((s) => `<option>${s}</option>`).join("");
  $("apiBase").value = wbApiBase();
  $("go").disabled = false;
  status("Select text in the document, then Improve.");
  $("go").addEventListener("click", improve);
  $("save").addEventListener("click", () => status("Saved engine URL: " + wbSetApiBase($("apiBase").value)));
});

// Read the current selection's plain text via the Word API.
function readSelection() {
  return Word.run(async (ctx) => {
    const sel = ctx.document.getSelection();
    sel.load("text");
    await ctx.sync();
    return sel.text;
  });
}

// Replace the current selection with improved text.
function writeSelection(text) {
  return Word.run(async (ctx) => {
    const sel = ctx.document.getSelection();
    sel.insertText(text, Word.InsertLocation.replace);
    await ctx.sync();
  });
}

async function improve() {
  $("go").disabled = true;
  try {
    const text = (await readSelection()).trim();
    if (!text) { status("Select some text in the document first."); return; }
    status("Polishing…");
    const out = await wbImprove(text, $("service").value, wbApiBase());
    await writeSelection(out);
    status("Improved ✓");
  } catch (e) {
    status("Error: " + (e.message || e));
  } finally {
    $("go").disabled = false;
  }
}
