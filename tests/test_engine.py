from types import SimpleNamespace

from write_better.engine import (
    PREMIUM_MODEL,
    ROUTINE_MODEL,
    STANDARD_MODEL,
    Request,
    improve,
    route_model,
)
from write_better.modes import resolve_services


def test_route_routine_jobs_to_cheap_model():
    assert route_model(resolve_services("correct")) == ROUTINE_MODEL
    assert route_model(resolve_services("tighten,summarize")) == ROUTINE_MODEL


def test_route_premium_when_any_premium_mode_present():
    # write is premium; mixing with routine still routes premium
    assert route_model(resolve_services("write")) == PREMIUM_MODEL
    assert route_model(resolve_services("correct,paraphrase")) == PREMIUM_MODEL


def test_route_standard_for_standard_modes():
    assert route_model(resolve_services("translate")) == STANDARD_MODEL
    assert route_model(resolve_services("correct,structure")) == STANDARD_MODEL


class _FakeMessages:
    def __init__(self, recorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder["kwargs"] = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="POLISHED")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=3),
        )


class _FakeClient:
    def __init__(self, recorder):
        self.messages = _FakeMessages(recorder)


def test_improve_uses_routed_model_and_returns_text():
    recorder: dict = {}
    req = Request(text="some words here", services=["tighten"])
    result = improve(req, client=_FakeClient(recorder))

    assert result.text == "POLISHED"
    assert result.model == ROUTINE_MODEL
    assert recorder["kwargs"]["model"] == ROUTINE_MODEL
    # Haiku tier must NOT receive thinking/effort (would 400 on the real API).
    assert "thinking" not in recorder["kwargs"]
    assert "output_config" not in recorder["kwargs"]


def test_improve_adds_thinking_for_premium_tier():
    recorder: dict = {}
    req = Request(text="brief: a tagline for a bakery", services=["write"], effort="max")
    improve(req, client=_FakeClient(recorder))

    assert recorder["kwargs"]["model"] == PREMIUM_MODEL
    assert recorder["kwargs"]["thinking"] == {"type": "adaptive"}
    assert recorder["kwargs"]["output_config"] == {"effort": "max"}


def test_user_message_contains_inputs_contract():
    recorder: dict = {}
    req = Request(
        text="hello world",
        services=["translate"],
        output_format="plain",
        language="French",
        show_changes=True,
    )
    improve(req, client=_FakeClient(recorder))
    content = recorder["kwargs"]["messages"][0]["content"]

    assert "SERVICE(S)    = translate" in content
    assert "OUTPUT_FORMAT = plain" in content
    assert "SHOW_CHANGES  = true" in content
    assert "language: French" in content
    assert "hello world" in content


def test_extended_service_instruction_is_injected():
    recorder: dict = {}
    req = Request(text="some words", services=["tone-detect"])
    improve(req, client=_FakeClient(recorder))
    content = recorder["kwargs"]["messages"][0]["content"]
    assert "SERVICE INSTRUCTIONS" in content
    assert "Analyze the TONE" in content
    assert "--- tone-detect ---" in content


def test_core_service_injects_no_instruction_block():
    recorder: dict = {}
    improve(Request(text="x", services=["tighten"]), client=_FakeClient(recorder))
    content = recorder["kwargs"]["messages"][0]["content"]
    assert "SERVICE INSTRUCTIONS" not in content


def test_extended_service_routing():
    assert route_model(resolve_services("tone-detect")) == STANDARD_MODEL
    assert route_model(resolve_services("template")) == PREMIUM_MODEL
    assert route_model(resolve_services("fluency")) == ROUTINE_MODEL


def test_explicit_model_override_wins():
    recorder: dict = {}
    req = Request(text="x", services=["correct"], model="claude-opus-4-8")
    result = improve(req, client=_FakeClient(recorder))
    assert result.model == "claude-opus-4-8"
    # opus is a thinking model -> kwargs include thinking
    assert recorder["kwargs"]["thinking"] == {"type": "adaptive"}
