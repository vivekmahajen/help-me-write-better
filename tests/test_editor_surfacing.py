"""The editor surfaces the new services: dictate mic, scrub scan, personalize."""

from write_better.ui import PAGE


def test_mic_button_uses_speech_api_and_selects_dictate():
    assert 'id="mic"' in PAGE
    assert "SpeechRecognition" in PAGE              # Web Speech API
    assert 'value="dictate"' in PAGE                # auto-selects dictate while recording


def test_scan_button_calls_scrub_endpoint():
    assert 'id="scan"' in PAGE
    assert "/scrub" in PAGE
    assert 'id="apply"' in PAGE                     # "use redacted" action


def test_personalize_fields_map_to_open_api():
    assert 'id="protected"' in PAGE and "protected_terms:" in PAGE   # #5 never-flag
    assert 'id="voice"' in PAGE and "voice_sample:" in PAGE          # #4 voice profile
