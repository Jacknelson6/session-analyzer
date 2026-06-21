"""In-memory store for accounts and transactions."""

from .models import Account, Transaction


class LedgerStore:
    def __init__(self) -> None:
        self._accounts: dict[int, Account] = {}
        self._txns: dict[int, Transaction] = {}

    def add_account(self, account: Account) -> None:
        self._accounts[account.id] = account

    def add(self, txn: Transaction) -> None:
        self._txns[txn.id] = txn

    def get(self, txn_id: int) -> Transaction:
        return self._txns[txn_id]

    def all(self) -> list[Transaction]:
        return list(self._txns.values())

    def by_account(self, account_id: int) -> list[Transaction]:
        return [t for t in self._txns.values() if t.account_id == account_id]
