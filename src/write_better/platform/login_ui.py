"""The browser auth page — sign in / create account / forgot + reset password.

One self-contained HTML page (no external assets), served by the webauth app:

    GET /auth/login            -> sign in / create account / forgot tabs
    GET /auth/reset?token=...  -> set-a-new-password form (from the email link)

Its JavaScript calls the JSON endpoints on the same origin (``/auth/login``,
``/auth/signup``, ``/auth/forgot``, ``/auth/reset``) and, on success, sends the
user to the editor (``/app``). The page only exists where the platform (and a
database) are mounted, so it's never a dead link on the engine-only demo.
"""

AUTH_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in — Help Me Write Better</title>
<style>
  :root{--ink:#0E2A47;--teal:#0E7C7B;--mint:#1FA37A;--bg:#F6F4EF;--panel:#fff;
    --line:#E2DCD0;--muted:#5A6473;--err:#B23B3B;--ok:#0B6B47}
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;background:var(--bg);color:var(--ink);
    font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    display:flex;flex-direction:column}
  header{border-bottom:1px solid var(--line);background:rgba(246,244,239,.92)}
  header .wrap{max-width:960px;margin:0 auto;padding:0 24px;height:56px;display:flex;align-items:center}
  .brand{font-weight:700;text-decoration:none;color:var(--ink)}
  main{flex:1;display:flex;align-items:flex-start;justify-content:center;padding:48px 24px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
    padding:24px;width:100%;max-width:400px;box-shadow:0 1px 0 rgba(14,42,71,.04)}
  h1{font-size:22px;margin:0 0 4px;letter-spacing:-.01em}
  .sub{color:var(--muted);margin:0 0 18px;font-size:14px}
  .tabs{display:flex;gap:6px;margin-bottom:18px;border-bottom:1px solid var(--line)}
  .tabs button{flex:1;background:none;border:0;border-bottom:2px solid transparent;
    padding:9px 4px;cursor:pointer;color:var(--muted);font:inherit;font-size:14px}
  .tabs button.on{color:var(--ink);border-bottom-color:var(--teal);font-weight:600}
  label{display:block;font-size:13px;color:var(--muted);margin:12px 0 5px}
  input{width:100%;border:1px solid var(--line);border-radius:8px;padding:10px;font:inherit;
    background:#fff;color:var(--ink)}
  input:focus-visible{outline:3px solid var(--teal);outline-offset:1px}
  button.submit{width:100%;margin-top:18px;padding:11px;border:0;border-radius:8px;
    background:var(--ink);color:#fff;font-weight:600;font-size:15px;cursor:pointer}
  button.submit:disabled{opacity:.6;cursor:default}
  .msg{margin-top:14px;font-size:14px;min-height:18px}
  .msg.err{color:var(--err)}
  .msg.ok{color:var(--ok)}
  .alt{margin-top:14px;font-size:13px;color:var(--muted);text-align:center}
  .alt a{color:var(--teal);cursor:pointer;text-decoration:underline}
  form{display:none}form.on{display:block}
</style>
</head>
<body>
<header><div class="wrap"><a class="brand" href="/">Help Me Write Better</a></div></header>
<main>
  <div class="card">
    <h1 id="title">Sign in</h1>
    <p class="sub" id="sub">Access your account and the editor.</p>

    <div class="tabs" id="tabs">
      <button data-view="signin" class="on">Sign in</button>
      <button data-view="signup">Create account</button>
      <button data-view="forgot">Forgot?</button>
    </div>

    <form id="signin" class="on" autocomplete="on">
      <label for="si_email">Email</label>
      <input id="si_email" type="email" autocomplete="username" required>
      <label for="si_pw">Password</label>
      <input id="si_pw" type="password" autocomplete="current-password" required>
      <button class="submit" type="submit">Sign in</button>
    </form>

    <form id="signup">
      <label for="su_email">Email</label>
      <input id="su_email" type="email" autocomplete="username" required>
      <label for="su_pw">Password <span style="text-transform:none">(8+ characters)</span></label>
      <input id="su_pw" type="password" autocomplete="new-password" required minlength="8">
      <button class="submit" type="submit">Create account</button>
    </form>

    <form id="forgot">
      <label for="fo_email">Email</label>
      <input id="fo_email" type="email" autocomplete="username" required>
      <button class="submit" type="submit">Email me a reset link</button>
    </form>

    <form id="reset">
      <label for="re_pw">New password <span style="text-transform:none">(8+ characters)</span></label>
      <input id="re_pw" type="password" autocomplete="new-password" required minlength="8">
      <button class="submit" type="submit">Set new password</button>
    </form>

    <div class="msg" id="msg" aria-live="polite"></div>
    <div class="alt" id="alt"></div>
  </div>
</main>
<script>
(function(){
  var $=function(id){return document.getElementById(id);};
  var token=new URLSearchParams(location.search).get('token');
  var msg=$('msg');
  function setMsg(t,kind){ msg.textContent=t||''; msg.className='msg'+(kind?(' '+kind):''); }

  function view(name){
    ['signin','signup','forgot','reset'].forEach(function(v){
      $(v).classList.toggle('on', v===name);
    });
    document.querySelectorAll('#tabs button').forEach(function(b){
      b.classList.toggle('on', b.dataset.view===name);
    });
    setMsg('');
    var titles={signin:['Sign in','Access your account and the editor.'],
      signup:['Create account','Start improving your writing.'],
      forgot:['Reset password',"We'll email you a link to set a new one."],
      reset:['Set a new password','Choose a new password for your account.']};
    $('title').textContent=titles[name][0]; $('sub').textContent=titles[name][1];
    $('tabs').style.display = name==='reset' ? 'none' : 'flex';
  }

  document.querySelectorAll('#tabs button').forEach(function(b){
    b.addEventListener('click', function(){ view(b.dataset.view); });
  });

  async function post(path, body){
    var res, data;
    try { res=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)}); }
    catch(e){ throw new Error('Accounts are not enabled on this deployment yet.'); }
    try { data=await res.json(); } catch(e){ data={}; }
    if(res.status===404) throw new Error('Accounts are not enabled on this deployment yet.');
    if(!res.ok) throw new Error(data.error || ('HTTP '+res.status));
    return data;
  }
  function submit(form, fn){
    $(form).addEventListener('submit', async function(e){
      e.preventDefault();
      var btn=$(form).querySelector('button'); btn.disabled=true; var lbl=btn.textContent;
      setMsg('Working…');
      try { await fn(); } catch(err){ setMsg(err.message, 'err'); }
      finally { btn.disabled=false; btn.textContent=lbl; }
    });
  }

  submit('signin', async function(){
    await post('/auth/login',{email:$('si_email').value.trim(),password:$('si_pw').value});
    location.href='/app';
  });
  submit('signup', async function(){
    var d=await post('/auth/signup',{email:$('su_email').value.trim(),password:$('su_pw').value});
    // New users choose a plan first; the admin/owner skips straight to the editor.
    location.href=(d && d.user && d.user.admin) ? '/app' : '/billing/choose';
  });
  submit('forgot', async function(){
    var r=await post('/auth/forgot',{email:$('fo_email').value.trim()});
    setMsg(r.message || 'If that email is registered, a reset link is on its way.', 'ok');
  });
  submit('reset', async function(){
    await post('/auth/reset',{token:token,password:$('re_pw').value});
    setMsg('Password updated. Taking you to the editor…', 'ok');
    setTimeout(function(){ location.href='/app'; }, 800);
  });

  view(token ? 'reset' : 'signin');
})();
</script>
</body>
</html>
"""
