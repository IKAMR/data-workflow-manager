import unittest

from gui.depot_result_center_a16_4 import DepotResultCenterDialogA16_4


class A164PeriodViewTests(unittest.TestCase):
    def test_span_text(self):
        self.assertEqual(DepotResultCenterDialogA16_4._span_text({"first_year":"2008","last_year":"2020"}), "2008–2020")
        self.assertEqual(DepotResultCenterDialogA16_4._span_text({}), "–")


if __name__ == "__main__":
    unittest.main()
