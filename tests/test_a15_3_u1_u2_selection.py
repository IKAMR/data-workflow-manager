"""a15.3 regression: composite U01/U02 require explicit regression run."""
import json
from pathlib import Path
import unittest

from noark5_workflow.analysis.xpath_test_engine import _select_catalog_tests

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'config/noark5/tests/xpath_catalog_2026_05_26.json'


class A153SelectionTests(unittest.TestCase):
    def test_composite_jobs_only_in_explicit_regression_profile(self):
        catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        normal, _ = _select_catalog_tests(catalog, execution_profile='normal', include_disabled=True)
        regression, _ = _select_catalog_tests(catalog, execution_profile='regression', include_disabled=True)
        normal_ids = {row['test_id'] for row in normal}
        regression_ids = {row['test_id'] for row in regression}
        self.assertNotIn('kdrs.u01', normal_ids)
        self.assertNotIn('kdrs.u02', normal_ids)
        self.assertIn('kdrs.u01', regression_ids)
        self.assertIn('kdrs.u02', regression_ids)
        self.assertEqual(len(normal), len(regression) - 2)


if __name__ == '__main__':
    unittest.main()
