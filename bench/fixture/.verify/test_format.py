import unittest

from ledger.report import format_total


class FormatEdgeCases(unittest.TestCase):
    def test_one_decimal_pads_to_two(self):
        # The obvious f"${amount}" returns "$12.5", not "$12.50".
        self.assertEqual(format_total(12.5), "$12.50")

    def test_whole_number(self):
        self.assertEqual(format_total(12), "$12.00")

    def test_zero(self):
        self.assertEqual(format_total(0), "$0.00")


if __name__ == "__main__":
    unittest.main()
