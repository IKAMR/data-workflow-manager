from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


class A2110ArchiveQueueContentTests(unittest.TestCase):
    def test_version_is_a2110_or_newer(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        assert_v016_at_least(self, text, 21, 10, consolidated_alpha=True)

    def test_runtime_activates_a2110(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a21_10 import run_gui", source)
        self.assertLess(source.rfind("persistent_app_a21_10"), source.find('if __name__ == "__main__":'))

    def test_queue_has_three_line_name_shortname_period_status_contract(self):
        source = (ROOT / "gui" / "depot_result_center_a21_10.py").read_text(encoding="utf-8")
        self.assertIn("short_name", source)
        self.assertIn('period_text = f" ({period})"', source)
        self.assertIn("Komplett data", source)
        self.assertIn("Mangler data:", source)

    def test_queue_does_not_render_uuid_or_systemid(self):
        source = (ROOT / "gui" / "depot_result_center_a21_10.py").read_text(encoding="utf-8")
        queue = source[source.index("def _a2110_refresh_archive_queue"):]
        self.assertNotIn("systemID:", queue)
        self.assertNotIn("f\"{system_id}", queue)

    def test_ctkbutton_uses_supported_left_alignment_only(self):
        source = (ROOT / "gui" / "depot_result_center_a21_10.py").read_text(encoding="utf-8")
        self.assertIn('anchor="w"', source)
        self.assertNotIn('justify="left"', source)


if __name__ == "__main__":
    unittest.main()
