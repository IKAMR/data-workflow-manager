from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import ModuleType
import sys

from noark5_workflow.external_evidence.derived_depot_html_a5 import write_derived_depot_html


class DerivedHtmlTests(unittest.TestCase):
    def test_renders_marked_report_with_provenance_and_preserves_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native = root / 'depot_validation_report.html'
            native.write_text('UNCHANGED', encoding='utf-8')
            source = root / 'depot-derived-evidence-report.json'
            source.write_text(json.dumps({'external_evidence_application': {
                'derived_report': True, 'native_report_sha256': 'abc123', 'applied': [{
                    'scope': 'part:2', 'metric': 'folder_count', 'dwm_value': None,
                    'effective_value': 66834, 'evidence': {'source_file': '<source.txt>',
                    'test_id': 'T01', 'line': 33}}]}}), encoding='utf-8')
            def render(_report, target):
                Path(target).write_text('<html><body><main>Rapport</main></body></html>', encoding='utf-8')
            module = ModuleType('noark5_workflow.analysis.depot_report_builder')
            module.write_depot_report_html = render
            with patch.dict(sys.modules, {'noark5_workflow.analysis.depot_report_builder': module}):
                destination = write_derived_depot_html(source)
            result = destination.read_text(encoding='utf-8')
            self.assertIn('Avledet depotrapport', result)
            self.assertIn('66 834', result)
            self.assertIn('&lt;source.txt&gt;', result)
            self.assertIn('abc123', result)
            self.assertEqual(native.read_text(encoding='utf-8'), 'UNCHANGED')

    def test_refuses_unmarked_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            path.write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError):
                write_derived_depot_html(path)


if __name__ == '__main__':
    unittest.main()
