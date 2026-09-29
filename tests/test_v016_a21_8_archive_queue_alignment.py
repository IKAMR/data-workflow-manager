from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _assert_version_at_least(testcase, version_text, alpha, sub=0):
    match = re.search(r'0\.1\.6-a(\d+)(?:\.(\d+))?', version_text)
    testcase.assertIsNotNone(match)
    actual_alpha = int(match.group(1))
    actual_sub = None if match.group(2) is None else int(match.group(2))
    testcase.assertTrue(actual_alpha > alpha or (actual_alpha == alpha and (actual_sub is None or actual_sub >= sub)))


class TestA218ArchiveQueueAlignment(unittest.TestCase):
    def test_runtime_stays_on_proven_a217_layer(self):
        source = (ROOT / "gui" / "depot_result_center_a21_7.py").read_text(encoding="utf-8")
        self.assertIn("DepotResultCenterDialogA21_7", source)

    def test_uuid_and_multiline_text_are_left_aligned(self):
        source = (ROOT / "gui" / "depot_result_center_a21_7.py").read_text(encoding="utf-8")
        # CTkButton does not support justify=. Left alignment is provided by anchor="w".
        self.assertIn('anchor="w"', source)
        self.assertNotIn('justify="left"', source)

    def test_version(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        _assert_version_at_least(self, version, 21, 8)


if __name__ == "__main__":
    unittest.main()
