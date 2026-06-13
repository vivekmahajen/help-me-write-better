"""Search Console ownership meta tag (for the Safe Browsing review)."""

from write_better import seo


def test_verification_meta_present_only_when_env_set():
    assert seo._verification({}) == ""
    tag = seo._verification({"WB_GOOGLE_VERIFICATION": "tok123"})
    assert 'name="google-site-verification" content="tok123"' in tag


def test_verification_value_is_escaped():
    tag = seo._verification({"WB_GOOGLE_VERIFICATION": 'a"<b'})
    assert '"' not in tag.split("content=")[1][1:].split('"')[0] or "&quot;" in tag
    assert "&lt;" in tag
