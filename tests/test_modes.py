import pytest

from write_better.modes import MODES, resolve_one, resolve_services


def test_every_mode_resolves_by_name():
    for mode in MODES:
        assert resolve_one(mode.name) is mode


def test_lettered_modes_resolve_by_letter():
    for mode in MODES:
        if mode.letter:
            assert resolve_one(mode.letter) is mode
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


def test_core_letters_are_unique_and_contiguous():
    letters = [m.letter for m in MODES if m.letter]
    assert letters == list("ABCDEFGHIJKLM")


def test_extended_services_carry_instructions():
    extended = [m for m in MODES if not m.letter]
    assert len(extended) == 26
    assert all(m.instruction.strip() for m in extended)
    # Core modes are defined in the operator prompt, not via instructions.
    assert all(not m.instruction for m in MODES if m.letter)


def test_total_service_count():
    assert len(MODES) == 39


def test_new_services_resolve_by_name():
    for name in ("tone-detect", "humanize", "score", "fiction", "fluency", "cite"):
        assert resolve_one(name).name == name


def test_no_name_letter_or_alias_collisions():
    keys: list[str] = []
    for m in MODES:
        keys.append(m.name.lower())
        if m.letter:
            keys.append(m.letter.lower())
        keys.extend(a.lower() for a in m.aliases)
    assert len(keys) == len(set(keys)), "duplicate name/letter/alias across services"
