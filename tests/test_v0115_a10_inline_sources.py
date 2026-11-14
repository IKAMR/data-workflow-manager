"""Regression guard: one source list, with explicit external selection."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.canonical_external_selection_v0115_a10 import (
    external_row_metadata, selected_external_rows,
)


class TestInlineSelection(unittest.TestCase):
    def test_previous_source_is_checked_but_new_source_is_not(self):
        candidates = [
            {'path': 'external_evidence/arkade5/1/normalized/arkade5_results.json', 'label': 'Arkade', 'bytes': 600},
            {'path': 'external_evidence/arkade5/1/normalized/pronom_statistics.json', 'label': 'PRONOM', 'bytes': 30},
        ]
        output = external_row_metadata(candidates, [candidates[1]['path']])
        self.assertEqual([x['selected'] for x in output], [False, True])
        self.assertEqual(output[0]['label'], 'Arkade')

    def test_no_initial_auto_selection(self):
        result = external_row_metadata([{'path':'one.json','bytes':1}], [])
        self.assertFalse(result[0]['selected'])

    def test_ignores_duplicate_casefolded_sources(self):
        result = external_row_metadata([{'path':'Foo.json'}, {'path':'foo.json'}], [])
        self.assertEqual(len(result), 1)

    def test_only_checked_external_rows_are_analyzed(self):
        rows = [('master','master.json',True), ('raw','raw.json',True),
                ('external','arkade.json',True), ('external','pronom.json',True),
                ('external','siegfried.json',False)]
        self.assertEqual(selected_external_rows(rows), ('arkade.json','pronom.json'))

    def test_empty_selection_has_no_side_effect(self):
        self.assertEqual(selected_external_rows([('external','x',False)]), ())

    def test_ui_has_no_nested_modal_file_picker_for_external_analysis(self):
        src = (ROOT / 'gui_qt/canonical_results_v0115_a3.py').read_text(encoding='utf8')
        body = src.split('    def analyze_external(self):',1)[1].split('    def create_context(self):',1)[0]
        self.assertNotIn('dlg.exec(', body)
        self.assertNotIn('QFileDialog', body)
        self.assertNotIn('QMessageBox.question', body)
        self.assertIn('self._selected_external()', body)

    def test_refresh_loads_external_candidates_with_dwm_sources(self):
        src = (ROOT / 'gui_qt/canonical_results_v0115_a3.py').read_text(encoding='utf8')
        self.assertIn("result['external_candidates']",src)
        self.assertIn("('external', candidate['path'], 'candidate')",src)
        self.assertIn("if category == 'external':\n                continue",src)


if __name__ == '__main__':
    unittest.main()
