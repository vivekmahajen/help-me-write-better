import io
import json
import time

import pytest

from write_better.platform import accounts, analytics
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def test_word_count():
    assert analytics.word_count("the quick brown fox") == 4
    assert analytics.word_count("don't can't won't") == 3
    assert analytics.word_count("") == 0


def _seed(store, user_id, ts, services="tighten", words=10, suggestions=0, issue_types=None):
    store.insert_usage(user_id, services, "claude-haiku-4-5", premium=False,
                       input_tokens=0, output_tokens=0, ts=ts, words=words,
                       suggestions=suggestions, issue_types=issue_types)


def test_summarize_aggregates(store):
    u = accounts.create_user(store, "a@b.com", "supersecret")
    now = int(time.time())
    _seed(store, u["id"], now - 100, "tighten", words=12)
    _seed(store, u["id"], now - 50, "correct", words=8,
          suggestions=3, issue_types={"spelling": 2, "grammar": 1})

    s = analytics.summarize(store, u["id"], now - 1000)
    assert s["calls"] == 2
    assert s["words"] == 20
    assert s["suggestions"] == 3
    assert s["by_service"] == {"tighten": 1, "correct": 1}
    assert s["by_issue_type"] == {"spelling": 2, "grammar": 1}
    assert s["estimated_minutes_saved"] == round(3 * 20 / 60, 1)
    assert sum(d["calls"] for d in s["by_day"].values()) == 2


def test_weekly_insights_deltas(store):
    u = accounts.create_user(store, "a@b.com", "supersecret")
    now = int(time.time())
    # this week: 2 calls, 30 words; last week: 1 call, 5 words
    _seed(store, u["id"], now - 86400, words=20)
    _seed(store, u["id"], now - 2 * 86400, words=10)
    _seed(store, u["id"], now - 9 * 86400, words=5)

    ins = analytics.weekly_insights(store, u["id"], now=now)
    assert ins["this_week"]["calls"] == 2 and ins["this_week"]["words"] == 30
    assert ins["last_week"]["calls"] == 1 and ins["last_week"]["words"] == 5
    assert ins["deltas"]["calls"] == 1
    assert ins["deltas"]["words"] == 25


def test_rollup_over_multiple_users(store):
    now = int(time.time())
    a = accounts.create_user(store, "a@b.com", "supersecret")
    b = accounts.create_user(store, "b@b.com", "supersecret")
    c = accounts.create_user(store, "c@b.com", "supersecret")  # inactive
    _seed(store, a["id"], now - 100, words=10, suggestions=2, issue_types={"spelling": 2})
    _seed(store, b["id"], now - 100, words=5, suggestions=1, issue_types={"grammar": 1})

    r = analytics.rollup(store, [a["id"], b["id"], c["id"]], now - 1000)
    assert r["members"] == 3
    assert r["active_users"] == 2
    assert r["total_words"] == 15
    assert r["top_issues"] == {"spelling": 2, "grammar": 1}


# --- gateway endpoint + instrumentation --------------------------------------

def _call(app, method, path, token, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path.split("?")[0],
               "QUERY_STRING": path.split("?")[1] if "?" in path else "",
               "HTTP_AUTHORIZATION": f"Bearer {token}"}
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out))


def test_check_records_words_and_issue_types(store):
    u = accounts.create_user(store, "a@b.com", "supersecret")
    token, _ = accounts.create_api_key(store, u["id"])
    app = make_gateway(store)
    _call(app, "POST", "/v1/check", token, {"text": "i dont recieve teh thing"})

    s = analytics.summarize(store, u["id"], 0)
    assert s["words"] == 5
    assert s["suggestions"] >= 3
    assert "spelling" in s["by_issue_type"]


def test_analytics_endpoint(store):
    u = accounts.create_user(store, "a@b.com", "supersecret")
    token, _ = accounts.create_api_key(store, u["id"])
    app = make_gateway(store)
    _call(app, "POST", "/v1/check", token, {"text": "teh cat"})

    status, data = _call(app, "GET", "/v1/analytics?window=30", token)
    assert status.startswith("200")
    assert data["window_days"] == 30
    assert data["summary"]["calls"] == 1
    assert "this_week" in data["insights"]
