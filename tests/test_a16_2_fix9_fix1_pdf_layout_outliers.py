"""Regression for fixed job ID width and visible sparse boundary observations.

Uses unittest and the PDF dependencies installed by install.bat; no PDF reader required.
"""
import unittest
from bs4 import BeautifulSoup
from noark5_workflow.reporting.report_package_a16 import (
    STYLE, _yearly_chart, _pdf_bytes, _table,
)


class TestFix9Fix1(unittest.TestCase):
    def test_sparse_year_and_time_gap_visible(self):
        volume = {1999: {'folder': 168, 'document_description': 3796},
                  2005: {'folder': 105, 'document_description': 764},
                  2099: {'folder': 1}}
        html = _yearly_chart(volume, compact=True)
        self.assertIn('2099', html)
        self.assertIn('data-sparse="[2099]"', html)
        self.assertIn('>1</text>', html)
        self.assertIn('>//</text>', html)
        self.assertIn('"2099":[1,0,0,0]', BeautifulSoup(html, 'html.parser').div['data-yearly'])

    def test_pdf_overview_job_ids(self):
        cells = ('Jobb', 'Uttrekk', 'Arkivdel(er)', 'Periodevurdering',
                 'Status', 'Fremdrift', 'Depotrapport')
        table = _table(cells, [('JOB-001', 'uttrekk', 'arkivdel', 'Samsvar',
                                'Ferdig', '100 %', 'Funnet')]).replace(
                                    '<table>', '<table class="job-overview">', 1)
        self.assertIn('white-space:nowrap', STYLE)
        self.assertIn('min-width:82px', STYLE)
        self.assertIn('class="job-overview"', table)
        pdf = _pdf_bytes('<html><body><h1>Test</h1>' + table + '</body></html>')
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertGreater(len(pdf), 500)


if __name__ == '__main__':
    unittest.main()
