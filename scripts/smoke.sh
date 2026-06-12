#!/usr/bin/env bash
# End-to-end smoke test: boots the platform gateway on a temp SQLite DB, creates
# an account + API key, and curls every feature, printing PASS/FAIL.
#
#   bash scripts/smoke.sh
#
# Keys are optional — the script adapts:
#   ANTHROPIC_API_KEY   -> tests model generation (improve / templates); else SKIP
#   ORIGINALITY_API_KEY -> /v1/scan expects 200; else expects a clean 503
#
# Exits non-zero if any hard check fails.
set -u

PORT="${WB_SMOKE_PORT:-8137}"
BASE="http://127.0.0.1:${PORT}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}"
export WB_DB_PATH="$(mktemp -u)_wb.db"
FAILED=0
BODY=/tmp/wb_smoke_body

cleanup() { [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null; rm -f "$WB_DB_PATH" "$BODY"; }
trap cleanup EXIT

echo "== booting gateway on $BASE (db: $WB_DB_PATH) =="
python -c "from wsgiref.simple_server import make_server; \
from write_better.platform.wsgi import app; \
make_server('127.0.0.1', ${PORT}, app).serve_forever()" >/dev/null 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 40); do
  curl -s -o /dev/null "$BASE/v1" && break
  sleep 0.25
done

echo "== creating account + key =="
python -m write_better.platform.admin create-user --email smoke@x.com --password "supersecret123" --plan business >/dev/null
KEY="$(python -m write_better.platform.admin create-key --email smoke@x.com | tail -1 | tr -d ' ')"
[ -n "$KEY" ] || { echo "FAIL: no API key"; exit 1; }

req() { # method path [body]
  if [ -n "${3:-}" ]; then
    curl -s -o "$BODY" -w "%{http_code}" -X "$1" "$BASE$2" \
      -H "Authorization: Bearer $KEY" -H "content-type: application/json" -d "$3"
  else
    curl -s -o "$BODY" -w "%{http_code}" -X "$1" "$BASE$2" -H "Authorization: Bearer $KEY"
  fi
}
check() { # name method path expected [body]
  local code; code="$(req "$2" "$3" "${5:-}")"
  if [ "$code" = "$4" ]; then printf "  PASS  %-26s (%s)\n" "$1" "$code"
  else printf "  FAIL  %-26s (got %s, want %s)\n" "$1" "$code" "$4"; FAILED=$((FAILED+1)); fi
}

echo "== platform =="
# auth gate (no key)
NOAUTH="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/v1/account")"
[ "$NOAUTH" = "401" ] && printf "  PASS  %-26s (401)\n" "auth required" || { printf "  FAIL  auth required (got %s)\n" "$NOAUTH"; FAILED=$((FAILED+1)); }
check "GET /v1"              GET  /v1                     200
check "GET /v1/openapi.json" GET /v1/openapi.json        200
check "GET /v1/account"     GET  /v1/account             200
check "GET /v1/usage"       GET  /v1/usage               200
check "GET /v1/analytics"   GET  /v1/analytics?window=30 200

echo "== free / local features =="
check "real-time check"     POST /v1/check       200 '{"text":"i dont recieve teh email"}'
check "style fingerprint"   POST /v1/fingerprint 200 '{"text":"She ran. He waited very patiently in the long hall."}'
check "citations (free-text)" POST /v1/cite      200 '{"cite":{"inputs":["Smith, J. (2020). A paper."],"style":"apa"}}'
check "templates list"      GET  /v1/templates?category=marketing 200

echo "== accounts / docs / teams =="
check "save document"       POST /v1/documents   201 '{"title":"N","content":"first draft"}'
check "list documents"      GET  /v1/documents   200
check "set preferences"     PUT  /v1/preferences 200 '{"default_tone":"friendly"}'
check "create team"         POST /v1/team        201 '{"name":"Acme"}'
check "set style guide"     PUT  /v1/team/style-guide 200 '{"banned_terms":["synergy"]}'
check "billing plans"       GET  /billing/plans  200

echo "== external / metered =="
if [ -n "${ORIGINALITY_API_KEY:-}" ]; then
  check "plagiarism scan"   POST /v1/scan 200 '{"text":"a long pasted paragraph here","check":{"modes":["plagiarism"]}}'
else
  check "scan -> feature_unavailable" POST /v1/scan 503 '{"text":"x","check":{"modes":["plagiarism"]}}'
fi

echo "== model generation =="
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  check "improve"           POST /v1/improve 200 '{"text":"their going to the store","services":"correct"}'
  check "template (variants)" POST /v1/improve 200 '{"template":"cold-email-b2b","template_fields":{"product":"Acme","audience":"ops teams","cta":"Book a demo"}}'
else
  echo "  SKIP  improve / templates   (set ANTHROPIC_API_KEY to test generation)"
fi

echo
if [ "$FAILED" -eq 0 ]; then echo "ALL CHECKS PASSED ✅"; else echo "$FAILED CHECK(S) FAILED ❌"; fi
exit "$FAILED"
