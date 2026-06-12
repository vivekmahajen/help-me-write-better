"""The owner/admin account (vmahajans@yahoo.com) bypasses every plan cap."""

from write_better import plans
from write_better.modes import resolve_services
from write_better.platform import accounts, metering, scans
from write_better.platform.store import Store


def _store():
    return Store(":memory:")


def test_default_admin_is_the_owner_email():
    assert plans.is_admin("vmahajans@yahoo.com") is True
    assert plans.is_admin("VMahajanS@Yahoo.com ") is True   # case/space-insensitive
    assert plans.is_admin("someone@else.com") is False
    assert plans.is_admin(None) is False


def test_admin_emails_env_override(monkeypatch):
    monkeypatch.setenv("WB_ADMIN_EMAILS", "boss@corp.com, vip@corp.com")
    assert plans.is_admin("boss@corp.com") is True
    assert plans.is_admin("vip@corp.com") is True
    assert plans.is_admin("vmahajans@yahoo.com") is False    # replaced by the override


def test_admin_premium_quota_is_unlimited_even_on_free_plan():
    store = _store()
    # Force the stored plan to free to prove the bypass is by email, not plan.
    user = store.insert_user("vmahajans@yahoo.com", "x", plan="free")
    q = metering.quota(store, user)
    assert q["unlimited"] is True
    assert q["premium_cap"] == plans.UNLIMITED
    # A premium request is allowed regardless of usage.
    allowed, _ = metering.check_allowed(store, user, resolve_services("write"))
    assert allowed is True


def test_non_admin_free_user_is_still_capped():
    store = _store()
    user = accounts.create_user(store, "normal@user.com", "supersecret")  # free plan
    q = metering.quota(store, user)
    assert q["unlimited"] is False
    allowed, _ = metering.check_allowed(store, user, resolve_services("write"))
    assert allowed is False                                  # free has 0 premium gens


def test_admin_signup_starts_on_top_tier():
    store = _store()
    user = accounts.create_user(store, "vmahajans@yahoo.com", "supersecret")
    assert user["plan"] == "business"                        # complete UI...
    assert metering.quota(store, user)["unlimited"] is True  # ...and uncapped


def test_admin_scan_quota_is_unlimited():
    store = _store()
    user = store.insert_user("vmahajans@yahoo.com", "x", plan="free")
    q = scans.quota(store, user, since_ts=0)
    assert q["unlimited"] is True
    assert q["scan_credits_remaining"] >= plans.UNLIMITED - 0
    # A normal free user gets zero scan credits.
    normal = accounts.create_user(store, "n@u.com", "supersecret")
    assert scans.quota(store, normal, since_ts=0)["scan_credits_remaining"] == 0
