"""The browser UI — a single self-contained HTML page (no external assets).

Served on ``GET /`` when the client accepts HTML. It talks to the same ``POST /``
JSON endpoint the API exposes, and populates its service/format controls from
``GET /`` (JSON) so it never drifts from the engine.
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Help Me Write Better</title>
<style>
  :root { --bg:#0f1221; --panel:#171b2e; --ink:#e8eaf2; --muted:#9aa3b8;
          --accent:#6ea8fe; --line:#283049; --ok:#3fb37f; --err:#e06c75; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  header { padding:20px 24px; border-bottom:1px solid var(--line); }
  header h1 { margin:0; font-size:20px; }
  header p { margin:4px 0 0; color:var(--muted); font-size:13px; }
  main { max-width:980px; margin:0 auto; padding:24px;
         display:grid; grid-template-columns:1fr 1fr; gap:20px; }
  @media (max-width:820px){ main { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--line);
           border-radius:12px; padding:16px; }
  label { display:block; font-size:12px; color:var(--muted);
          text-transform:uppercase; letter-spacing:.04em; margin:12px 0 6px; }
  textarea, select, input[type=text] { width:100%; background:#0c0f1c;
          color:var(--ink); border:1px solid var(--line); border-radius:8px;
          padding:10px; font:inherit; }
  textarea { min-height:200px; resize:vertical; }
  .row { display:flex; gap:12px; } .row > div { flex:1; }
  .chips { display:flex; flex-wrap:wrap; gap:8px; }
  .chip { display:inline-flex; align-items:center; gap:6px; padding:6px 10px;
          background:#0c0f1c; border:1px solid var(--line); border-radius:999px;
          cursor:pointer; font-size:13px; user-select:none; }
  .chip input { accent-color:var(--accent); }
  .opts { display:flex; align-items:center; gap:8px; margin-top:12px;
          color:var(--muted); font-size:13px; }
  .actions { display:flex; gap:10px; margin-top:16px; }
  button { flex:1; padding:11px; border:0; border-radius:8px;
           background:var(--accent); color:#0a0e1a; font-weight:600; font-size:15px;
           cursor:pointer; }
  button.secondary { background:transparent; color:var(--accent);
                     border:1px solid var(--line); font-weight:500; }
  button:disabled { opacity:.6; cursor:default; }
  .meta { color:var(--muted); font-size:12px; margin-bottom:8px; min-height:16px; }
  pre { white-space:pre-wrap; word-wrap:break-word; background:#0c0f1c;
        border:1px solid var(--line); border-radius:8px; padding:12px;
        min-height:200px; margin:0; }
  .err { color:var(--err); }
  .bar { display:flex; justify-content:space-between; align-items:center; }
  .copy { width:auto; margin:0; padding:5px 10px; font-size:12px;
          background:transparent; color:var(--accent); border:1px solid var(--line); }
</style>
</head>
<body>
<header>
  <h1>Help Me Write Better</h1>
  <p>Improve and format text with Claude — preserving meaning and voice.</p>
</header>
<main>
  <section class="panel">
    <label for="text">Your text</label>
    <textarea id="text" placeholder="Paste the text you want to improve…"></textarea>

    <label>Services</label>
    <div id="services" class="chips"></div>

    <div class="row">
      <div>
        <label for="format">Format</label>
        <select id="format"></select>
      </div>
      <div>
        <label for="effort">Effort</label>
        <select id="effort">
          <option>low</option><option>medium</option>
          <option selected>high</option><option>max</option>
        </select>
      </div>
    </div>

    <div class="row">
      <div>
        <label for="tone">Tone (optional)</label>
        <select id="tone">
          <option value="">— none —</option>
          <option>friendly</option><option>professional</option>
          <option>formal</option><option>casual</option>
          <option>confident</option><option>persuasive</option>
          <option>academic</option><option>enthusiastic</option>
          <option>empathetic</option><option>authoritative</option>
          <option>playful</option><option>neutral</option>
          <option>urgent</option>
        </select>
      </div>
      <div>
        <label for="language">Language (optional)</label>
        <select id="language">
          <option value="">— none —</option>
          <option>English</option><option>Spanish</option>
          <option>French</option><option>German</option>
          <option>Italian</option><option>Portuguese</option>
          <option>Dutch</option><option>Polish</option>
          <option>Russian</option><option>Arabic</option>
          <option>Hindi</option><option>Chinese (Simplified)</option>
          <option>Chinese (Traditional)</option><option>Japanese</option>
          <option>Korean</option><option>Vietnamese</option>
          <option>Turkish</option><option>Indonesian</option>
        </select>
      </div>
    </div>

    <label for="request">Instruction (optional)</label>
    <textarea id="request" style="min-height:60px"
      placeholder="Steer the result — e.g. for 'reply', say what you want to convey back…"></textarea>

    <div class="opts">
      <input id="show_changes" type="checkbox">
      <label for="show_changes" style="margin:0;text-transform:none;letter-spacing:0;">
        Include a summary of changes</label>
    </div>

    <div class="actions">
      <button id="sample" class="secondary" type="button">Try a sample</button>
      <button id="go">Polish</button>
    </div>
  </section>

  <section class="panel">
    <div class="bar">
      <div class="meta" id="meta">Result will appear here.</div>
      <button class="copy" id="copy" hidden>Copy</button>
    </div>
    <pre id="out"></pre>
  </section>
</main>

<script>
const $ = (id) => document.getElementById(id);
let SAMPLES = {};
// Controls some samples want set so the demo is meaningful.
const PRESETS = {
  translate: { language: 'Spanish' },
  retone: { tone: 'professional' },
  convert: { format: 'email' },
  reply: { tone: 'professional',
    request: 'Accept the project, agree to deliver by the end of next month, and offer a '
      + '10% discount for paying half upfront. Warm and professional.' },
};

// A `?service=NAME` query param preselects that service (deep-linked from the
// landing page's service chips). Falls back to `clarify` when absent/unknown.
function requestedService() {
  try { return new URLSearchParams(location.search).get('service'); }
  catch (e) { return null; }
}

async function init() {
  try {
    const info = await (await fetch('/', { headers: { Accept: 'application/json' } })).json();
    SAMPLES = info.samples || {};
    const wanted = requestedService();
    const preselect = info.services.includes(wanted) ? wanted : 'clarify';
    $('services').innerHTML = info.services.map(s =>
      `<label class="chip"><input type="checkbox" name="svc" value="${s}"`
      + (s === preselect ? ' checked' : '') + `>${s}</label>`).join('');
    $('format').innerHTML = info.formats.map(f =>
      `<option${f === 'markdown' ? ' selected' : ''}>${f}</option>`).join('');
  } catch (e) {
    $('meta').innerHTML = '<span class="err">Could not load options: ' + e + '</span>';
  }
}

function loadSample() {
  const sel = chosenServices();
  if (!sel.length) { $('meta').innerHTML = '<span class="err">Pick a service first.</span>'; return; }
  const svc = sel[0];
  const text = SAMPLES[svc];
  if (!text) { $('meta').innerHTML = '<span class="err">No sample for ' + svc + '.</span>'; return; }
  $('text').value = text;
  const preset = PRESETS[svc] || {};
  if (preset.language) $('language').value = preset.language;
  if (preset.tone) $('tone').value = preset.tone;
  if (preset.format) $('format').value = preset.format;
  $('request').value = preset.request || '';
  run();
}

function chosenServices() {
  return [...document.querySelectorAll('#services input:checked')].map(i => i.value);
}

async function run() {
  const text = $('text').value.trim();
  if (!text) { $('meta').innerHTML = '<span class="err">Enter some text first.</span>'; return; }
  const services = chosenServices();
  if (!services.length) { $('meta').innerHTML = '<span class="err">Pick at least one service.</span>'; return; }

  const body = {
    text, services,
    format: $('format').value,
    effort: $('effort').value,
    show_changes: $('show_changes').checked,
    tone: $('tone').value.trim() || null,
    language: $('language').value.trim() || null,
    request: $('request').value.trim() || null,
  };

  $('go').disabled = true; $('go').textContent = 'Polishing…';
  $('meta').textContent = ''; $('out').textContent = ''; $('copy').hidden = true;
  try {
    const res = await fetch('/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      $('meta').innerHTML = '<span class="err">' + (data.error || ('HTTP ' + res.status)) + '</span>';
    } else {
      $('out').textContent = data.text;
      $('meta').textContent = `${data.model} · ${data.services.join(', ')}`
        + ` · ${data.usage.output_tokens} output tokens`;
      $('copy').hidden = false;
    }
  } catch (e) {
    $('meta').innerHTML = '<span class="err">Request failed: ' + e + '</span>';
  } finally {
    $('go').disabled = false; $('go').textContent = 'Polish';
  }
}

$('go').addEventListener('click', run);
$('sample').addEventListener('click', loadSample);
$('copy').addEventListener('click', () => navigator.clipboard.writeText($('out').textContent));
init();
</script>
</body>
</html>
"""
