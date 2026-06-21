import unittest

from ledger.models import Account, Transaction
from ledger.report import total_for_account
from ledger.store import LedgerStore


class AccountEdgeCases(unittest.TestCase):
    def test_sum_for_account(self):
        s = LedgerStore()
        s.add(Transaction(1, 1, 10.0, "a"))
        s.add(Transaction(2, 1, 5.0, "a"))
        s.add(Transaction(3, 2, 99.0, "b"))
        self.assertEqual(total_for_account(s, 1), 15.0)

    def test_missing_account_is_zero(self):
        self.assertEqual(total_for_account(LedgerStore(), 999), 0.0)


if __name__ == "__main__":
    unittest.main()
