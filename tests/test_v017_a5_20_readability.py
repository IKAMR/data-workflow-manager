import unittest
from pathlib import Path
from noark5_workflow.external_evidence.archive_part_evidence_a5 import evidence_table_rows


class ReadableEvidenceTests(unittest.TestCase):
    def test_human_labels_missing_and_selected_zero(self):
        annex = {'records': [
            {'archive_part_index': 43, 'metric_id': 'folder_count', 'dwm_value': None,
             'external_unique_values': [2188], 'status': 'external_evidence_selected',
             'effective_value': 2188, 'evidence': {'source_file':'U02.txt','source_line_number':8,'reason':'missing_dwm_test'}},
            {'archive_part_index': 43, 'metric_id': 'correspondence_party_count', 'dwm_value': None,
             'external_unique_values': [0], 'status': 'missing'},
            {'archive_part_index': 42, 'metric_id': 'folder_count', 'dwm_value': None,
             'external_unique_values': [324], 'status': 'missing'}]}
        rows = evidence_table_rows(annex, 43)
        self.assertEqual(len(rows), 2)
        self.assertIn(('Mapper', 'Ukjent', '2 188', '2 188', 'DWM mangler verdi'), [r['cells'] for r in rows])
        self.assertTrue(any(r['cells'][0]=='Korrespondanseparter' and r['cells'][2]=='0' for r in rows))
        self.assertTrue(any('U02.txt' in r['detail'] for r in rows))

    def test_report_shows_approved_source_near_top(self):
        source=(Path(__file__).resolve().parents[1]/'noark5_workflow/external_evidence/derived_depot_html_a5.py').read_text(encoding='utf8')
        self.assertIn('Godkjente verdier og kilde',source)
        self.assertIn('Full kildesporbarhet',source)

if __name__ == '__main__': unittest.main()
