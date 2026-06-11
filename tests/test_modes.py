import pytest

from write_better.modes import MODES, resolve_one, resolve_services


def test_every_mode_resolves_by_letter_and_name():
    for mode in MODES:
        assert resolve_one(mode.letter) is mode
        assert resolve_one(mode.name) is mode
        assert resolve_one(mode.letter.lower()) is mode


def test_aliases_resolve():
    assert resolve_one("grammar").name == "correct"
    assert resolve_one("tldr").name == "summarize"
    assert resolve_one("rewrite").name == "paraphrase"
    assert resolve_one("reformat").name == "convert"


def test_resolve_services_dedupes_and_preserves_order():
    modes = resolve_services("tighten, correct, tighten, structure")
    names = [m.name for m in modes]
    assert names == ["tighten", "correct", "structure"]


def test_resolve_services_accepts_list():
    modes = resolve_services(["D", "summarize"])
    assert [m.name for m in modes] == ["tighten", "summarize"]


def test_unknown_service_raises():
    with pytest.raises(ValueError):
        resolve_one("nonsense-mode")


def test_letters_are_unique_and_contiguous():
    letters = [m.letter for m in MODES]
    assert letters == list("ABCDEFGHIJKLM")
