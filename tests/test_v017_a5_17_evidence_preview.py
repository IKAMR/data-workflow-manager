from pathlib import Path
import unittest


class A517EvidencePreviewTests(unittest.TestCase):
    def test_source_select_preview_and_conflict_warning(self):
        source = Path('gui/kdrs_query_results_a4.py').read_text(encoding='utf-8')
        self.assertIn('source_menu.configure(command=refresh_preview)', source)
        self.assertIn('KILDEKONFLIKT:', source)
        self.assertIn("len(distinct) == 1", source)
        self.assertIn('Originale DWM-tall beholdes.', source)
        self.assertIn("preview.grid(row=4, column=1", source)
        self.assertIn("reason_menu.grid(row=5, column=1", source)
        self.assertIn("note.grid(row=6, column=1", source)


if __name__ == '__main__':
    unittest.main()
