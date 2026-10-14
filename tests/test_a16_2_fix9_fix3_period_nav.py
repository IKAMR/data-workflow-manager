import unittest
from types import SimpleNamespace
from unittest.mock import patch
from noark5_workflow.reporting import report_package_a16 as mod

class TestFix9Fix3(unittest.TestCase):
    def test_sticky_nav_only_html(self):
        page = mod._page('T', '<p>data</p>', ['index.html'])
        self.assertIn('position:sticky', page)
        self.assertIn('top:0', page)
        self.assertIn('@media print{nav{display:none}', page)
    def test_approved_period_remark(self):
        job = SimpleNamespace(job_id='JOB-019', progress=1.0, status='Ferdig')
        candidate={'declared_years':[1999,2099], 'observed_years':[1999,2099], 'proposed_years':[1999,2005]}
        with patch.object(mod, '_extraction_label', return_value='Møteserie'), patch.object(mod,'_archive_names',return_value='Møteserie'), patch.object(mod,'_review_status',return_value='Godkjent'), patch.object(mod,'review_candidate',return_value=candidate), patch.object(mod,'load_assessment',return_value={'x':'y'}), patch.object(mod,'reviewed_years',return_value=[1999,2005]):
            result=mod._overview_entry(job, {'summary':{}}, '')
        self.assertEqual(len(result),8)
        self.assertIn('2099: 1 observert sak', result[4])
        self.assertIn('faglig vurdert 1999–2005',result[4])
    def test_eight_column_pdf_smoke(self):
        headings=('Jobb','Uttrekk','Arkivdel(er)','Periodevurdering','Periodemerknad','Status','Fremdrift','Depotrapport')
        table=mod._table(headings,[('JOB-019','Møteserie','Møteserie','Godkjent','Oppgitt 1999–2099; faglig vurdert 1999–2005; 2099: 1 observert sak','Ferdig','100 %','Funnet')]).replace('<table>', '<table class="job-overview">',1)
        try:
            import reportlab, bs4
        except ImportError:
            self.skipTest('PDF-ekstrabiblioteker ikke installert')
        pdf=mod._pdf_bytes('<html><body>'+table+'</body></html>')
        self.assertTrue(pdf.startswith(b'%PDF-'))
