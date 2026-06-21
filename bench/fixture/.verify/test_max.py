import unittest

from ledger.models import Transaction
from ledger.report import max_transaction
from ledger.store import LedgerStore


class MaxEdgeCases(unittest.TestCase):
    def test_max_amount(self):
        s = LedgerStore()
        s.add(Transaction(1, 1, 10.0, "a"))
        s.add(Transaction(2, 1, 99.0, "a"))
        self.assertEqual(max_transaction(s), 99.0)

    def test_empty_store_is_zero(self):
        # The obvious max(...) raises ValueError on an empty sequence.
        self.assertEqual(max_transaction(LedgerStore()), 0.0)


if __name__ == "__main__":
    unittest.main()
