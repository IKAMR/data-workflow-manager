"""a10: existing output inventory; never traverse Noark 5 content."""
import ast
import json
import tempfile
import unittest
from pathlib import Path
from gui.noark5_overview_evidence_a10 import extraction_root, evidence_status, report_candidates


class ControlInventoryTests(unittest.TestCase):
    def test_run_subfolder_and_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'extraction'
            base = root / 'repository_operations' / 'dwm' / 'a01'
            report = base / 'noark5_reports' / 'depot_validation' / 'JOB-001__RUN-20261004' / 'depot_validation_report.json'
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({'technical_validation': {'status': 'ok'}}), encoding='utf8')
            ark = base / 'external_evidence' / 'arkade5' / 'some-import' / 'normalized' / 'arkade5_results.json'
            ark.parent.mkdir(parents=True)
            ark.write_text('{}', encoding='utf8')
            (report.parent / 'depot-effective-evidence.json').write_text('{}', encoding='utf8')
            self.assertEqual(extraction_root(root / 'content' / 'sip' / 'content'), root)
            self.assertEqual(report_candidates(root, 'JOB-001'), [report])
            status = evidence_status(root, 'JOB-001')
            self.assertEqual((status['depot'], status['arkade'], status['kdrs']),
                             ('Funnet', 'Importert', 'Evidensfil'))
            self.assertEqual(status['technical'], 'ok')
            self.assertFalse(report_candidates(root, 'JOB-002'))

    def test_no_content_scan_or_false_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'extraction'
            fake = root / 'content' / 'sip' / 'content' / 'repository_operations' / 'dwm' / 'a01' / 'noark5_reports' / 'depot_validation' / 'JOB-001__RUN-x' / 'depot_validation_report.json'
            fake.parent.mkdir(parents=True)
            fake.write_text('{}', encoding='utf8')
            self.assertEqual(report_candidates(root), [])
            self.assertEqual(evidence_status(root)['depot'], 'Mangler')

    def test_gui_has_columns_and_keeps_manual_search(self):
        source = (Path(__file__).resolve().parents[1] / 'gui' / 'noark5_multi_overview_a65.py').read_text(encoding='utf8')
        ast.parse(source)
        for marker in ('Depotrapport', 'Arkade 5', 'KDRS Query', 'command=self._search_folders', 'self._load_joblist()'):
            self.assertIn(marker, source)

if __name__ == '__main__':
    unittest.main()
