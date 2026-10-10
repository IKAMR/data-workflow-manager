"""a8: HTML/JSON/CSV survive a PDF conversion failure."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'tools' / 'noark5_batch_overview_a6.py'
spec = importlib.util.spec_from_file_location('a8_batch', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class A8Exports(unittest.TestCase):
    def test_three_formats_survive_pdf_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / 'dwm' / 'noark5_reports' / 'depot_validation' / 'JOB-001__RUN-20261001'
            src.mkdir(parents=True)
            (src / 'depot_validation_report.json').write_text(json.dumps({
                'report_type': 'noark5_depot_validation',
                'summary': {'archive_part_count': 1, 'folder_count': 2},
                'archive_parts': [{'archive_part': {'title': 'Test'}, 'folder_count': 2}],
                'technical_validation': {'status': 'ok'}, 'deviations': [],
            }), encoding='utf-8')
            output = root / 'out'
            output.mkdir()
            (output / 'noark5-uttrekksoversikt.pdf').write_bytes(b'old-pdf')
            fake = types.ModuleType('report_outputs')
            def fail_pdf(*args):
                raise RuntimeError('PDF-konvertering utilgjengelig')
            fake.html_to_pdf = fail_pdf
            with patch.dict(sys.modules, {'tools.report_outputs': fake, 'report_outputs': fake}):
                result = mod.main(['--source', str(root / 'dwm'), '--output', str(output)])
            self.assertEqual(result, 0)
            for ext in ('html', 'json', 'csv'):
                self.assertTrue((output / ('noark5-uttrekksoversikt.' + ext)).is_file())
            self.assertFalse((output / 'noark5-uttrekksoversikt.pdf').exists())
            data = json.loads((output / 'noark5-uttrekksoversikt.json').read_text('utf-8'))
            self.assertEqual(len(data['items']), 1)
            self.assertNotIn('før ekstern kildecontainer kan slettes', (output / 'noark5-uttrekksoversikt.html').read_text('utf-8'))


if __name__ == '__main__':
    unittest.main()

class A8SixJobs(unittest.TestCase):
    def test_six_jobs_four_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(1, 7):
                report_dir = (root / f'1502_{22+i:03d}' / 'repository_operations' /
                              'dwm' / 'noark5_reports' / 'depot_validation' /
                              f'JOB-{i:03d}__RUN-20261001')
                report_dir.mkdir(parents=True)
                (report_dir / 'depot_validation_report.json').write_text(json.dumps({
                    'report_type': 'noark5_depot_validation',
                    'summary': {'archive_part_count': 1, 'folder_count': i},
                    'archive_parts': [{'archive_part': {'title': f'Arkivdel {i}'}, 'folder_count': i}],
                    'technical_validation': {'status': 'ok'}, 'deviations': [],
                }), encoding='utf-8')
            fake = types.ModuleType('report_outputs')
            def pdf_ok(html, pdf):
                Path(pdf).write_bytes(b'%PDF test stub')
                return Path(pdf)
            fake.html_to_pdf = pdf_ok
            output = root / 'result'
            with patch.dict(sys.modules, {'tools.report_outputs': fake, 'report_outputs': fake}):
                result = mod.main(['--source', str(root), '--output', str(output)])
            self.assertEqual(result, 0)
            self.assertEqual(len(json.loads((output / 'noark5-uttrekksoversikt.json').read_text('utf-8'))['items']), 6)
            for ext in ('html', 'json', 'csv', 'pdf'):
                self.assertTrue((output / ('noark5-uttrekksoversikt.' + ext)).exists(), ext)
