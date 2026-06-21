"""Minimal command-line interface for the ledger."""

import argparse

from .report import totals_by_category
from .store import LedgerStore


def list_transactions(store: LedgerStore) -> list:
    """Return all transactions ordered by id."""
    return sorted(store.all(), key=lambda t: t.id)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ledger")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list transactions")
    sub.add_parser("report", help="totals by category")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    store = LedgerStore()
    if args.cmd == "list":
        for t in list_transactions(store):
            print(f"{t.id}\t{t.category}\t{t.amount}")
    elif args.cmd == "report":
        for cat, total in totals_by_category(store).items():
            print(f"{cat}\t{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
