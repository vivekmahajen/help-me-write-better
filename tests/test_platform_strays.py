"""Platform strays (PR-6): snippets, goals, weekly email + cron, version restore."""

import io
import json
import os

import pytest

from write_better import plans
from write_better.platform import accounts, goals as goals_mod, weekly
from write_better.platform.gateway import make_gateway
from write_better.platform.mailer import ConsoleMailer
from write_better.platform.store import Store


# --- store: snippets, version restore/prune, recipients ----------------------

def test_store_snippets_crud():
    s = Store(":memory:")
    u = accounts.create_user(s, "a@b.com", "supersecret")["id"]
    assert s.list_snippets(u) == []
    s.upsert_snippet(u, "/sig", "Best, Alex")
    s.upsert_snippet(u, "/sig", "Cheers, Alex")        # upsert overwrites
    s.upsert_snippet(u, "/addr", "12 Birch Lane")
    snips = {x["trigger"]: x["body"] for x in s.list_snippets(u)}
    assert snips == {"/sig": "Cheers, Alex", "/addr": "12 Birch Lane"}
    assert s.remove_snippet(u, "/sig") is True
    assert s.remove_snippet(u, "/sig") is False
    s.close()


def test_store_version_restore_and_prune():
    s = Store(":memory:")
    u = accounts.create_user(s, "a@b.com", "supersecret")["id"]
    doc = s.create_document(u, "Doc", "v1")
    for n in range(2, 8):
        s.add_document_version(u, doc["id"], f"v{n}")
    versions = s.list_document_versions(u, doc["id"])
    oldest = versions[-1]                              # the v1 snapshot
    restored = s.restore_document_version(u, doc["id"], oldest["id"])
    assert restored is not None
    assert s.list_document_versions(u, doc["id"])[0]["content"] == oldest["content"]
    deleted = s.prune_document_versions(doc["id"], keep=3)
    assert deleted >= 1 and len(s.list_document_versions(u, doc["id"])) == 3
    s.close()


def test_version_caps_and_recipients():
    assert plans.version_cap("free") == 5 and plans.version_cap("business") == 200
    assert plans.version_cap("nonsense") == 5
    s = Store(":memory:")
    u = accounts.create_user(s, "a@b.com", "supersecret")["id"]
    s.set_preferences(u, {"weekly_email": True})
    accounts.create_user(s, "c@d.com", "supersecret")  # no opt-in
    recipients = s.weekly_email_recipients()
    assert [r["email"] for r in recipients] == ["a@b.com"]
    s.close()


# --- goals + weekly helpers (pure) -------------------------------------------

def test_goals_normalize_and_trend():
    assert goals_mod.normalize(["grammar", "grammar", "bogus", "style"]) == ["grammar", "style"]
    s = Store(":memory:")
    u = accounts.create_user(s, "a@b.com", "supersecret")["id"]
    tr = goals_mod.trend(s, u, ["grammar"], weeks=3)
    assert tr["weeks"] == 3 and len(tr["series"]["grammar"]) == 3
    s.close()


def test_weekly_token_and_compose():
    assert weekly.verify_unsubscribe(7, weekly.unsubscribe_token(7))
    assert not weekly.verify_unsubscribe(7, "wrong")
    email = weekly.compose({"id": 7, "email": "a@b.com"},
                           {"this_week": {"calls": 4, "words": 900,
                                          "by_issue_type": {"passive_voice": 6, "style": 2}},
                            "deltas": {"suggestions": -3}},
                           base_url="https://x.test")
    assert email.subject == "Your weekly writing recap"
    assert "passive voice: 6" in email.body
    assert "/v1/unsubscribe?u=7&token=" in email.body     # one-click unsubscribe


# --- gateway endpoints -------------------------------------------------------

def _gw():
    store = Store(":memory:")
    mailer = ConsoleMailer()
    gw = make_gateway(store, mailer=mailer, base_url="https://x.test")
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="free")
    token, _ = accounts.create_api_key(store, user["id"])
    return store, gw, user, token, mailer


def _call(gw, method, path, token=None, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path.split("?")[0],
               "QUERY_STRING": path.split("?")[1] if "?" in path else ""}
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = gw(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    blob = b"".join(out)
    ctype = cap["headers"].get("Content-Type", "")
    return cap["status"], (json.loads(blob) if "json" in ctype else blob.decode())


def test_gateway_snippets_crud_and_validation():
    store, gw, user, token, _ = _gw()
    assert _call(gw, "GET", "/v1/snippets", token)[1] == {"snippets": []}
    status, body = _call(gw, "POST", "/v1/snippets", token, {"trigger": "/sig", "body": "Best, A"})
    assert status.startswith("201") and body["snippets"][0]["trigger"] == "/sig"
    assert _call(gw, "POST", "/v1/snippets", token,
                 {"trigger": "has space", "body": "x"})[0].startswith("400")
    assert _call(gw, "POST", "/v1/snippets", token,
                 {"trigger": "x" * 40, "body": "x"})[0].startswith("400")
    assert _call(gw, "DELETE", "/v1/snippets", token, {"trigger": "/sig"})[0].startswith("200")


def test_gateway_goals_get_put():
    store, gw, user, token, _ = _gw()
    status, body = _call(gw, "PUT", "/v1/goals", token, {"goals": ["passive_voice", "nope"]})
    assert status.startswith("200") and body["goals"] == ["passive_voice"]
    status, body = _call(gw, "GET", "/v1/goals", token)
    assert body["goals"] == ["passive_voice"] and "passive_voice" in body["categories"]
    assert "series" in body["trend"]


def test_gateway_version_restore_and_cap(monkeypatch):
    store, gw, user, token, _ = _gw()           # plan=free -> cap 5
    doc = store.create_document(user["id"], "Doc", "v1")
    for n in range(2, 9):                        # add 7 versions (total 8)
        _call(gw, "POST", f"/v1/documents/{doc['id']}/versions", token, {"content": f"v{n}"})
    versions = _call(gw, "GET", f"/v1/documents/{doc['id']}/versions", token)[1]["versions"]
    assert len(versions) == 5                     # pruned to the free cap
    vid = versions[-1]["id"]
    status, _ = _call(gw, "POST", f"/v1/documents/{doc['id']}/versions/{vid}/restore", token)
    assert status.startswith("201")


def test_cron_requires_secret_and_respects_optout(monkeypatch):
    store, gw, user, token, mailer = _gw()
    monkeypatch.setenv("WB_CRON_SECRET", "s3cret")
    # no secret -> 403
    assert _call(gw, "GET", "/v1/cron/weekly-email")[0].startswith("403")
    # opted out by default -> nobody mailed
    assert _call(gw, "GET", "/v1/cron/weekly-email?secret=s3cret")[1] == {"sent": 0}
    # opt in -> mailed once
    store.set_preferences(user["id"], {"weekly_email": True})
    assert _call(gw, "GET", "/v1/cron/weekly-email?secret=s3cret")[1] == {"sent": 1}
    assert len(mailer.sent) == 1 and mailer.sent[0].to == "a@b.com"
    # unsubscribe (public, signed) -> removed, never mailed again
    tok = weekly.unsubscribe_token(user["id"])
    status, _ = _call(gw, "GET", f"/v1/unsubscribe?u={user['id']}&token={tok}")
    assert status.startswith("200")
    assert store.get_preferences(user["id"])["weekly_email"] is False
    assert _call(gw, "GET", "/v1/cron/weekly-email?secret=s3cret")[1] == {"sent": 0}  # none mailed
    assert len(mailer.sent) == 1                              # no second email composed


# --- CLI snippets (local file) -----------------------------------------------

def test_cli_snippets(tmp_path, monkeypatch, capsys):
    from write_better import cli
    monkeypatch.setenv("WB_SNIPPETS_PATH", str(tmp_path / "snips.json"))
    assert cli.main(["snippets", "add", "/sig", "Best,", "Alex"]) == 0
    assert cli.main(["snippets", "list"]) == 0
    out = capsys.readouterr().out
    assert "/sig\tBest, Alex" in out
    assert cli.main(["snippets", "add", "bad trigger", "x"]) == 2     # whitespace rejected
    assert cli.main(["snippets", "rm", "/sig"]) == 0
    assert cli.main(["snippets", "rm", "/sig"]) == 1                  # already gone
