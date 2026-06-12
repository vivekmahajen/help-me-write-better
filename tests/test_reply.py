"""The `reply` service: draft a response to a message you received."""

from write_better.modes import resolve_one, resolve_services
from write_better.prompt import build_user_message
from write_better.samples import SAMPLES
from write_better.ui import PAGE


def test_reply_is_a_premium_generative_service():
    m = resolve_one("reply")
    assert m.name == "reply"
    assert m.tier == "premium"                       # generative -> top model + premium cap
    assert "RECEIVED" in m.instruction               # treats TEXT as an incoming message
    assert resolve_one("respond").name == "reply"    # alias
    assert resolve_one("reply-to").name == "reply"


def test_reply_sample_is_a_received_message():
    assert SAMPLES["reply"].strip()
    assert SAMPLES["reply"].endswith("Dana")          # it's a message FROM someone


def test_reply_prompt_injects_instruction_and_intent():
    modes = resolve_services("reply")
    msg = build_user_message(
        text="Can you do it by Friday?",
        service_names=[m.name for m in modes],
        output_format="plain", show_changes=False,
        tone="professional",
        free_form="Politely decline; suggest next week instead.",
        service_instructions=[(m.name, m.instruction) for m in modes if m.instruction],
    )
    # the received message is the TEXT, the intent rides in via REQUEST
    assert "Can you do it by Friday?" in msg
    assert "REQUEST       = Politely decline; suggest next week instead." in msg
    assert "message the user RECEIVED" in msg
    assert "do NOT invent facts" in msg


def test_editor_exposes_instruction_field_and_sends_request():
    assert 'id="request"' in PAGE                     # the Instruction box
    assert "request: $('request').value.trim() || null" in PAGE  # sent to the API
    assert "reply:" in PAGE                            # a sample preset for reply
