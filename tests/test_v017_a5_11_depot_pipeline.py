from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.external_evidence.depot_report_pipeline_a5 import write_depot_evidence_outputs


class DepotPipelineEvidenceTests(unittest.TestCase):
    def test_no_external_import_preserves_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / 'depot_validation_report.json'
            report.write_text('{"original":true}', encoding='utf-8')
            before = report.read_bytes()
            value = write_depot_evidence_outputs(report, root)
            self.assertEqual(value['status'], 'not_available')
            self.assertEqual(report.read_bytes(), before)
            self.assertEqual(list(root.glob('depot-*')), [])

    def test_pipeline_reuses_existing_companions_without_mutating_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'external_evidence' / 'kdrs_query').mkdir(parents=True)
            report = root / 'depot_validation_report.json'
            report.write_text('{"original":true}', encoding='utf-8')
            def output(name):
                path = report.with_name(name)
                path.write_text('{}', encoding='utf-8')
                return path
            module = 'noark5_workflow.external_evidence'
            with patch(f'{module}.evidence_report_bridge_a5.write_depot_evidence_companion', side_effect=lambda *_: output('depot-external-evidence.json')) as companion, \
                 patch(f'{module}.evidence_projection_a5.write_effective_projection', side_effect=lambda *_: output('depot-effective-evidence.json')) as projection, \
                 patch(f'{module}.effective_depot_report_a5.write_derived_depot_report', side_effect=lambda *_: output('depot-derived-evidence-report.json')) as derived, \
                 patch(f'{module}.evidence_html_a5.write_evidence_html', side_effect=lambda *_: output('depot-evidence-report.html')) as html, \
                 patch(f'{module}.derived_depot_html_a5.write_derived_depot_html', side_effect=lambda *_: output('depot-derived-evidence-report.html')) as derived_html:
                result = write_depot_evidence_outputs(report, root)
            self.assertEqual(result['status'], 'generated')
            self.assertEqual(report.read_text(encoding='utf-8'), '{"original":true}')
            for mock in (companion, projection, derived, html, derived_html):
                self.assertEqual(mock.call_count, 1)

    def test_operation_integrates_and_reports_external_failure(self):
        src = Path(__file__).resolve().parents[1] / 'noark5_workflow' / 'operations' / 'build_noark5_depot_report.py'
        source = src.read_text(encoding='utf-8')
        self.assertIn('write_depot_evidence_outputs(model_file, work)', source)
        self.assertIn('"external_evidence": external', source)
        self.assertIn('"status": "error"', source)
        self.assertLess(source.index('inject_arkade5_html(html_file, model)'), source.index('write_depot_evidence_outputs(model_file, work)'))


if __name__ == '__main__':
    unittest.main()
