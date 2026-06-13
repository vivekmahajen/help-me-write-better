"""The marketing landing page — one self-contained HTML page (no external assets).

Served on ``GET /`` when the client accepts HTML. The demo editor lives at
``/app`` (see ``ui.py``); this page introduces the product, runs a *real* hero
demo against the engine, and links visitors into the editor and the JSON API.

Honesty rules enforced here:
  * Every gated surface renders from :data:`features.FEATURES_LIVE`. With all
    flags off the page makes **zero** "available" claims and contains **zero**
    dead links — unbuilt surfaces say "coming soon". Flipping a flag lights the
    section up with no copy rewrites.
  * No fabricated social proof — no invented testimonials, counts, logos, or
    ratings. Proof is real and checkable (automated tests, composable services,
    an open JSON API, model routing, a live demo). ``<!-- PROOF SLOT -->``
    markers reserve room for further verifiable evidence.

Pricing (from ``plans.py``), the FAQ, legal footer, and the SEO/analytics layer
arrive in later slices (PR-3, PR-4).
"""

from __future__ import annotations

from . import seo
from .demo import DEMO_INPUT
from .features import FEATURES_LIVE, surface_states

# Real, checkable proof points (keep in sync with the codebase; never invented).
TEST_COUNT = 188
SERVICE_COUNT = 45

# "How it works" deep-link chips — every name is a real service (see modes.py).
_CHIP_SERVICES = ("correct", "clarify", "tighten", "retone", "paraphrase", "translate")


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _chips_html() -> str:
    return "".join(
        f'<a class="chip" href="/app?service={s}" data-cta="chip_{s}">{s}</a>'
        for s in _CHIP_SERVICES
    )


def _work_html(flags: dict) -> str:
    # The "Work" card is gated on the platform being live at this deployment.
    if flags.get("platform"):
        return (
            '<a class="card" href="/app">'
            "<h3>Work together</h3>"
            "<p>Shared accounts, a team style guide the engine follows, and "
            "usage you can see. Open your workspace.</p></a>"
        )
    return (
        '<div class="card soft">'
        "<h3>Work together</h3>"
        "<p>Shared accounts, a team style guide, and per-seat usage. "
        '<span class="soon">Coming soon.</span></p></div>'
    )


def _trust_html(flags: dict) -> str:
    # The Trust Layer section only appears as live when the gateway exposes it.
    if not flags.get("trust_layer"):
        return (
            '<section class="block" id="trust" aria-label="Trust layer">'
            '<div class="wrap"><h2>Check before you ship</h2>'
            "<p>Originality and AI-likelihood checks (always a confidence band, "
            "never a verdict) and citation formatting. "
            '<span class="soon">Coming soon.</span></p></div></section>'
        )
    return (
        '<section class="block" id="trust" aria-label="Trust layer">'
        '<div class="wrap"><h2>Check before you ship</h2>'
        "<p>Originality and AI-likelihood checks — reported as a confidence band "
        "with the limits stated, never a binary verdict — plus citation "
        'formatting in APA, MLA, Chicago, Harvard, and IEEE. '
        '<a href="/app">Open the tools.</a></p></div></section>'
    )


def _surfaces_html(flags: dict) -> str:
    cells = []
    for s in surface_states(flags):
        if s["live"]:
            cells.append(
                f'<a class="surface" href="{_esc(s["url"])}" data-cta="surface_{s["key"]}">'
                f'<b>{_esc(s["name"])}</b><span>{_esc(s["blurb"])}</span>'
                '<span class="tag live">Available</span></a>'
            )
        else:
            cells.append(
                f'<div class="surface soft">'
                f'<b>{_esc(s["name"])}</b><span>{_esc(s["blurb"])}</span>'
                '<span class="tag">Coming soon</span></div>'
            )
    return "".join(cells)


def render(flags: dict | None = None) -> str:
    """Render the landing page for a given feature-flag state."""
    f = FEATURES_LIVE if flags is None else flags
    html = _TEMPLATE
    html = html.replace("__SEO_HEAD__", seo.head())
    html = html.replace("__TESTS__", str(TEST_COUNT))
    html = html.replace("__SERVICES__", str(SERVICE_COUNT))
    html = html.replace("__DEMO_INPUT__", _esc(DEMO_INPUT))
    html = html.replace("__CHIPS__", _chips_html())
    html = html.replace("__WORK__", _work_html(f))
    html = html.replace("__TRUST__", _trust_html(f))
    html = html.replace("__SURFACES__", _surfaces_html(f))
    # "Log in" only when the platform (accounts) is actually mounted here, so it's
    # never a dead link on the engine-only demo.
    nav_auth = '\n      <a href="/auth/login" data-cta="login">Log in</a>' if f.get("platform") else ""
    html = html.replace("__NAV_AUTH__", nav_auth)
    return html


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__SEO_HEAD__
<style>
  :root{
    --ink:#0E2A47; --teal:#0E7C7B; --mint:#1FA37A;
    --bg:#F6F4EF; --panel:#FFFFFF; --line:#E2DCD0; --muted:#5A6473;
    --ins:#E3F4EC; --insink:#0B6B47;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
  a{color:var(--teal)}
  code,pre,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  .wrap{max-width:980px;margin:0 auto;padding:0 24px}
  header.site{position:sticky;top:0;z-index:10;background:rgba(246,244,239,.92);
    backdrop-filter:saturate(150%) blur(6px);border-bottom:1px solid var(--line)}
  header.site .wrap{display:flex;align-items:center;gap:16px;height:56px}
  .brand{font-weight:700;letter-spacing:-.01em}
  header.site nav{margin-left:auto;display:flex;gap:18px;align-items:center;font-size:14px}
  @media (max-width:640px){header.site nav a:not(.btn){display:none}}
  .btn{display:inline-block;padding:10px 16px;border-radius:8px;font-weight:600;
    text-decoration:none;border:1px solid transparent;cursor:pointer;font-size:15px}
  .btn.primary{background:var(--ink);color:#fff}
  .btn.ghost{border-color:var(--line);color:var(--ink);background:var(--panel)}
  .btn:focus-visible,a:focus-visible,textarea:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
  main{display:block}
  .hero{padding:64px 0 40px}
  .hero-grid{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:start}
  @media (max-width:820px){.hero-grid{grid-template-columns:1fr;gap:24px}}
  .hero h1{font-size:clamp(30px,5vw,44px);line-height:1.1;margin:0 0 14px;
    letter-spacing:-.02em}
  .hero p.lead{font-size:19px;color:var(--muted);margin:0 0 24px}
  .cta{display:flex;gap:12px;flex-wrap:wrap}
  .demo{background:var(--panel);border:1px solid var(--line);border-radius:14px;
    padding:16px;box-shadow:0 1px 0 rgba(14,42,71,.04)}
  .demo h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;
    color:var(--muted);margin:0 0 10px}
  .demo textarea{width:100%;min-height:96px;resize:vertical;border:1px solid var(--line);
    border-radius:10px;padding:11px;font:inherit;background:#fff;color:var(--ink)}
  .demo .row{display:flex;gap:10px;align-items:center;margin-top:10px}
  .demo .status{color:var(--muted);font-size:13px;min-height:18px;flex:1}
  .demo .out{margin-top:12px;border-top:1px dashed var(--line);padding-top:12px;display:none}
  .demo .out.show{display:block}
  .demo .label{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
  .demo .result{font-size:16px;margin:6px 0 0}
  .demo mark{background:var(--ins);color:var(--insink);border-radius:4px;padding:0 2px}
  .demo .sample-note{background:#FBF3DD;border:1px solid #ECD9A0;color:#6b551b;
    border-radius:8px;padding:8px 10px;font-size:13px;margin-bottom:8px}
  .anim mark{animation:hl .5s ease-out both}
  @keyframes hl{from{background:transparent}to{background:var(--ins)}}
  .proof{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:18px 0}
  .proof ul{list-style:none;display:flex;flex-wrap:wrap;gap:26px;margin:0;padding:0;
    color:var(--muted);font-size:15px}
  .proof b{color:var(--ink)}
  section.block{padding:46px 0}
  section.block h2{font-size:26px;margin:0 0 8px;letter-spacing:-.01em}
  section.block>.wrap>p.sub{color:var(--muted);margin:0 0 22px;max-width:60ch}
  .steps{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
  @media (max-width:720px){.steps{grid-template-columns:1fr}}
  .step{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
  .step b{display:block;margin-bottom:4px}
  .chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
  .chip{display:inline-block;padding:6px 12px;border-radius:999px;background:var(--panel);
    border:1px solid var(--line);font-size:14px;text-decoration:none;color:var(--ink)}
  .trio{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
  @media (max-width:720px){.trio{grid-template-columns:1fr}}
  .card{display:block;background:var(--panel);border:1px solid var(--line);border-radius:12px;
    padding:18px;text-decoration:none;color:inherit}
  .card h3{margin:0 0 6px;font-size:18px}
  .card p{margin:0;color:var(--muted)}
  .card.soft{opacity:.85}
  .soon{color:var(--teal);font-weight:600}
  .card pre{background:#0E2A47;color:#E8EEF5;border-radius:8px;padding:10px;font-size:13px;
    overflow:auto;margin:8px 0 0}
  .surfaces{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px}
  .surface{display:flex;flex-direction:column;gap:4px;background:var(--panel);
    border:1px solid var(--line);border-radius:12px;padding:14px;text-decoration:none;color:inherit}
  .surface b{font-size:15px}.surface span{color:var(--muted);font-size:13px}
  .surface.soft{opacity:.8}
  .tag{align-self:flex-start;margin-top:6px;font-size:12px;padding:2px 8px;border-radius:999px;
    background:#EEE9DD;color:var(--muted)}
  .tag.live{background:var(--ins);color:var(--insink)}
  footer.site{border-top:1px solid var(--line);padding:30px 0;color:var(--muted);font-size:14px}
  footer.site a{color:var(--muted)}
  @media (prefers-reduced-motion: reduce){
    *{scroll-behavior:auto !important}
    .anim mark{animation:none}
  }
</style>
</head>
<body>
<header class="site">
  <div class="wrap">
    <span class="brand">Help Me Write Better</span>
    <nav>
      <a href="#how">How it works</a>
      <a href="#build">For developers</a>__NAV_AUTH__
      <a class="btn ghost" href="/app">Open the editor</a>
    </nav>
  </div>
</header>

<main>
  <section class="hero">
    <div class="wrap hero-grid">
      <div>
        <!-- Hero headline candidates:
             A) "Clear writing, with an API behind it"
             B) "Fix the writing. Keep the voice." -->
        <h1>Clear writing, with an API behind it</h1>
        <p class="lead">Improve and format text with Claude while keeping your
          meaning and your voice. Try it right here, or call the same engine
          from your own code.</p>
        <div class="cta">
          <a class="btn primary" href="/app" data-cta="open_editor">Open the editor</a>
          <a class="btn ghost" href="#build" data-cta="see_api">See the API</a>
        </div>
      </div>

      <div class="demo" id="demo">
        <h2>Try it — fix this sentence</h2>
        <textarea id="demoText" aria-label="Text to fix">__DEMO_INPUT__</textarea>
        <div class="row">
          <span class="status" id="demoStatus">Runs correct + tighten on the real engine.</span>
          <button class="btn primary" id="demoBtn" data-cta="demo_run">Fix it</button>
        </div>
        <div class="out" id="demoOut" aria-live="polite">
          <div class="sample-note" id="demoSample" hidden></div>
          <div class="label">Result</div>
          <p class="result" id="demoResult"></p>
        </div>
      </div>
    </div>
  </section>

  <section class="proof" aria-label="What's actually built">
    <div class="wrap">
      <!-- PROOF SLOT: only verifiable evidence belongs here. -->
      <ul>
        <li><b>__TESTS__ automated tests</b> across the engine and platform</li>
        <li><b>__SERVICES__ composable services</b> you can chain in one call</li>
        <li><b>Open JSON API</b> — the editor and your code hit one endpoint</li>
        <li><b>Model routing</b> picks the right Claude tier per request</li>
      </ul>
    </div>
  </section>

  <section class="block" id="how">
    <div class="wrap">
      <!-- Section headline candidates:
           A) "How it works" B) "Three steps, your words" -->
      <h2>How it works</h2>
      <p class="sub">Paste text, pick what you want done, get it back sounding
        like you — optionally with a summary of every change.</p>
      <div class="steps">
        <div class="step"><b>1. Paste</b>Drop in a sentence, a paragraph, or a draft.</div>
        <div class="step"><b>2. Choose</b>Correct, tighten, clarify, retone, translate — chain as many as you need.</div>
        <div class="step"><b>3. Keep your voice</b>Polished text that preserves your meaning, not a rewrite into someone else's.</div>
      </div>
      <div class="chips" aria-label="Jump into a service">__CHIPS__</div>
    </div>
  </section>

  <section class="block" id="features">
    <div class="wrap">
      <h2>Three ways in</h2>
      <div class="trio">
        <a class="card" href="/app">
          <h3>Write</h3>
          <p>The editor: every service, tone and language options, and a diff of
            what changed. Open it.</p>
        </a>
        __WORK__
        <div class="card">
          <h3>Build</h3>
          <p>Call the engine from anywhere:</p>
          <pre class="mono">curl -X POST https://your-host/ \\
  -H 'Content-Type: application/json' \\
  -d '{"text":"...","services":["tighten"]}'</pre>
          <p style="margin-top:8px">There's a JS/TS SDK and a CLI too.</p>
        </div>
      </div>
    </div>
  </section>

  __TRUST__

  <section class="block" id="everywhere">
    <div class="wrap">
      <h2>Where you'll write</h2>
      <p class="sub">We link a surface only when it's actually live here. The
        rest say "coming soon" — no dead links.</p>
      <div class="surfaces">__SURFACES__</div>
    </div>
  </section>

  <section class="block" id="build">
    <div class="wrap">
      <h2>For developers</h2>
      <p>The browser editor and your code call the same <code>POST /</code>
        endpoint. Ask <code>GET /</code> with
        <code>Accept: application/json</code> for the full request shape and the
        list of services.</p>
    </div>
  </section>
</main>

<footer class="site">
  <div class="wrap">
    <p>Help Me Write Better. <a href="/app">Editor</a> ·
       <a href="/" data-cta="api_descriptor">API</a></p>
    <!-- Pricing, FAQ, and legal (Privacy/Terms) land in PR-3 and need legal review. -->
  </div>
</footer>

<script>
(function(){
  // First-party analytics — best-effort, no third-party trackers.
  function track(ev, props){
    try{
      var body=JSON.stringify({event:ev, props:props||{}});
      if(navigator.sendBeacon){ navigator.sendBeacon('/events', new Blob([body],{type:'application/json'})); }
      else { fetch('/events',{method:'POST',headers:{'Content-Type':'application/json'},body:body,keepalive:true}); }
    }catch(e){}
  }
  window.__track=track;
  track('landing_view',{});
  document.querySelectorAll('[data-cta]').forEach(function(el){
    el.addEventListener('click', function(){ track('cta_click', {target: el.getAttribute('data-cta')||''}); });
  });
})();
(function(){
  var $=function(id){return document.getElementById(id);};
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var esc=function(s){return String(s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});};

  // Word-level diff: highlight tokens in the result that aren't in the input.
  function highlight(before, after){
    var src=new Set(before.toLowerCase().match(/[a-z0-9']+/g) || []);
    return after.split(/(\\s+)/).map(function(tok){
      var w=tok.toLowerCase().replace(/[^a-z0-9']/g,'');
      if(w && !src.has(w)) return '<mark>'+esc(tok)+'</mark>';
      return esc(tok);
    }).join('');
  }

  function show(input, text, isSample, note){
    var out=$('demoOut'), res=$('demoResult'), s=$('demoSample');
    if(isSample){ s.hidden=false; s.textContent=note || 'Sample result — an example, not a live model call.'; }
    else { s.hidden=true; }
    res.innerHTML=highlight(input, text);
    out.classList.add('show');
    if(!reduce){ out.classList.remove('anim'); void out.offsetWidth; out.classList.add('anim'); }
  }

  var REASONS={rate_limited:"You've hit the demo limit — here's a sample result.",
    no_key:"This demo isn't connected to a key right now — here's a sample result.",
    error:"The live call didn't go through — here's a sample result.",
    empty:"Add some text to fix."};

  $('demoBtn').addEventListener('click', function(){
    var text=$('demoText').value.trim();
    if(!text){ $('demoStatus').textContent='Add some text to fix.'; return; }
    var btn=$('demoBtn'); btn.disabled=true; var label=btn.textContent; btn.textContent='Fixing…';
    $('demoStatus').textContent='Working…';
    fetch('/demo',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:text})})
      .then(function(r){return r.json();})
      .then(function(d){
        show(d.input || text, d.text, d.fallback, REASONS[d.reason]);
        $('demoStatus').textContent = d.fallback
          ? 'Sample result.' : (d.model+' · '+(d.services||[]).join(' + '));
        if(window.__track) window.__track(d.fallback?'demo_fallback':'demo_run',{});
      })
      .catch(function(){
        show(text, text, true, 'Could not reach the demo — showing your text unchanged.');
        $('demoStatus').textContent='Offline.';
      })
      .finally(function(){ btn.disabled=false; btn.textContent=label; });
  });
})();
</script>
</body>
</html>
"""

# Back-compat: a default-flags render for callers importing a constant.
LANDING = render()
