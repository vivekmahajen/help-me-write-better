import io
import json

import pytest

from write_better.platform import accounts, teams
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store
from write_better.engine import Result
from write_better.modes import resolve_services
from write_better.realtime import brand_suggestions


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def _user(store, email, plan="business"):
    return accounts.create_user(store, email, "supersecret", plan=plan)


# --- org + roles + seats ------------------------------------------------------

def test_create_org_owner_is_admin_seats_from_plan(store):
    owner = _user(store, "owner@b.com", plan="business")
    org = teams.create_org(store, "Acme", owner)
    assert org["seats"] == 5  # business tier
    member = store.get_org_member(org["id"], owner["id"])
    assert member["role"] == "admin"


def test_add_member_requires_admin(store):
    owner = _user(store, "owner@b.com")
    org = teams.create_org(store, "Acme", owner)
    member = teams.add_member(store, org["id"], owner["id"], _user(store, "m@b.com"))
    stranger = _user(store, "s@b.com")
    # a non-admin member cannot add others
    with pytest.raises(teams.PermissionError_):
        teams.add_member(store, org["id"], member["user_id"], stranger)


def test_seat_limit_enforced(store):
    owner = _user(store, "owner@b.com")  # business: 5 seats, owner = 1
    org = teams.create_org(store, "Acme", owner)
    for i in range(4):  # fill to 5 total
        teams.add_member(store, org["id"], owner["id"], _user(store, f"m{i}@b.com"))
    with pytest.raises(teams.SeatLimitError):
        teams.add_member(store, org["id"], owner["id"], _user(store, "over@b.com"))


def test_duplicate_member_rejected(store):
    owner = _user(store, "owner@b.com")
    org = teams.create_org(store, "Acme", owner)
    u = _user(store, "m@b.com")
    teams.add_member(store, org["id"], owner["id"], u)
    with pytest.raises(ValueError):
        teams.add_member(store, org["id"], owner["id"], u)


def test_only_admin_sets_style_guide(store):
    owner = _user(store, "owner@b.com")
    org = teams.create_org(store, "Acme", owner)
    member = teams.add_member(store, org["id"], owner["id"], _user(store, "m@b.com"))
    teams.set_style_guide(store, org["id"], owner["id"], {"tone": "warm"})
    assert teams.get_style_guide(store, org["id"])["tone"] == "warm"
    with pytest.raises(teams.PermissionError_):
        teams.set_style_guide(store, org["id"], member["user_id"], {"tone": "cold"})


# --- style guide rendering + enforcement --------------------------------------

def test_render_style_guide_text():
    text = teams.render_style_guide({
        "tone": "warm", "banned_terms": ["utilize"], "preferred_terms": {"leverage": "use"},
    })
    assert "TEAM STYLE GUIDE" in text
    assert "utilize" in text and "leverage → use" in text


def test_brand_suggestions_flags_banned_terms():
    sugs = brand_suggestions("We utilize synergy daily.", banned_terms=["synergy"],
                             preferred_terms={"utilize": "use"})
    by_text = {("We utilize synergy daily."[s.start:s.end]): s for s in sugs}
    assert by_text["utilize"].replacements == ("use",)   # preferred replacement
    assert by_text["synergy"].replacements == ()         # banned, no replacement


# --- gateway: injection + acceptance ------------------------------------------

def _call(app, method, path, token, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path.split("?")[0],
               "QUERY_STRING": "", "HTTP_AUTHORIZATION": f"Bearer {token}"}
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out) or b"{}")


def _key(store, user):
    token, _ = accounts.create_api_key(store, user["id"])
    return token


def test_member_check_enforces_style_guide(store):
    """Acceptance: an admin sets a style guide; a member's check enforces it."""
    owner = _user(store, "owner@b.com")
    org = teams.create_org(store, "Acme", owner)
    member_user = _user(store, "m@b.com")
    teams.add_member(store, org["id"], owner["id"], member_user)
    teams.set_style_guide(store, org["id"], owner["id"],
                          {"banned_terms": ["synergy"], "preferred_terms": {"utilize": "use"}})

    app = make_gateway(store)
    token = _key(store, member_user)
    _, data = _call(app, "POST", "/v1/check", token, {"text": "We utilize synergy."})
    flagged = {s["range"]["start"]: s for s in data["suggestions"]}
    texts = ["We utilize synergy."[s["range"]["start"]:s["range"]["end"]]
             for s in data["suggestions"]]
    assert "synergy" in texts and "utilize" in texts


def test_improve_injects_style_guide(store):
    captured = {}

    def fake_engine(req):
        captured["req"] = req
        return Result(text="ok", model="claude-haiku-4-5",
                      services=resolve_services(req.services), input_tokens=1, output_tokens=1)

    owner = _user(store, "owner@b.com")
    org = teams.create_org(store, "Acme", owner)
    teams.set_style_guide(store, org["id"], owner["id"], {"tone": "warm and direct"})

    app = make_gateway(store, engine=fake_engine)
    token = _key(store, owner)
    _call(app, "POST", "/v1/improve", token, {"text": "hello", "services": "retone"})
    assert "TEAM STYLE GUIDE" in captured["req"].style_guide
    assert "warm and direct" in captured["req"].style_guide


def test_team_endpoints_create_and_seats(store):
    owner = _user(store, "owner@b.com")
    member_user = _user(store, "m@b.com")
    app = make_gateway(store)
    token = _key(store, owner)

    status, data = _call(app, "POST", "/v1/team", token, {"name": "Acme"})
    assert status.startswith("201")
    assert data["org"]["role"] == "admin" and data["org"]["seats"] == 5

    # admin adds a member by email
    status, data = _call(app, "POST", "/v1/team/members", token, {"email": "m@b.com"})
    assert status.startswith("201")

    # add a non-existent user -> 404
    status, _ = _call(app, "POST", "/v1/team/members", token, {"email": "ghost@b.com"})
    assert status.startswith("404")

    # member cannot edit the style guide -> 403
    mtoken = _key(store, member_user)
    status, _ = _call(app, "PUT", "/v1/team/style-guide", mtoken, {"tone": "x"})
    assert status.startswith("403")


def test_team_seat_limit_returns_402(store):
    owner = _user(store, "owner@b.com")
    app = make_gateway(store)
    token = _key(store, owner)
    _call(app, "POST", "/v1/team", token, {"name": "Acme"})
    for i in range(4):
        _user(store, f"m{i}@b.com")
        _call(app, "POST", "/v1/team/members", token, {"email": f"m{i}@b.com"})
    _user(store, "over@b.com")
    status, data = _call(app, "POST", "/v1/team/members", token, {"email": "over@b.com"})
    assert status.startswith("402") and data["code"] == "seat_limit"
