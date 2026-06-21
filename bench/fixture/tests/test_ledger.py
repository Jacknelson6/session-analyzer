import unittest

from ledger.models import Account, Transaction
from ledger.report import grand_total, totals_by_category
from ledger.store import LedgerStore


def _store() -> LedgerStore:
    s = LedgerStore()
    s.add_account(Account(1, "checking"))
    s.add(Transaction(1, 1, 10.0, "food"))
    s.add(Transaction(2, 1, 5.0, "food"))
    s.add(Transaction(3, 1, 20.0, "rent"))
    return s


class LedgerTests(unittest.TestCase):
    def test_totals_by_category(self):
        t = totals_by_category(_store())
        self.assertEqual(t["food"], 15.0)
        self.assertEqual(t["rent"], 20.0)

    def test_grand_total(self):
        self.assertEqual(grand_total(_store()), 35.0)

    def test_by_account(self):
        self.assertEqual(len(_store().by_account(1)), 3)


if __name__ == "__main__":
    unittest.main()
