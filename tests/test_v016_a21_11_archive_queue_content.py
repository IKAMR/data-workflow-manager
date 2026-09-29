from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A2111ArchiveQueueContentTests(unittest.TestCase):
    def test_version(self):
        text=(ROOT/'version.py').read_text(encoding='utf-8')
        m=re.search(r'0\.1\.6-a(\d+)(?:\.(\d+))?', text)
        self.assertIsNotNone(m)
        self.assertTrue(int(m.group(1)) > 21 or (int(m.group(1)) == 21 and (m.group(2) is None or int(m.group(2)) >= 11)))

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
