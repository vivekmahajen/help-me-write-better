# Deploying — and turning on login

The app runs in two shapes from one entrypoint (`app.py`):

| Mode | When | What works |
|------|------|------------|
| **Engine-only** (default) | no database configured | Landing page, editor (`/app`), live demo (`/demo`), JSON API (`GET`/`POST /`) |
| **Full platform** | a Postgres URL is configured | Everything above **plus** accounts + **login** at `/auth/*`, the metered API gateway at `/v1/*`, and billing at `/billing/*` |

`app.py` picks the platform automatically when it sees a Postgres URL in the
environment. **Login needs a database** — serverless filesystems are ephemeral,
so SQLite isn't durable there and sessions wouldn't survive between requests.

---

## Make login work on Vercel

### 1. Add a Postgres database
In the Vercel dashboard: **Storage → Create → Postgres** (Vercel Postgres / Neon),
and connect it to the project. This sets `POSTGRES_URL` (and friends)
automatically — the app already recognises these. Any managed Postgres works too
(Neon, Supabase, Railway, RDS); just set one of:

```
WB_DB_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
# or DATABASE_URL / POSTGRES_URL / POSTGRES_URL_NON_POOLING
```

`psycopg` is already in `requirements.txt`, so the driver is installed in the build.

### 2. Set the remaining environment variables
```
ANTHROPIC_API_KEY=sk-ant-...           # required for the engine + demo
WB_BASE_URL=https://your-app.vercel.app # exact public origin (secure cookies, OAuth, reset links)
WB_ADMIN_EMAILS=vmahajans@yahoo.com     # uncapped owner account(s) (default already includes this)
```
Optional:
```
WB_FEATURE_PLATFORM=1                    # force the platform UI on (auto-on once a DB is set)
WB_SMTP_HOST/PORT/USER/PASSWORD, WB_MAIL_FROM   # real password-reset emails (else links print to logs)
STRIPE_API_KEY, STRIPE_PRICE_*           # real billing (else a keyless local provider)
```

### 3. Redeploy
A new deploy now serves the full platform. The landing header shows **Log in**
(auto-enabled by the database), and `/auth/login` is live.

### 4. Create your account
Either sign up at `/auth/login`, or from a shell with the DB env set:
```
WB_DB_URL=postgres://... write-better-admin create-user \
  --email vmahajans@yahoo.com --password 'a-strong-password'
```
`vmahajans@yahoo.com` starts on the top tier and is **uncapped** (no pricing
limits) — see `WB_ADMIN_EMAILS`.

---

## Verifying

```bash
# JSON API still works (and proves the descriptor is unchanged):
curl -H 'Accept: application/json' https://your-app.vercel.app/

# Auth page is being served (only in platform mode):
curl -sI https://your-app.vercel.app/auth/login | grep -i content-type   # text/html

# Sign in:
curl -i -X POST https://your-app.vercel.app/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"vmahajans@yahoo.com","password":"..."}'                   # 200 + Set-Cookie
```

If `/auth/login` returns the **landing page** instead of the sign-in form, the app
is still in engine-only mode — the database URL isn't being detected. Check the
env var is set on the right environment (Production) and redeploy. If a DB *is*
configured but the platform fails to start, `app.py` falls back to engine-only
and logs the reason (look for `[app] database configured but platform failed`).

> **Note on serverless + a stateful gateway.** Vercel functions are short-lived
> and cold-start often; with Postgres this works, but for heavy authenticated/
> gateway traffic a small always-on host (Railway, Fly.io, Render) pointed at the
> same `app.py` is a better fit. The code is identical — only the host changes.
