"""Yearly registration data must not be invented from journalpost counts."""
import unittest
from bs4 import BeautifulSoup
from noark5_workflow.reporting.yearly_volume_a16 import registration_years
from noark5_workflow.reporting.report_package_a16 import _yearly_chart, _yearly_section


class TestFix9Fix5RegistrationYears(unittest.TestCase):
    def test_missing_is_unknown_not_zero(self):
        report={'archive_parts':[{'archive_part':{'system_id':'a'},'yearly_volume':{'folder':{'2099':1},'journal':{}}}]}
        self.assertIsNone(registration_years(report))
        self.assertIn('ikke lagret',_yearly_section(None,report))
        self.assertIn('"2099":[1,0,0,0]',BeautifulSoup(_yearly_chart({2099:{'folder':1}}),'html.parser').div['data-yearly'])

    def test_independent_registration_series_and_pdf(self):
        report={'archive_parts':[{'archive_part':{'system_id':'a'},'yearly_volume':{'folder':{'2099':1},'registration':{'2099':46}}}]}
        self.assertEqual(registration_years(report),{2099:46})
        html=_yearly_section(None,report)
        self.assertIn('Registr.',html)
        self.assertIn('>46</td>',html)
        self.assertIn('"2099":[1,0,0,0,46]',BeautifulSoup(html,'html.parser').div['data-yearly'])
        from noark5_workflow.reporting.report_package_a16 import _pdf_bytes
        self.assertTrue(_pdf_bytes('<html><body>'+html+'</body></html>').startswith(b'%PDF-'))

    def test_incomplete_multiarc_part_is_unknown(self):
        report={'archive_parts':[{'archive_part':{'system_id':'a'},'yearly_volume':{'registration':{'2099':46}}},
                                 {'archive_part':{'system_id':'b'},'yearly_volume':{'journal':{'2099':2}}}]}
        self.assertIsNone(registration_years(report))
        self.assertEqual(registration_years(report,archive_part_id='a'),{2099:46})

if __name__=='__main__':unittest.main()
