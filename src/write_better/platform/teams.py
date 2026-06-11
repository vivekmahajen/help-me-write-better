"""Teams / organizations and the shared brand-voice style guide (#8).

An org has members with roles (admin/member) and a seat count tied to its plan
(`plans.py`). Admins edit a shared style guide; every member inherits it — it's
injected into the engine's brand-voice on `/v1/improve` and enforced as banned
terms on `/v1/check`.
"""

from __future__ import annotations

import json
from typing import Optional

from ..plans import PLANS_BY_NAME
from .store import Store


class SeatLimitError(Exception):
    pass


class PermissionError_(Exception):
    pass


def create_org(store: Store, name: str, owner: dict, plan: str = "business") -> dict:
    plan = plan.lower()
    if plan not in PLANS_BY_NAME:
        raise ValueError(f"unknown plan {plan!r}")
    seats = PLANS_BY_NAME[plan].seats
    return store.insert_org(name, owner["id"], plan, seats)


def require_admin(store: Store, org_id: int, user_id: int) -> None:
    member = store.get_org_member(org_id, user_id)
    if not member or member["role"] != "admin":
        raise PermissionError_("admin role required")


def add_member(store: Store, org_id: int, actor_id: int, new_user: dict,
               role: str = "member") -> dict:
    require_admin(store, org_id, actor_id)
    if role not in ("admin", "member"):
        raise ValueError("role must be 'admin' or 'member'")
    if store.get_org_member(org_id, new_user["id"]):
        raise ValueError("user is already a member")
    org = store.get_org(org_id)
    if store.count_org_members(org_id) >= org["seats"]:
        raise SeatLimitError(f"seat limit reached ({org['seats']} seats on the "
                             f"{org['plan']} plan)")
    return store.add_org_member(org_id, new_user["id"], role)


def remove_member(store: Store, org_id: int, actor_id: int, user_id: int) -> None:
    require_admin(store, org_id, actor_id)
    org = store.get_org(org_id)
    if user_id == org["owner_user_id"]:
        raise ValueError("cannot remove the org owner")
    store.remove_org_member(org_id, user_id)


def set_style_guide(store: Store, org_id: int, actor_id: int, guide: dict) -> dict:
    require_admin(store, org_id, actor_id)
    if not isinstance(guide, dict):
        raise ValueError("style guide must be an object")
    store.set_org_style_guide(org_id, json.dumps(guide))
    return guide


def get_style_guide(store: Store, org_id: int) -> dict:
    org = store.get_org(org_id)
    if not org:
        return {}
    try:
        return json.loads(org["style_guide"] or "{}")
    except (ValueError, TypeError):
        return {}


def org_for_user(store: Store, user_id: int) -> Optional[dict]:
    return store.get_org_for_user(user_id)


# --- style-guide helpers used by the engine + checks --------------------------

def render_style_guide(guide: dict) -> str:
    """A compact text rendering injected into the engine's brand-voice."""
    if not guide:
        return ""
    lines = ["TEAM STYLE GUIDE (apply as brand-voice rules):"]
    if guide.get("tone"):
        lines.append(f"- Tone: {guide['tone']}")
    if guide.get("formality"):
        lines.append(f"- Formality: {guide['formality']}")
    if guide.get("banned_terms"):
        lines.append(f"- Never use: {', '.join(guide['banned_terms'])}")
    if guide.get("preferred_terms"):
        prefs = ", ".join(f"{k} → {v}" for k, v in guide["preferred_terms"].items())
        lines.append(f"- Prefer: {prefs}")
    if guide.get("formatting_rules"):
        lines.append(f"- Formatting: {guide['formatting_rules']}")
    if guide.get("notes"):
        lines.append(f"- Notes: {guide['notes']}")
    return "\n".join(lines) if len(lines) > 1 else ""


def banned_and_preferred(guide: dict) -> tuple[list[str], dict]:
    """Extract the (banned_terms, preferred_terms) used by the real-time check."""
    banned = list(guide.get("banned_terms") or [])
    preferred = dict(guide.get("preferred_terms") or {})
    return banned, preferred
