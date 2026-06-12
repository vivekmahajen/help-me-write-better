"""The `send-check` service: a single pre-send readiness verdict."""

from write_better.modes import resolve_one, resolve_services
from write_better.prompt import build_user_message
from write_better.samples import SAMPLES


def test_send_check_is_a_standard_analysis_service():
    m = resolve_one("send-check")
    assert m.name == "send-check"
    assert m.tier == "standard"                       # analysis, not generation
    # the differentiator: an emotional/regret risk flag, not just errors
    assert "Regret/escalation risk" in m.instruction
    assert "VERDICT" in m.instruction
    for alias in ("send-readiness", "pre-send", "before-send"):
        assert resolve_one(alias).name == "send-check"


def test_send_check_sample_is_a_risky_message():
    s = SAMPLES["send-check"]
    assert s.strip()
    assert "THIRD" in s                                # an angry, regret-prone draft


def test_send_check_prompt_injects_the_checklist():
    modes = resolve_services("send-check")
    msg = build_user_message(
        text="If I don't get this by tomorrow I'm done with you people.",
        service_names=[m.name for m in modes],
        output_format="plain", show_changes=False,
        service_instructions=[(m.name, m.instruction) for m in modes if m.instruction],
    )
    assert "SEND-READINESS" in msg
    assert "Send | Review | Hold" in msg
    assert "do NOT rewrite" in msg
