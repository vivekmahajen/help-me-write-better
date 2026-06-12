"""The marketing landing page — a single self-contained HTML page (no external assets).

Served on ``GET /`` when the client accepts HTML. The demo editor moved to
``/app`` (see ``ui.py``); this page is what a browser visitor sees first and
links them into the editor and the JSON API.

Honesty rules (enforced here and expanded in later slices):
  * No fabricated social proof — no invented testimonials, counts, logos, or
    ratings. Proof is real and checkable (automated tests, composable services,
    an open JSON API, model-routing transparency, a live editor).
  * ``<!-- PROOF SLOT -->`` markers reserve spots for verifiable evidence.

This slice (PR-1) is a lean but truthful page; the live hero demo, the
``FEATURES_LIVE`` honesty gate, and the full section set land in PR-2.
"""

# Real, checkable proof points (keep in sync with the codebase; no invention).
TEST_COUNT = 188
SERVICE_COUNT = 36

# <!-- Headline candidates:
#   A) "Better writing, on tap — and an API behind it"
#   B) "Polish your words. Keep your voice." -->
LANDING = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Help Me Write Better — clear writing, with an API behind it</title>
<meta name="description" content="Improve and format text with Claude while keeping your meaning and voice. A live editor, an open JSON API, and {services} composable services.">
<style>
  :root {{
    --ink:#0E2A47; --teal:#0E7C7B; --mint:#1FA37A;
    --bg:#F6F4EF; --panel:#FFFFFF; --line:#E2DCD0; --muted:#5A6473;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
  a {{ color:var(--teal); }}
  .wrap {{ max-width:960px; margin:0 auto; padding:0 24px; }}
  header.site {{ position:sticky; top:0; z-index:10; background:rgba(246,244,239,.92);
    backdrop-filter:saturate(150%) blur(6px); border-bottom:1px solid var(--line); }}
  header.site .wrap {{ display:flex; align-items:center; gap:16px; height:56px; }}
  .brand {{ font-weight:700; letter-spacing:-.01em; }}
  header.site nav {{ margin-left:auto; display:flex; gap:18px; align-items:center; font-size:14px; }}
  .btn {{ display:inline-block; padding:10px 16px; border-radius:8px; font-weight:600;
    text-decoration:none; border:1px solid transparent; }}
  .btn.primary {{ background:var(--ink); color:#fff; }}
  .btn.ghost {{ border-color:var(--line); color:var(--ink); background:var(--panel); }}
  .btn:focus-visible, a:focus-visible {{ outline:3px solid var(--teal); outline-offset:2px; }}
  main {{ display:block; }}
  .hero {{ padding:72px 0 56px; }}
  .hero h1 {{ font-size:clamp(30px,5vw,46px); line-height:1.1; margin:0 0 16px;
    letter-spacing:-.02em; max-width:18ch; }}
  .hero p.lead {{ font-size:19px; color:var(--muted); max-width:60ch; margin:0 0 28px; }}
  .cta {{ display:flex; gap:12px; flex-wrap:wrap; }}
  .proof {{ border-top:1px solid var(--line); border-bottom:1px solid var(--line);
    padding:20px 0; }}
  .proof ul {{ list-style:none; display:flex; flex-wrap:wrap; gap:28px;
    margin:0; padding:0; color:var(--muted); font-size:15px; }}
  .proof b {{ color:var(--ink); }}
  section.block {{ padding:48px 0; }}
  section.block h2 {{ font-size:24px; margin:0 0 12px; letter-spacing:-.01em; }}
  footer.site {{ border-top:1px solid var(--line); padding:32px 0; color:var(--muted);
    font-size:14px; }}
  footer.site a {{ color:var(--muted); }}
  @media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior:auto !important; }} }}
</style>
</head>
<body>
<header class="site">
  <div class="wrap">
    <span class="brand">Help Me Write Better</span>
    <nav>
      <a href="#how">How it works</a>
      <a href="#build">For developers</a>
      <a class="btn ghost" href="/app">Open the editor</a>
    </nav>
  </div>
</header>

<main>
  <section class="hero">
    <div class="wrap">
      <!-- Hero headline candidates:
           A) "Clear writing, with an API behind it"
           B) "Fix the writing. Keep the voice." -->
      <h1>Clear writing, with an API behind it</h1>
      <p class="lead">Improve and format text with Claude while keeping your
        meaning and your voice. Try it in the editor, or call the same engine
        from your own code.</p>
      <div class="cta">
        <a class="btn primary" href="/app" data-cta="open_editor">Open the editor</a>
        <a class="btn ghost" href="#build" data-cta="see_api">See the API</a>
      </div>
    </div>
  </section>

  <section class="proof" aria-label="What's actually built">
    <div class="wrap">
      <!-- PROOF SLOT: only verifiable evidence belongs here. -->
      <ul>
        <li><b>{tests} automated tests</b> across the engine and platform</li>
        <li><b>{services} composable services</b> you can chain in one call</li>
        <li><b>Open JSON API</b> — the editor and your code hit the same endpoint</li>
        <li><b>Model routing</b> picks the right Claude tier per request</li>
      </ul>
    </div>
  </section>

  <section class="block" id="how">
    <div class="wrap">
      <h2>How it works</h2>
      <p>Paste text, choose what you want done — correct, tighten, clarify,
        retone, translate, and more — and the engine returns polished text that
        still sounds like you. Optionally ask for a summary of every change.</p>
      <p><a href="/app">Open the editor</a> to try it.</p>
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
    <!-- Legal stubs (Privacy, Terms) land in PR-3 and need legal review before launch. -->
  </div>
</footer>
</body>
</html>
""".format(tests=TEST_COUNT, services=SERVICE_COUNT)
