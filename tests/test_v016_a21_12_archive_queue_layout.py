from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


class A2112ArchiveQueueLayoutTests(unittest.TestCase):
    def test_version(self):
        text = (ROOT / "version.py").read_text(encoding="utf-8")
        assert_v016_at_least(self, text, 21, 12, consolidated_alpha=True)

    def test_runtime_activates_a2112(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from gui.persistent_app_a21_12 import run_gui", source)
        self.assertLess(source.rfind("persistent_app_a21_12"), source.find('if __name__ == "__main__":'))

    def test_queue_has_three_line_contract_without_uuid(self):
        source = (ROOT / "gui" / "depot_result_center_a21_12.py").read_text(encoding="utf-8")
        queue = source[source.index("def _a2112_refresh_archive_queue"):]
        self.assertIn('period_line = f"({period})"', queue)
        self.assertIn('status = "Komplett data"', queue)
        self.assertIn('text="\\n".join(lines)', queue)
        self.assertNotIn("systemID:", queue)
        self.assertNotIn("system_id}", queue)

    def test_queue_restores_centered_compact_visual_rhythm(self):
        source = (ROOT / "gui" / "depot_result_center_a21_12.py").read_text(encoding="utf-8")
        self.assertIn('height=72', source)
        self.assertIn('anchor="center"', source)
        self.assertNotIn('justify="left"', source)

    def test_long_names_are_shortened_only_on_title_line(self):
        source = (ROOT / "gui" / "depot_result_center_a21_12.py").read_text(encoding="utf-8")
        self.assertIn("def _a2112_title", source)
        self.assertIn('title = self._a2112_title(raw_title)', source)


if __name__ == "__main__":
    unittest.main()
