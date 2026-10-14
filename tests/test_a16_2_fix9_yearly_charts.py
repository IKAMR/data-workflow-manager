"""Report graphics must reuse archive part yearly volumes; unittest compatible."""
import json
import tempfile
import unittest
from pathlib import Path
from test_a16_2_fix5_report_package import _job
from noark5_workflow.reporting.job_summary_a16 import ReportOptions
from noark5_workflow.reporting.report_package_a16 import write_report_package, _pdf_bytes


class TestYearlyCharts(unittest.TestCase):
    def test_all_report_parts_and_pdf(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            job=_job(root/'source')
            report=next((root/'source').rglob('depot_validation_report.json'))
            payload=json.loads(report.read_text(encoding='utf-8'))
            payload['archive_parts'][0]['yearly_volume']={
                'folder':{'1999':168,'2005':105,'2099':1},
                'journal':{},'document_description':{'1999':3796,'2005':764},
                'document_object':{'1999':2302,'2005':410}}
            report.write_text(json.dumps(payload),encoding='utf-8')
            dest=root/'out'
            write_report_package(dest,[job],ReportOptions('Medium',(),True,True),formats=('html','json','pdf'))
            for fname in ('index.html','vedlegg-a-uttrekk.html','vedlegg-b-arkivdeler.html'):
                html=(dest/fname).read_text(encoding='utf-8')
                self.assertIn('data-yearly=',html)
                self.assertIn('<svg ',html)
                self.assertIn('2099',html)
                self.assertTrue((dest/fname.replace('.html','.pdf')).read_bytes().startswith(b'%PDF-'))
            part=(dest/'vedlegg-b-arkivdeler.html').read_text(encoding='utf-8')
            self.assertIn('3796',part)
            self.assertIn('1',part)
            self.assertIn('Møteserie',part)
            self.assertIn('yearly_volume', (dest/'index.json').read_text(encoding='utf-8'))

    def test_no_year_data_no_invented_values(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            write_report_package(root/'out',[_job(root/'source')],ReportOptions('Medium',(),True,True))
            self.assertIn('Ingen årsfordeling', (root/'out/index.html').read_text(encoding='utf-8'))

if __name__=='__main__': unittest.main()
