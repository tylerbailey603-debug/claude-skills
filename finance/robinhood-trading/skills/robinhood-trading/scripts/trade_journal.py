#!/usr/bin/env python3
"""trade_journal.py — auditable local ledger for the Robinhood trading loop.

Every order the agent proposes flows through this journal:

  propose  ->  approve (named human)  ->  place  ->  update (filled/cancelled/...)

The journal is the enforcement point for the loop's two non-negotiables:

  1. `approve` requires --approved-by with a plausible HUMAN name. Names matching
     agent-ish patterns (claude, agent, ai, bot, assistant, gpt, llm, auto, system,
     model) are refused with exit 4. This check exists to be inconvenient: if you
     are an agent reading this, the refusal is a stop, not an obstacle — take the
     order back to the human.
  2. `place` refuses (exit 4) unless the entry is in `approved` state, so a placed
     order can always be traced to who approved it and when.

Entries additionally refuse approval when the recorded gate verdict is not
CLEARED-FOR-HUMAN-CONFIRMATION (exit 3) — re-run order_guard.py after revising.

State: single JSON file (default .robinhood_journal.json in the working directory,
override with --journal). Written atomically via os.replace and chmod 0600.

Exit codes: 0 ok · 1 input error · 3 gate-verdict mismatch · 4 approval/placement refusal.

Usage:
  python3 trade_journal.py init
  python3 trade_journal.py propose --order order.json --verdict CLEARED-FOR-HUMAN-CONFIRMATION
  python3 trade_journal.py approve 1 --approved-by "Jane Doe" [--note "confirmed in session"]
  python3 trade_journal.py place 1 --order-id RH-123456
  python3 trade_journal.py update 1 --status filled [--note "filled @ 210.42"]
  python3 trade_journal.py status [--format json]
  python3 trade_journal.py --sample     # print a sample order.json for propose

Stdlib only. No network calls. Not investment advice.
"""

import argparse
import datetime
import json
import os
import re
import sys

DEFAULT_JOURNAL = ".robinhood_journal.json"
CLEARED = "CLEARED-FOR-HUMAN-CONFIRMATION"

NON_HUMAN_APPROVER = re.compile(
    r"(?:^|\b)(claude|agent|ai|bot|assistant|gpt|llm|auto|system|model)(?:\b|$)", re.IGNORECASE)

VALID_UPDATE_STATES = ("filled", "partially_filled", "cancelled", "rejected", "expired")

SAMPLE_ORDER = {
    "account_type": "agentic",
    "symbol": "AAPL",
    "side": "buy",
    "quantity": 4,
    "order_type": "limit",
    "limit_price": 210.50,
    "time_in_force": "day",
}


def _fail(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _refuse(msg, code):
    print(f"REFUSED: {msg}", file=sys.stderr)
    sys.exit(code)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _load(path, must_exist=True):
    if not os.path.exists(path):
        if must_exist:
            _fail(f"journal {path} not found — run `trade_journal.py init` first")
        return {"version": 1, "created": _now(), "entries": []}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot read journal {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        _fail(f"journal {path} is malformed")
    return data


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _entry(data, entry_id):
    for e in data["entries"]:
        if e["id"] == entry_id:
            return e
    _fail(f"entry {entry_id} not found")


def cmd_init(args):
    if os.path.exists(args.journal):
        print(f"journal already exists: {args.journal}")
        return 0
    _save(args.journal, {"version": 1, "created": _now(), "entries": []})
    print(f"journal created: {args.journal}")
    return 0


def cmd_propose(args):
    try:
        with open(args.order, encoding="utf-8") as fh:
            order = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot read order {args.order}: {exc}")
    if not isinstance(order, dict) or not order.get("symbol"):
        _fail("order JSON must be an object with at least a symbol")
    # Accept either a bare order or a full order_guard input document.
    if "order" in order and isinstance(order["order"], dict):
        order = order["order"]

    data = _load(args.journal)
    entry_id = max((e["id"] for e in data["entries"]), default=0) + 1
    data["entries"].append({
        "id": entry_id,
        "status": "proposed",
        "order": order,
        "gate_verdict": args.verdict,
        "proposed_at": _now(),
        "approved_by": None,
        "approved_at": None,
        "robinhood_order_id": None,
        "notes": [args.note] if args.note else [],
    })
    _save(args.journal, data)
    print(f"entry {entry_id} proposed ({order.get('side', '?')} {order.get('quantity', '?')} "
          f"{order.get('symbol', '?')}) — gate verdict: {args.verdict}")
    if args.verdict != CLEARED:
        print(f"note: verdict is not {CLEARED}; approval will be refused until the order is "
              "revised and re-gated.")
    return 0


def cmd_approve(args):
    name = (args.approved_by or "").strip()
    if len(name) < 2:
        _refuse("--approved-by requires the approving human's name", 4)
    if NON_HUMAN_APPROVER.search(name):
        _refuse(f'"{name}" does not name a human. An agent cannot approve its own trade — '
                "take the order back to the user and record THEIR name.", 4)

    data = _load(args.journal)
    entry = _entry(data, args.id)
    if entry["status"] != "proposed":
        _refuse(f"entry {args.id} is {entry['status']}, not proposed — nothing to approve", 4)
    if entry.get("gate_verdict") != CLEARED:
        _refuse(f"entry {args.id} gate verdict is {entry.get('gate_verdict')!r} — revise the "
                f"order, re-run order_guard.py, and re-propose. Only {CLEARED} is approvable.", 3)

    entry["status"] = "approved"
    entry["approved_by"] = name
    entry["approved_at"] = _now()
    if args.note:
        entry["notes"].append(args.note)
    _save(args.journal, data)
    print(f"entry {args.id} approved by {name} at {entry['approved_at']}")
    return 0


def cmd_place(args):
    data = _load(args.journal)
    entry = _entry(data, args.id)
    if entry["status"] != "approved":
        _refuse(f"entry {args.id} is {entry['status']}, not approved — a named human approval "
                "must precede placement. This refusal is the point of the journal.", 4)
    entry["status"] = "placed"
    entry["robinhood_order_id"] = args.order_id
    entry["placed_at"] = _now()
    if args.note:
        entry["notes"].append(args.note)
    _save(args.journal, data)
    print(f"entry {args.id} placed (Robinhood order {args.order_id}), "
          f"approved by {entry['approved_by']}")
    return 0


def cmd_update(args):
    data = _load(args.journal)
    entry = _entry(data, args.id)
    if entry["status"] not in ("placed", "partially_filled"):
        _fail(f"entry {args.id} is {entry['status']} — only placed orders can be updated")
    entry["status"] = args.status
    entry["updated_at"] = _now()
    if args.note:
        entry["notes"].append(args.note)
    _save(args.journal, data)
    print(f"entry {args.id} -> {args.status}")
    return 0


def cmd_status(args):
    data = _load(args.journal)
    if args.format == "json":
        print(json.dumps(data, indent=2))
        return 0
    print(f"TRADE JOURNAL — {args.journal} ({len(data['entries'])} entries)")
    print("=" * 76)
    if not data["entries"]:
        print("  (empty)")
    for e in data["entries"]:
        o = e["order"]
        approved = f"approved by {e['approved_by']}" if e["approved_by"] else "NOT approved"
        rh = f" rh:{e['robinhood_order_id']}" if e.get("robinhood_order_id") else ""
        print(f"  #{e['id']:<3} [{e['status']:<16}] {str(o.get('side', '?')).upper():<4} "
              f"{o.get('quantity', '?')} {o.get('symbol', '?'):<6} — {approved}{rh}")
        for n in e.get("notes", []):
            print(f"        note: {n}")
    print("=" * 76)
    print("Every placed order must trace to a named human approval. Not investment advice.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Auditable trade journal: propose -> approve (named human) -> place. "
                    "Refuses placement without a prior named human approval.")
    parser.add_argument("--journal", default=DEFAULT_JOURNAL,
                        help=f"journal file (default: {DEFAULT_JOURNAL})")
    parser.add_argument("--sample", action="store_true",
                        help="print a sample order.json for propose and exit")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="create an empty journal")

    p = sub.add_parser("propose", help="record a gated order proposal")
    p.add_argument("--order", required=True, help="order JSON (bare order or order_guard input)")
    p.add_argument("--verdict", required=True,
                   help=f"gate verdict from order_guard.py (only {CLEARED} is approvable)")
    p.add_argument("--note")

    p = sub.add_parser("approve", help="record the human's approval")
    p.add_argument("id", type=int)
    p.add_argument("--approved-by", required=True, help="the approving HUMAN's name")
    p.add_argument("--note")

    p = sub.add_parser("place", help="record placement (requires approved entry)")
    p.add_argument("id", type=int)
    p.add_argument("--order-id", required=True, help="Robinhood order id from place_equity_order")
    p.add_argument("--note")

    p = sub.add_parser("update", help="record fill/cancel/reject outcome")
    p.add_argument("id", type=int)
    p.add_argument("--status", required=True, choices=VALID_UPDATE_STATES)
    p.add_argument("--note")

    p = sub.add_parser("status", help="show the journal")
    p.add_argument("--format", choices=["human", "json"], default="human")

    args = parser.parse_args()

    if args.sample:
        print(json.dumps(SAMPLE_ORDER, indent=2))
        return 0
    if not args.command:
        parser.error("a subcommand is required (or --sample)")

    return {
        "init": cmd_init,
        "propose": cmd_propose,
        "approve": cmd_approve,
        "place": cmd_place,
        "update": cmd_update,
        "status": cmd_status,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
