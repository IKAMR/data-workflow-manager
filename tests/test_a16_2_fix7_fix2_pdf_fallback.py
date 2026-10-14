import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_a16_2_fix5_report_package import _job
from noark5_workflow.reporting.job_summary_a16 import ReportOptions
from noark5_workflow.reporting.report_package_a16 import write_report_package

class TestPdfFallback(unittest.TestCase):
    def test_html_json_continue_when_pdf_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            job=_job(root/'job')
            warnings=[]
            with patch('noark5_workflow.reporting.report_package_a16._pdf_bytes', side_effect=RuntimeError('missing PDF libraries')):
                result=write_report_package(root/'out',[job],ReportOptions('Full',(),True,True),
                    formats=('html','pdf','json'),on_warning=warnings.append)
            self.assertTrue(result.exists())
            self.assertEqual(len(list((root/'out').glob('*.html'))), 5)
            self.assertEqual(len(list((root/'out').glob('*.json'))), 5)
            self.assertEqual(len(list((root/'out').glob('*.pdf'))), 0)
            self.assertEqual(len(warnings),1)
            self.assertIn('missing PDF libraries',warnings[0])
    def test_pdf_only_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch('noark5_workflow.reporting.report_package_a16._pdf_bytes', side_effect=RuntimeError('missing PDF libraries')):
                with self.assertRaisesRegex(RuntimeError,'PDF-eksport feilet'):
                    write_report_package(root/'out',[_job(root/'job')],ReportOptions('Full',(),False,False),formats=('pdf',))
            self.assertFalse((root/'out').exists())

if __name__=='__main__':
    unittest.main()
