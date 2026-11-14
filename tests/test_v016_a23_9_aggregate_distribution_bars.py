from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]
CENTER = ROOT / "gui" / "depot_result_center_a23_9.py"


class A239AggregateDistributionBarsTests(unittest.TestCase):
    def test_runtime_activates_a239_or_newer(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = [
            int(v)
            for v in re.findall(
                r"from gui\.persistent_app_a23_(\d+) import run_gui",
                source,
            )
        ]
        self.assertTrue(imports)
        self.assertGreaterEqual(max(imports), 9)

    def test_version_is_a239_or_newer(self):
        source = (ROOT / "version.py").read_text(encoding="utf-8")
        assert_v016_at_least(self, source, 23, 9)

    def test_distribution_bar_spans_full_row_width(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertIn("columnspan=2", source)
        self.assertIn("Full-width bar below the labels", source)
        self.assertIn("CTkProgressBar", source)
        self.assertIn("share =", source)

    def test_same_renderer_has_no_archive_scope_branch(self):
        source = CENTER.read_text(encoding="utf-8")
        self.assertNotIn("is_all_archive_parts", source)
        self.assertNotIn("is_virtual_selection", source)


if __name__ == "__main__":
    unittest.main()
