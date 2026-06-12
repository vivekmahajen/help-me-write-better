"""The `dictate` service: rambly voice/dictation transcript -> clean prose."""

from write_better.modes import resolve_one, resolve_services
from write_better.prompt import build_user_message
from write_better.samples import SAMPLES


def test_dictate_is_a_standard_service():
    m = resolve_one("dictate")
    assert m.name == "dictate"
    assert m.tier == "standard"
    for alias in ("voice-memo", "dictation", "transcribe-clean"):
        assert resolve_one(alias).name == "dictate"


def test_dictate_instruction_targets_spoken_filler():
    m = resolve_one("dictate")
    assert "transcript" in m.instruction
    assert "filler" in m.instruction
    assert "do not add" in m.instruction.lower()      # preserves meaning, invents nothing


def test_dictate_sample_is_a_rambly_transcript():
    s = SAMPLES["dictate"]
    assert s.strip()
    assert "um" in s and "uh" in s                     # actually rambly


def test_dictate_prompt_injects_instruction():
    modes = resolve_services("dictate")
    msg = build_user_message(
        text="um so like i think we should uh ship it friday you know",
        service_names=[m.name for m in modes],
        output_format="plain", show_changes=False,
        service_instructions=[(m.name, m.instruction) for m in modes if m.instruction],
    )
    assert "raw voice/dictation transcript" in msg
    assert "Remove verbal filler" in msg
