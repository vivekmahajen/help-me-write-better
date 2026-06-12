"""The post-signup "Choose your plan" page — rendered from ``plans.py``.

Served by the billing app at ``GET /billing/choose``. New sign-ups land here
(the admin/owner skips it); picking a plan calls ``POST /billing/select`` and
continues to the editor. The cards are generated from :data:`plans.PLANS`, so
pricing here can never drift from the model.

This is the no-payment selection step (the chosen default): selecting a tier
records it on the account. Wiring real Stripe Checkout later only changes what
the buttons POST to — the page itself stays the same.
"""

from __future__ import annotations

from ..plans import PLANS


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _price_line(p) -> str:
    if p.monthly_price == 0:
        return "Free"
    annual = ""
    if p.annual_monthly:
        annual = f"<span class='ann'>or ${p.annual_monthly}/mo billed yearly</span>"
    return f"<span class='amt'>${p.monthly_price}</span><span class='per'>/month</span>{annual}"


def _caps(p) -> str:
    rows = []
    if p.premium_generations:
        rows.append(f"{p.premium_generations:,} premium generations / mo")
    else:
        rows.append("Unlimited routine edits; premium generations not included")
    rows.append(f"{p.seats} seat" + ("s" if p.seats != 1 else ""))
    if p.plagiarism_checks:
        rows.append(f"{p.plagiarism_checks} originality checks / mo")
    if p.ai_images:
        rows.append(f"{p.ai_images} AI images / mo")
    return "".join(f"<li>{_esc(r)}</li>" for r in rows)


def _card(p) -> str:
    name = p.name.lower()
    cta = "Start on Free" if p.monthly_price == 0 else f"Choose {_esc(p.name)}"
    return (
        f'<div class="card" data-plan="{name}">'
        f'<h2>{_esc(p.name)}</h2>'
        f'<div class="price">{_price_line(p)}</div>'
        f'<ul>{_caps(p)}</ul>'
        f'<button class="pick" data-plan="{name}">{cta}</button>'
        f"</div>"
    )


def render_plans_page() -> str:
    cards = "".join(_card(p) for p in PLANS)
    return _TEMPLATE.replace("__CARDS__", cards)


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Choose your plan — Help Me Write Better</title>
<style>
  :root{--ink:#0E2A47;--teal:#0E7C7B;--mint:#1FA37A;--bg:#F6F4EF;--panel:#fff;
    --line:#E2DCD0;--muted:#5A6473}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
  header{border-bottom:1px solid var(--line)}
  header .wrap{max-width:1000px;margin:0 auto;padding:0 24px;height:56px;display:flex;align-items:center}
  .brand{font-weight:700;text-decoration:none;color:var(--ink)}
  main{max-width:1000px;margin:0 auto;padding:40px 24px}
  h1{font-size:28px;margin:0 0 6px;letter-spacing:-.01em}
  .sub{color:var(--muted);margin:0 0 28px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;align-items:stretch}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;
    display:flex;flex-direction:column}
  .card h2{margin:0 0 8px;font-size:20px}
  .price{margin-bottom:14px;min-height:46px}
  .price .amt{font-size:28px;font-weight:700}
  .price .per{color:var(--muted)}
  .price .ann{display:block;color:var(--muted);font-size:13px}
  .card ul{list-style:none;padding:0;margin:0 0 18px;flex:1}
  .card li{padding:5px 0;border-top:1px solid var(--line);font-size:14px;color:var(--ink)}
  .card li:first-child{border-top:0}
  .pick{margin-top:auto;padding:11px;border:0;border-radius:8px;background:var(--ink);color:#fff;
    font-weight:600;font-size:15px;cursor:pointer}
  .pick:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
  .pick:disabled{opacity:.6;cursor:default}
  .msg{margin-top:18px;min-height:20px;font-size:14px}
  .msg.err{color:#B23B3B}
  .note{margin-top:10px;color:var(--muted);font-size:13px}
</style>
</head>
<body>
<header><div class="wrap"><a class="brand" href="/">Help Me Write Better</a></div></header>
<main>
  <h1>Choose your plan</h1>
  <p class="sub">Pick a plan to get started. You can change it later. Free works
    right away — paid tiers raise your monthly limits.</p>
  <div class="grid">__CARDS__</div>
  <div class="msg" id="msg" aria-live="polite"></div>
  <p class="note">Paid plans don't take payment yet — selecting one records it on
    your account.</p>
</main>
<script>
(function(){
  var msg=document.getElementById('msg');
  function track(ev, props){
    try{
      var body=JSON.stringify({event:ev, props:props||{}});
      if(navigator.sendBeacon){ navigator.sendBeacon('/events', new Blob([body],{type:'application/json'})); }
      else { fetch('/events',{method:'POST',headers:{'Content-Type':'application/json'},body:body,keepalive:true}); }
    }catch(e){}
  }
  track('pricing_view',{});
  // Must be signed in to choose a plan.
  fetch('/auth/me').then(function(r){ if(r.status===401) location.href='/auth/login'; });

  document.querySelectorAll('.pick').forEach(function(btn){
    btn.addEventListener('click', async function(){
      var plan=btn.dataset.plan;
      track('plan_selected', {plan: plan});
      document.querySelectorAll('.pick').forEach(function(b){ b.disabled=true; });
      msg.textContent='Setting up your account…'; msg.className='msg';
      try{
        var res=await fetch('/billing/select',{method:'POST',
          headers:{'Content-Type':'application/json'},body:JSON.stringify({plan:plan})});
        var d=await res.json().catch(function(){return {};});
        if(res.status===401){ location.href='/auth/login'; return; }
        if(!res.ok) throw new Error(d.error||('HTTP '+res.status));
        location.href='/app';
      }catch(e){
        msg.textContent=e.message; msg.className='msg err';
        document.querySelectorAll('.pick').forEach(function(b){ b.disabled=false; });
      }
    });
  });
})();
</script>
</body>
</html>
"""
