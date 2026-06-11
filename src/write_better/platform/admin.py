"""Admin CLI for the platform: create users + API keys, set plans, view usage.

    python -m write_better.platform.admin create-user  --email a@b.com --password ...
    python -m write_better.platform.admin create-key   --email a@b.com [--name ci]
    python -m write_better.platform.admin set-plan      --email a@b.com --plan pro
    python -m write_better.platform.admin usage         --email a@b.com

Uses the SQLite DB at $WB_DB_PATH (default ./wb.db).
"""

from __future__ import annotations

import argparse
import os
import sys

from . import accounts, metering
from .billing import LocalBillingProvider
from .store import Store


def _store() -> Store:
    return Store(os.environ.get("WB_DB_PATH", "wb.db"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="write-better-admin",
                                description="Manage platform accounts, keys, plans, usage.")
    sub = p.add_subparsers(dest="cmd", required=True)

    cu = sub.add_parser("create-user")
    cu.add_argument("--email", required=True)
    cu.add_argument("--password", required=True)
    cu.add_argument("--plan", default="free")

    ck = sub.add_parser("create-key")
    ck.add_argument("--email", required=True)
    ck.add_argument("--name", default="default")

    sp = sub.add_parser("set-plan")
    sp.add_argument("--email", required=True)
    sp.add_argument("--plan", required=True)

    us = sub.add_parser("usage")
    us.add_argument("--email", required=True)

    args = p.parse_args(argv)
    store = _store()

    try:
        if args.cmd == "create-user":
            user = accounts.create_user(store, args.email, args.password, args.plan)
            print(f"created user #{user['id']} {user['email']} (plan: {user['plan']})")
            return 0

        # all remaining commands need an existing user
        user = store.get_user_by_email(args.email)
        if not user:
            print(f"error: no user with email {args.email!r}", file=sys.stderr)
            return 1

        if args.cmd == "create-key":
            token, rec = accounts.create_api_key(store, user["id"], args.name)
            print(f"API key '{rec['name']}' created. Save it now — it won't be shown again:")
            print(f"  {token}")
            return 0

        if args.cmd == "set-plan":
            LocalBillingProvider().change_plan(store, user["id"], args.plan)
            print(f"{user['email']} is now on plan: {args.plan}")
            return 0

        if args.cmd == "usage":
            q = metering.quota(store, user)
            s = store.usage_since(user["id"], q["period_start"])
            print(f"{user['email']} (plan: {q['plan']})")
            print(f"  premium generations: {q['premium_used']}/{q['premium_cap']} "
                  f"({q['premium_remaining']} remaining this period)")
            print(f"  calls: {s['calls']}  tokens in/out: "
                  f"{s['input_tokens']}/{s['output_tokens']}")
            return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
