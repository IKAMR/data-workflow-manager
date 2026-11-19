"""a3 release wiring without importing PySide6; preserves a2 and a1 chain."""
from __future__ import annotations
from pathlib import Path
import json
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A3ReleaseWiring(unittest.TestCase):
    def test_version_and_distribution(self):
        from version import VERSION
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.3', 3)
        with (ROOT / 'pyproject.toml').open('rb') as f:
            self.assertEqual(tomllib.load(f)['project']['version'], VERSION.replace('-a', 'a'))

    def test_entrypoint_is_a3_and_inherits_prior_stages(self):
        entry = (ROOT / 'gui_qt/__main__.py').read_text('utf-8')
        main = (ROOT / 'gui_qt/main_v023_a3.py').read_text('utf-8')
        gui = (ROOT / 'gui_qt/ks_value_inspection_v023_a3.py').read_text('utf-8')
        self.assertIn('from gui_qt.main_v023_a3 import DwmMainWindow', entry)
        self.assertIn('from gui_qt.main_v023_a2 import DwmMainWindow as _A2Window', main)
        self.assertIn('from gui_qt.ks_value_inspection_v023_a3 import KsWorkshopDialog', main)
        self.assertIn('class KsWorkshopDialog(_A2KsWorkshopDialog)', gui)
        self.assertIn('class OccurrenceInspectDialog(_A2OccurrenceInspectDialog)', gui)

    def test_inspect_controls_are_on_demand_and_threaded(self):
        gui = (ROOT / 'gui_qt/ks_value_inspection_v023_a3.py').read_text('utf-8')
        for value in ('Standardverdier og uttrekksverdier', 'Perioder og kilder',
                      'Tell faktiske verdier i uttrekket', '_ValueCountWorker',
                      '_PeriodEvidenceWorker', 'requestInterruption()',
                      'self.review_evidence_note', 'self.accept()'):
            self.assertIn(value, gui)
        self.assertNotIn('record_review(', gui)
        self.assertNotIn('api.run_job(', gui)

    def test_declared_delivery_conditions_are_scoped_to_v5(self):
        p = ROOT / 'config/noark5/standards/delivery_value_conditions_v023_a3.json'
        doc = json.loads(p.read_text('utf-8'))
        self.assertEqual(doc['reference_version'], '5.0')
        self.assertEqual({r['metadata_id'] for r in doc['rules']},
                         {'M051', 'M052', 'M053', 'M054'})
        self.assertIn('nasjonalarkivet.no', doc['source']['url'])

    def test_no_user_source_or_work_files_in_release_code(self):
        for path in ('app/ks_value_inspection_v023_a3.py',
                     'gui_qt/ks_value_inspection_v023_a3.py'):
            content = (ROOT / path).read_text('utf-8')
            self.assertNotIn('write_text(', content)
            self.assertNotIn('write_bytes(', content)
            self.assertNotIn('record_review(', content)


if __name__ == '__main__':
    unittest.main()
