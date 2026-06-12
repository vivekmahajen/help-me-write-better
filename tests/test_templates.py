import io
import json

import pytest

from write_better import templating as t
from write_better.platform import accounts
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store
from write_better.engine import Result
from write_better.modes import resolve_services


# --- YAML subset parser -------------------------------------------------------

def test_parse_yaml_shape():
    data = t.parse_yaml(
        'id: demo\n'
        'name: Demo\n'
        'fields:\n'
        '  - { key: a, label: "A", type: text, required: true }\n'
        '  - { key: b, type: select, options: [x, y, z], default: x }\n'
        'defaults: { service: write, format: email }\n'
        'variants: 3\n'
        'prompt: |\n'
        '  Hello {a}.\n'
        '  {{#b}}B is {b}.{{/b}}\n'
    )
    assert data["id"] == "demo"
    assert data["fields"][0]["required"] is True
    assert data["fields"][1]["options"] == ["x", "y", "z"]
    assert data["defaults"]["service"] == "write"
    assert data["variants"] == 3
    assert data["prompt"].startswith("Hello {a}.")


# --- loading + rendering ------------------------------------------------------

def test_marketing_templates_load():
    tpls = t.load_templates()
    assert len(tpls) >= 10
    assert "cold-email-b2b" in tpls
    assert all(tp.category for tp in tpls.values())


def test_list_templates_category_filter():
    marketing = t.list_templates("marketing")
    assert marketing and all(s["category"] == "marketing" for s in marketing)
    assert t.list_templates("nope") == []


def test_render_fills_defaults_and_conditionals():
    tpl = t.get_template("cold-email-b2b")
    out = t.validate_and_render(tpl, {"product": "Acme", "audience": "teams", "cta": "Demo"})
    assert "Acme" in out and "direct" in out      # tone default applied
    assert "Anchor on this pain point" not in out  # optional section omitted


def test_missing_required_fields_raise():
    tpl = t.get_template("cold-email-b2b")
    with pytest.raises(t.MissingFields) as exc:
        t.validate_and_render(tpl, {"product": "Acme"})
    assert set(exc.value.missing) == {"audience", "cta"}


def test_inverted_section():
    tpl = t.get_template("feature-benefit")
    out = t.validate_and_render(tpl, {"features": "fast, secure"})
    assert "the customer" in out  # {{^audience}} fallback


# --- gateway ------------------------------------------------------------------

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
    return cap["status"], json.loads(b"".join(out) or b"{}")


def _setup(store, plan="pro"):
    user = accounts.create_user(store, "a@b.com", "supersecret", plan=plan)
    token, _ = accounts.create_api_key(store, user["id"])
    captured = {"texts": [], "calls": 0}

    def engine(req):
        captured["calls"] += 1
        captured["texts"].append(req.text)
        return Result(text=f"VARIANT-{captured['calls']}", model="claude-opus-4-8",
                      services=resolve_services(req.services), input_tokens=10, output_tokens=5)

    return make_gateway(store, engine=engine), token, captured


def test_gateway_list_templates_drives_forms(store=None):
    store = Store(":memory:")
    app, token, _ = _setup(store)
    status, data = _call(app, "GET", "/v1/templates?category=marketing", token)
    assert status.startswith("200")
    ids = {tp["id"] for tp in data["templates"]}
    assert "cold-email-b2b" in ids
    # schema is sufficient to render a form
    ce = next(tp for tp in data["templates"] if tp["id"] == "cold-email-b2b")
    assert all("key" in f and "type" in f for f in ce["fields"])


def test_gateway_template_produces_variants():
    store = Store(":memory:")
    app, token, captured = _setup(store, plan="pro")
    status, data = _call(app, "POST", "/v1/improve", token, {
        "template": "cold-email-b2b",
        "template_fields": {"product": "Acme CRM", "audience": "ops teams", "cta": "Book a demo"},
    })
    assert status.startswith("200")
    assert data["template"] == "cold-email-b2b"
    assert len(data["variants"]) == 3                  # template variants: 3
    assert captured["calls"] == 3
    assert "Acme CRM" in captured["texts"][0]          # rendered prompt was the input


def test_gateway_unknown_template_422():
    store = Store(":memory:")
    app, token, _ = _setup(store)
    status, data = _call(app, "POST", "/v1/improve", token, {"template": "nope"})
    assert status.startswith("422") and data["code"] == "unknown_template"


def test_gateway_missing_field_422_echoes_schema():
    store = Store(":memory:")
    app, token, _ = _setup(store)
    status, data = _call(app, "POST", "/v1/improve", token,
                         {"template": "cold-email-b2b", "template_fields": {"product": "x"}})
    assert status.startswith("422") and data["code"] == "missing_fields"
    assert "audience" in data["missing"]
    assert any(f["key"] == "audience" for f in data["fields"])  # schema echoed


def test_variants_clamped_by_plan_cap():
    store = Store(":memory:")
    # starter cap 100; set used near the cap so only 2 remain
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="starter")
    token, _ = accounts.create_api_key(store, user["id"])
    for _ in range(98):
        store.insert_usage(user["id"], "write", "claude-opus-4-8", premium=True,
                           input_tokens=0, output_tokens=0)
    calls = {"n": 0}

    def engine(req):
        calls["n"] += 1
        return Result(text="x", model="m", services=resolve_services(req.services),
                      input_tokens=1, output_tokens=1)

    app = make_gateway(store, engine=engine)
    status, data = _call(app, "POST", "/v1/improve", token, {
        "template": "cold-email-b2b",  # wants 3 variants
        "template_fields": {"product": "x", "audience": "y", "cta": "z"}})
    assert status.startswith("200")
    assert len(data["variants"]) == 2 and calls["n"] == 2   # clamped to remaining
