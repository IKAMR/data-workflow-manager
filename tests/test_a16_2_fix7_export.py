"""Regression tests for fix7 using unittest (the project test.bat runner)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_a16_2_fix5_report_package import _job
from noark5_workflow.reporting.report_package_a16 import write_report_package, safe_prefix
from noark5_workflow.reporting.job_summary_a16 import ReportOptions


class TestFix7ReportExport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_three_formats_same_folder_and_prefix(self):
        if not (importlib.util.find_spec('reportlab') and importlib.util.find_spec('bs4')):
            self.skipTest('PDF export dependencies reportlab/beautifulsoup4 not installed')
        output = self.root / 'chosen'
        output.mkdir()
        job = _job(self.root / 'job')
        path = write_report_package(output, [job], ReportOptions('Full', (), True, True),
                                    prefix='1502-ephorte', formats=('html', 'pdf', 'json'))
        self.assertEqual(path, output / '1502-ephorte_index.html')
        self.assertEqual(len(list(output.iterdir())), 15)
        html = path.read_text(encoding='utf-8')
        self.assertIn('href="1502-ephorte_vedlegg-a-uttrekk.html"', html)
        self.assertEqual((output / '1502-ephorte_index.pdf').read_bytes()[:5], b'%PDF-')
        payload = json.loads((output / '1502-ephorte_index.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['jobs'][0]['job_id'], 'JOB-019')
        self.assertEqual(payload['jobs'][0]['depot_report']['summary']['folder_count'], 3)
        self.assertIn('1999', html)

    def test_no_override_and_invalid_prefix(self):
        job = _job(self.root / 'job')
        out = self.root / 'chosen'
        out.mkdir()
        opts = ReportOptions('Full', (), False, False)
        write_report_package(out, [job], opts, prefix='z', formats=('html',))
        with self.assertRaises(FileExistsError):
            write_report_package(out, [job], opts, prefix='z', formats=('html',))
        write_report_package(out, [job], opts, prefix='z', formats=('html',), overwrite=True)
        self.assertEqual(safe_prefix('foo'), 'foo_')
        for value in ('../escape', 'bad\\path', 'bad:name'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    safe_prefix(value)

    def test_json_only(self):
        job = _job(self.root / 'job')
        out = self.root / 'chosen'
        path = write_report_package(out, [job], ReportOptions('Full', (), False, False),
                                    formats=('json',))
        self.assertEqual(path, out / 'index.json')
        self.assertEqual(list(out.glob('*.html')), [])


if __name__ == '__main__':
    unittest.main()
