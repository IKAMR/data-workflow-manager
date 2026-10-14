import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class RegistrationYearlyProductionTests(unittest.TestCase):
    def test_definition_points_to_existing_c16_year_counts(self):
        root = Path(__file__).resolve().parents[1]
        definition = json.loads((root / 'config/noark5/views/canonical_views.json').read_text(encoding='utf-8'))
        fields = definition['section_library']['yearly_volume']['fields']
        match = next(f for f in fields if f['id'] == 'registration_created_per_year')
        self.assertEqual((match['source_test'], match['source_path']), ('kdrs.c16', 'created_per_year'))

    def test_depot_builder_retains_registration_per_archive_part(self):
        from noark5_workflow.analysis.depot_report_builder import build_depot_report_model
        f = lambda id, value: {'id': id, 'status': 'ok', 'value': value}
        presentation = {'views': [{'id': 'archive_part_overview', 'archive_parts': [
            {'archive_part': {'system_id': 'x'}, 'sections': [{'fields': [
                f('registration_created_per_year', {'2099-12-31': 46}),
                f('registration_count', 46),
                f('folder_created_per_year', {'2099-12-31': 1}),
            ]}]}
        ]}]}
        result = build_depot_report_model(presentation)['archive_parts'][0]['yearly_volume']
        self.assertEqual(result['registration'], {'2099': 46})
        self.assertEqual(result['folder'], {'2099': 1})

    def test_missing_registration_years_remain_missing(self):
        from noark5_workflow.analysis.depot_report_builder import build_depot_report_model
        presentation = {'views': [{'id': 'archive_part_overview', 'archive_parts': [
            {'archive_part': {'system_id': 'x'}, 'sections': [{'fields': []}]}
        ]}]}
        result = build_depot_report_model(presentation)['archive_parts'][0]['yearly_volume']
        self.assertNotIn('registration', result)

    def test_partial_archive_parts_do_not_report_incomplete_sum(self):
        from noark5_workflow.analysis.archive_parts_summary import _sum_yearly
        rows = [{'yearly_volume': {'registration': {'1999': 5}}},
                {'yearly_volume': {'folder': {'1999': 1}}}]
        self.assertNotIn('registration', _sum_yearly(rows))
        rows[1]['yearly_volume']['registration'] = {'1999': 7}
        self.assertEqual(_sum_yearly(rows)['registration'], {'1999': 12})


if __name__ == '__main__':
    unittest.main()
