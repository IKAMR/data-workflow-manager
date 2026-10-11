import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('report_a122', ROOT / 'tools' / 'noark5_batch_overview_a6.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class A122Tests(unittest.TestCase):
    def test_go_reason_summary(self):
        html = module.render_go_reasons([{'job':'JOB-002', 'extraction':'X/arkiv',
                       'go_assessment':{'status':'STOPP','reasons':['Mangelfull datadekning']}}])
        self.assertIn('STOPP', html)
        self.assertIn('Mangelfull datadekning', html)

    def test_only_arkade_provenance_keeps_provenance(self):
        text = ('<body><section class="page"><h2>JOB-002</h2>'
                '<h3>Kildesammenligning – mengdetall</h3>comparison'
                '<h4>Arkade 5 – kilde per import og måltall</h4>provenance'
                '<h3>Arkivdeler</h3>parts</section></body>')
        selected=module.filter_report_html(text,'standard',{'arkade_sources'})
        self.assertIn('provenance',selected)
        self.assertNotIn('comparison',selected)
        self.assertNotIn('parts',selected)
        selected=module.filter_report_html(text,'standard',{'sources'})
        self.assertIn('comparison',selected)
        self.assertNotIn('provenance',selected)

    def test_no_mutation(self):
        text='<body><section class="page"><h2>Job</h2><h3>Datadekning</h3>data</section></body>'
        self.assertEqual(module.filter_report_html(text,'detaljert',set(module.REPORT_SECTIONS)),text)

if __name__ == '__main__':
    unittest.main()
