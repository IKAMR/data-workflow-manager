from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


class A2111ArchiveQueueContentTests(unittest.TestCase):
    def test_version(self):
        text=(ROOT/'version.py').read_text(encoding='utf-8')
        assert_v016_at_least(self, text, 21, 11, consolidated_alpha=True)

    def test_runtime(self):
        source=(ROOT/'main.py').read_text(encoding='utf-8')
        self.assertIn('from gui.persistent_app_a21_11 import run_gui', source)
        self.assertLess(source.rfind('persistent_app_a21_11'), source.find('if __name__ == "__main__":'))

    def test_queue_omits_shortname_and_keeps_period(self):
        source=(ROOT/'gui'/'depot_result_center_a21_11.py').read_text(encoding='utf-8')
        queue=source[source.index('def _a2111_refresh_archive_queue'):]
        self.assertIn('period_text = f"({period})"', queue)
        self.assertIn('text = f"{line1}\\n{period_text}\\n{status}"', queue)
        self.assertNotIn('_a2111_materialized_short_name(row)', queue)

    def test_long_titles_are_shortened_without_uuid(self):
        source=(ROOT/'gui'/'depot_result_center_a21_11.py').read_text(encoding='utf-8')
        self.assertIn('_a2111_compact_title', source)
        queue=source[source.index('def _a2111_refresh_archive_queue'):]
        self.assertNotIn('systemID:', queue)
        self.assertNotIn('justify="left"', source)
        self.assertIn('anchor="w"', source)


if __name__ == '__main__':
    unittest.main()
