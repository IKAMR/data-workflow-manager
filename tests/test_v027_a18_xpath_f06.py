"""a18: F06's two deferred string-length XPath counts match lxml exactly."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from lxml import etree

from noark5_workflow.analysis.a17_xpath_stream import StreamPlan


EXPRS = {
    'method': 'count(//registrering[@type="journalpost"]/avskrivning[string-length(avskrivningsmaate)>0]/avskrivningsmaate)',
    'reference': 'count(//registrering[@type="journalpost"]/avskrivning[string-length(referanseAvskrivesAvJournalpost)>0]/referanseAvskrivesAvJournalpost)',
}
XML = '''<r xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><arkivdel>
<registrering xsi:type="journalpost"><avskrivning><avskrivningsmaate>A</avskrivningsmaate><referanseAvskrivesAvJournalpost>R</referanseAvskrivesAvJournalpost></avskrivning>
<avskrivning><avskrivningsmaate></avskrivningsmaate><referanseAvskrivesAvJournalpost/></avskrivning>
<avskrivning><avskrivningsmaate> </avskrivningsmaate></avskrivning>
<avskrivning><referanseAvskrivesAvJournalpost>ref</referanseAvskrivesAvJournalpost></avskrivning></registrering>
<registrering xsi:type="arkivnotat"><avskrivning><avskrivningsmaate>IGNORED</avskrivningsmaate></avskrivning></registrering>
</arkivdel><arkivdel><registrering xsi:type="journalpost"><avskrivning><avskrivningsmaate>B</avskrivningsmaate></avskrivning></registrering></arkivdel></r>'''

class TestF06(unittest.TestCase):
    def test_exact_xpath_values_whole_and_separate_archive_parts(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'arkivstruktur.xml'
            source.write_text(XML, encoding='utf-8')
            metrics = [{'id': k, 'type': 'xpath', 'expression': e} for k,e in EXPRS.items()]
            test = {'test_id': 'kdrs.f06', 'source_xml':'arkivstruktur.xml',
                    'execution':{'kind':'metrics','metrics':metrics}}
            plan = StreamPlan([test])
            self.assertEqual(plan.unsupported, {})
            plan.scan(source)
            values = plan.results()['kdrs.f06']
            tree = etree.parse(str(source))
            for node in tree.iter():
                if isinstance(node.tag, str):
                    attrs = {etree.QName(k).localname: v for k,v in node.attrib.items()}
                    node.attrib.clear()
                    node.attrib.update(attrs)
            for key, expression in EXPRS.items():
                self.assertEqual(values[key],int(tree.xpath(expression)),key)
            self.assertEqual(values['method'],3)
            self.assertEqual(values['reference'],2)

    def test_catalog_f06_is_accepted(self):
        import json
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads((root/'config/noark5/tests/xpath_catalog_2026_05_26.json').read_text(encoding='utf-8'))
        test = next(test for test in catalog['tests'] if test['test_id']=='kdrs.f06')
        self.assertNotIn('kdrs.f06', StreamPlan([test]).unsupported)

if __name__=='__main__':
    unittest.main()
