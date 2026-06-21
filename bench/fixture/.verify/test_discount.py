import unittest

from ledger.report import apply_discount


class DiscountEdgeCases(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(apply_discount(100, 10), 90)

    def test_clamp_above_100(self):
        self.assertEqual(apply_discount(100, 150), 0)

    def test_clamp_below_0(self):
        self.assertEqual(apply_discount(100, -10), 100)


if __name__ == "__main__":
    unittest.main()
