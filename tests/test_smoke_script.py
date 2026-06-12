import os
import stat
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke.sh"


def test_smoke_script_exists_and_is_executable():
    assert SCRIPT.is_file()
    assert os.stat(SCRIPT).st_mode & stat.S_IXUSR  # executable bit set


def test_smoke_script_covers_every_feature():
    text = SCRIPT.read_text()
    for endpoint in ("/v1/check", "/v1/fingerprint", "/v1/cite", "/v1/templates",
                     "/v1/scan", "/v1/improve", "/v1/documents", "/v1/team",
                     "/v1/analytics", "/billing/plans"):
        assert endpoint in text, f"smoke.sh does not exercise {endpoint}"
    # adapts to optional keys rather than hard-failing
    assert "ORIGINALITY_API_KEY" in text and "ANTHROPIC_API_KEY" in text
