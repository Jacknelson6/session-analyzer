import unittest

from ledger.report import average_amount
from ledger.store import LedgerStore


class AverageEdgeCases(unittest.TestCase):
    def test_empty_store_is_zero(self):
        # The obvious sum/len implementation raises ZeroDivisionError here.
        self.assertEqual(average_amount(LedgerStore()), 0.0)


if __name__ == "__main__":
    unittest.main()
