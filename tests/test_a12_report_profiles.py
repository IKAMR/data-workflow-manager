import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('overview_a12', ROOT/'tools'/'noark5_batch_overview_a6.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ReportProfileTests(unittest.TestCase):
    def test_profile_defaults(self):
        self.assertEqual(mod.selected_report_sections('oversikt'),set())
        self.assertIn('archive_parts',mod.selected_report_sections('standard'))
        self.assertNotIn('pronom',mod.selected_report_sections('standard'))
        self.assertEqual(mod.selected_report_sections('detaljert'),set(mod.REPORT_SECTIONS))
    def test_user_choice_overrides_profile(self):
        self.assertEqual(mod.selected_report_sections('standard',['pronom']),{'pronom'})
        self.assertEqual(mod.selected_report_sections('standard',[]),set())
        with self.assertRaises(ValueError): mod.selected_report_sections('standard',['unknown'])
    def test_html_filter_no_data_mutation(self):
        text='<body><section class="page"><h2>JOB-001</h2><h3>Datadekning</h3>coverage<h3>Arkivdeler</h3>parts<h3>PRONOM – importert filformatstatistikk</h3>formats</section></body>'
        filtered=mod.filter_report_html(text,'standard',{'coverage','archive_parts'})
        self.assertIn('coverage',filtered)
        self.assertIn('parts',filtered)
        self.assertNotIn('formats',filtered)
        brief=mod.filter_report_html(text,'oversikt',set())
        self.assertNotIn('JOB-001',brief)
        self.assertEqual(mod.filter_report_html(text,'detaljert',mod.selected_report_sections('detaljert')),text)

if __name__=='__main__':unittest.main()
