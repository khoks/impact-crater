#!/usr/bin/env python
"""Pick up user feedback captured in the app's diagnostics UI (A-023).

This is the bridge between the in-app feedback loop and a Claude Code
session: the user marks pipeline decisions correct / incorrect / different
in the app; this script lists that feedback so Claude (or the user) can act
on it, and marks items triaged/addressed afterward.

Usage:
    python scripts/feedback.py list            # pending (status=new), newest first
    python scripts/feedback.py list --all      # every status
    python scripts/feedback.py show <id>       # full detail incl. decision context
    python scripts/feedback.py mark <id> <status> [--note "..."]
                                               # new|triaged|addressed|dismissed

The SQLite `feedback` table (~/.impact-crater/db/...) is the authoritative
store. ~/.impact-crater/feedback.jsonl is an append-only event log of
submissions only: status changes, triage notes and out-of-band deletions
never reach it, so it is not a mirror and must not be read as one.
Pending schema migrations are applied before any command runs, so the CLI
works against a DB the app has not opened since an upgrade.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sqlite3
import sys

from impact_crater import paths
from impact_crater.storage import migrations

_VALID_STATUS = ("new", "triaged", "addressed", "dismissed")


def _conn() -> sqlite3.Connection:
    asyncio.run(migrations.run_pending_migrations())
    db = sqlite3.connect(str(paths.db_path()))
    db.row_factory = sqlite3.Row
    return db


def cmd_list(args: argparse.Namespace) -> int:
    db = _conn()
    if args.all:
        rows = db.execute("SELECT * FROM feedback ORDER BY created_at DESC, id DESC").fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM feedback WHERE status = 'new' ORDER BY created_at DESC, id DESC"
        ).fetchall()
    if not rows:
        print("No feedback." if args.all else "No pending feedback (status=new).")
        return 0
    print(f"{len(rows)} feedback item(s):\n")
    for r in rows:
        media = f" media={r['content_hash'][:12]}" if r["content_hash"] else ""
        comment = (r["comment"] or "").strip().replace("\n", " ")
        if len(comment) > 100:
            comment = comment[:97] + "..."
        print(
            f"  #{r['id']:<4} [{r['status']:<9}] {r['phase']:<18} {r['verdict']:<9} "
            f"ref={r['decision_ref'] or '-'}{media}"
        )
        if comment:
            print(f"         “{comment}”")
        if r["snapshot_id"]:
            print(f"         snapshot={r['snapshot_id']}")
        if r["triage_note"]:
            print(f"         triage ({(r['triaged_at'] or '')[:10]}): {r['triage_note']}")
    print(
        "\nUse `show <id>` for the full decision context, "
        "`mark <id> <status> --note ...` to triage."
    )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    db = _conn()
    r = db.execute("SELECT * FROM feedback WHERE id = ?", (args.id,)).fetchone()
    if r is None:
        print(f"No feedback #{args.id}.", file=sys.stderr)
        return 1
    d = dict(r)
    if d.get("context_json"):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            d["context"] = json.loads(d.pop("context_json"))
    print(json.dumps(d, indent=2, ensure_ascii=False))
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    if args.status not in _VALID_STATUS:
        print(f"status must be one of {_VALID_STATUS}", file=sys.stderr)
        return 2
    db = _conn()
    cur = db.execute(
        "UPDATE feedback SET status = ?, triage_note = COALESCE(?, triage_note), "
        "triaged_at = CURRENT_TIMESTAMP WHERE id = ?",
        (args.status, args.note, args.id),
    )
    db.commit()
    if cur.rowcount == 0:
        print(f"No feedback #{args.id}.", file=sys.stderr)
        return 1
    print(f"#{args.id} → {args.status}" + (f" — {args.note}" if args.note else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pick up in-app feedback (A-023).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list pending feedback")
    p_list.add_argument("--all", action="store_true", help="include all statuses")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="show one feedback item in full")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_show)

    p_mark = sub.add_parser("mark", help="set an item's status")
    p_mark.add_argument("id", type=int)
    p_mark.add_argument("status", help="|".join(_VALID_STATUS))
    p_mark.add_argument(
        "--note",
        help="why it leaves `new`: the story / PR that addressed it, or the follow-up that will",
    )
    p_mark.set_defaults(func=cmd_mark)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
