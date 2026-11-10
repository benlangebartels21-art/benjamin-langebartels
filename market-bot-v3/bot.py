#!/usr/bin/env python3
"""Market Bot V3 command line. Research and education only, not financial advice."""
import argparse
import json
import sys

from mbv3 import ledger, rules


def cmd_ledger(args):
    conn = ledger.connect(args.db)
    if args.action == "add":
        with open(args.file) as f:
            items = json.load(f)
        for p in items if isinstance(items, list) else [items]:
            pid = ledger.add_prediction(conn, p, backfill=args.backfill)
            print(f"stored prediction #{pid} {p['ticker']}" + (" (BACKFILLED)" if args.backfill else ""))
    elif args.action == "list":
        for p in ledger.list_predictions(conn, args.date):
            flags = (" APPROXIMATE" if rules.is_approximate(p["trigger_rule"]) else "") + (
                " BACKFILLED" if p["backfilled"] else "")
            print(f"#{p['id']} {p['issue_date']} {p['ticker']:<6} {p['type']:<5} {p['strategy']:<20} "
                  f"score {p['score']:.1f} conf {p['confidence_pct']:.0f}% stop {p['stop_price']:g} "
                  f"({p['stop_type']}) T1 {p['target1']:g} T2 {p['target2']:g} {p['timeframe_days']}d{flags}")
    elif args.action == "show":
        print(json.dumps(ledger.get_prediction(conn, args.id), indent=2))
    elif args.action == "verify":
        ok, msg = ledger.verify_chain(conn)
        print(("OK: " if ok else "FAIL: ") + msg)
        return 0 if ok else 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bot.py", description=__doc__)
    ap.add_argument("--db", default=str(ledger.DEFAULT_DB), help="ledger database path")
    sub = ap.add_subparsers(dest="cmd", required=True)
    led = sub.add_parser("ledger", help="prediction ledger").add_subparsers(dest="action", required=True)
    add = led.add_parser("add", help="append prediction(s) from a JSON file")
    add.add_argument("file")
    add.add_argument("--backfill", action="store_true",
                     help="allow a past issue date; the row is permanently flagged BACKFILLED")
    led.add_parser("list", help="list predictions").add_argument("--date", help="issue date YYYY-MM-DD")
    led.add_parser("show", help="show one prediction").add_argument("id", type=int)
    led.add_parser("verify", help="check the hash chain")
    args = ap.parse_args(argv)
    try:
        return {"ledger": cmd_ledger}[args.cmd](args)
    except (ledger.LedgerError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
