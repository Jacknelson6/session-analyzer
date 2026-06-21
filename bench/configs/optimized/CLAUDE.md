# ledger — orientation

Small expense-ledger library. This map is authoritative; trust it instead of
re-exploring the tree.

- `ledger/models.py` — `Account(id, name)`, `Transaction(id, account_id, amount, category, note="")`
- `ledger/store.py` — `LedgerStore`: `add_account`, `add`, `get`, `all`, `by_account(account_id)`
- `ledger/report.py` — `totals_by_category(store)`, `grand_total(store)`
- `ledger/cli.py` — argparse CLI: `list`, `report`; `list_transactions(store)`
- `tests/test_ledger.py` — unittest suite

## Workflow

- Read a file once, in full, before editing it. Do not re-read a file you have
  already loaded this session.
- Verify with `python3 -m unittest discover -s tests -t . -q`. Run it once when
  you are done, not repeatedly.
- Keep edits minimal and match the existing style.
