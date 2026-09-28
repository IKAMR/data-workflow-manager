import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.period_reconciliation import build_period_reconciliation


class A162PeriodReconciliationTests(unittest.TestCase):
    def _write(self, root, test_id, values):
        p = root / "results" / (test_id.replace('.', '_') + '.json')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"test_id": test_id, "values": values}), encoding="utf-8")

    def test_declared_observed_and_journal_crosscheck_are_separate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, 'kdrs.dwm.arkivuttrekk_metadata', {'properties': [
                {'name':'startDate','value':'2007-01-19'}, {'name':'endDate','value':'2099-12-31'}]})
            self._write(root, 'kdrs.c09', {'created_per_year': {'2008': 2, '2020': 1}})
            self._write(root, 'kdrs.c16', {'created_per_year': {'2008': 3, '2099': 2}, 'journalpost_journal_date_per_year': {'2008': 3, '2020': 2}})
            self._write(root, 'kdrs.h02', {'journal_date_per_year': {'2008': 3, '2020': 2}})
            self._write(root, 'kdrs.h06', {'journal_date_per_year': {'2008': 3, '2020': 2}})
            self._write(root, 'kdrs.j01', {'changes_per_year': {'2012': 1, '2020': 1}})
            result = build_period_reconciliation(root)
        self.assertEqual('2007', result['declared_period']['start_year'])
        self.assertEqual('2099', result['declared_period']['end_year'])
        self.assertTrue(result['cross_checks']['journal_year_distribution_match'])
        self.assertEqual('2099', result['observed_series']['registration_created']['span']['last_year'])
        self.assertEqual('2020', result['observed_series']['running_journal']['span']['last_year'])
        self.assertTrue(any(x['category']=='period_source_divergence' for x in result['findings']))

    def test_archive_part_period_is_materialized_from_four_content_levels(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ap = {'index': 1, 'system_id': 'A', 'title': 'Del A'}
            self._write(root, 'kdrs.c09', {'_archive_parts':[{'archive_part':ap,'values':{'created_per_year':{'2008':1}}}]})
            self._write(root, 'kdrs.c16', {'_archive_parts':[{'archive_part':ap,'values':{'created_per_year':{'2009':2},'journalpost_journal_date_per_year':{'2010':2}}}]})
            self._write(root, 'kdrs.c21', {'_archive_parts':[{'archive_part':ap,'values':{'document_description_created_per_year':{'2011':3}}}]})
            self._write(root, 'kdrs.c24', {'_archive_parts':[{'archive_part':ap,'values':{'document_object_parent_created_per_year':{'2012':4}}}]})
            result = build_period_reconciliation(root)
        row = result['archive_parts'][0]
        self.assertEqual({'first_year':'2008','last_year':'2012'}, row['observed_period'])
        self.assertEqual(4, row['metrics']['document_object_parent_created']['span']['count'])


if __name__ == '__main__':
    unittest.main()
