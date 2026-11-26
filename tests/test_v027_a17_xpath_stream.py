"""a17: explicit contract tests for bounded XML selection and counts."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from lxml import etree

from noark5_workflow.analysis.a17_xpath_stream import (
    Selector, Metric, StreamPlan, UnsupportedStreamMetric,
)

XML = '''<noark5 xmlns="urn:test" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<arkiv><arkivdel><systemID>A</systemID><tittel>Del A</tittel>
<mappe xsi:type="saksmappe"><opprettetDato>2022-01-01</opprettetDato>
<mappe><opprettetDato>2023-03-04</opprettetDato></mappe>
<registrering xsi:type="journalpost"><journalstatus>J</journalstatus></registrering>
</mappe><mappe><opprettetDato>2020-01-01</opprettetDato></mappe>
</arkivdel><arkivdel><systemID>B</systemID><tittel>Del B</tittel>
<mappe xsi:type="moetemappe"><saksstatus>A</saksstatus><opprettetDato>2019-01-01</opprettetDato></mappe>
</arkivdel></arkiv></noark5>'''


class StreamSelectors(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.xml_path = Path(self.temp.name) / 'arkivstruktur.xml'
        self.xml_path.write_text(XML, encoding='utf-8')

    def plan(self, metrics, part_metrics=()):
        test = {'test_id':'kdrs.c99','source_xml':'arkivstruktur.xml',
                'execution':{'kind':'metrics','metrics':metrics,
                             'archive_part_metrics':list(part_metrics)}}
        plan = StreamPlan([test])
        self.assertNotIn('kdrs.c99',plan.unsupported)
        plan.scan(self.xml_path)
        return plan.results()['kdrs.c99']

    def test_global_and_part_counts_equal_lxml(self):
        specs = [
            {'id':'folders','type':'xpath','expression':'count(//mappe)'},
            {'id':'leaves','type':'xpath','expression':'count(//mappe[not(mappe or registrering)])'},
            {'id':'typed','type':'xpath','expression':'count(//mappe[@type="saksmappe"])'},
            {'id':'level','type':'xpath','expression':'count(//arkivdel//mappe)-count(//arkivdel//mappe/mappe)'},
            {'id':'statuses','type':'group_text','select':'//registrering/journalstatus'},
        ]
        parts = [{'id':'folders','type':'xpath','expression':'count(.//mappe)'}]
        actual = self.plan(specs,parts)
        tree = etree.parse(str(self.xml_path))
        root = tree.getroot()
        for n in root.iter():
            if isinstance(n.tag,str):
                n.tag = etree.QName(n).localname
                attrs = {etree.QName(k).localname:v for k,v in n.attrib.items()}
                n.attrib.clear();n.attrib.update(attrs)
        for spec in specs:
            if spec['type']=='xpath':
                self.assertEqual(actual[spec['id']],int(tree.xpath(spec['expression'])),spec['id'])
        self.assertEqual(actual['statuses'],{'J':1})
        self.assertEqual([p['values']['folders'] for p in actual['_archive_parts']],[3,1])
        self.assertEqual([p['archive_part']['system_id'] for p in actual['_archive_parts']],['A','B'])

    def test_year_and_range_with_part_isolation(self):
        specs = [{'id':'dates','type':'date_range','select':'//mappe/opprettetDato'},
                 {'id':'years','type':'year_counts','select':'//mappe/opprettetDato'},
                 {'id':'types','type':'group_attr','select':'//mappe','value':'@type'}]
        parts = [{'id':'dates','type':'date_range','select':'.//mappe/opprettetDato'}]
        actual = self.plan(specs,parts)
        self.assertEqual(actual['dates'],{'first':'2019-01-01','last':'2023-03-04'})
        self.assertEqual(actual['years'],{'2019':1,'2020':1,'2022':1,'2023':1})
        self.assertEqual(actual['types'],{'moetemappe':1,'saksmappe':1})
        self.assertEqual(actual['_archive_parts'][0]['values']['dates'],
                         {'first':'2020-01-01','last':'2023-03-04'})

    def test_document_parent_date_and_correspondence_parent(self):
        self.xml_path.write_text('''<r><arkivdel><systemID>A</systemID>
<dokumentbeskrivelse><dokumentobjekt/><dokumentobjekt/><opprettetDato>2024-01-01</opprettetDato></dokumentbeskrivelse>
<registrering><korrespondansepart/></registrering></arkivdel></r>''', encoding='utf-8')
        values = self.plan([
            {'id':'parents','type':'group_xpath','select':'//dokumentobjekt',
             'value':'string(ancestor::dokumentbeskrivelse[1]/opprettetDato)'},
            {'id':'years','type':'year_counts_by_node','select':'//dokumentobjekt',
             'value':'string(ancestor::dokumentbeskrivelse[1]/opprettetDato)'},
            {'id':'types','type':'group_xpath','select':'//korrespondansepart','value':'name(..)'},
        ])
        self.assertEqual(values['parents'],{'2024-01-01':2})
        self.assertEqual(values['years'],{'2024':2})
        self.assertEqual(values['types'],{'registrering':1})

    def test_per_part_special_is_not_falsely_rejected(self):
        spec = {'test_id':'kdrs.u02','source_xml':'arkivstruktur.xml',
                'execution':{'kind':'u2_archive_parts'}}
        plan = StreamPlan([spec])
        self.assertNotIn('kdrs.u02', plan.unsupported)
        plan.scan(self.xml_path)
        result = plan.results()['kdrs.u02']
        self.assertEqual(len(result['archive_parts']),2)
        self.assertEqual([x['values']['folder_count'] for x in result['archive_parts']],[3,1])

    def test_class_list_specials_use_completed_parent(self):
        self.xml_path.write_text("""<r><arkivdel><systemID>X</systemID>
<klasse><klasseID>010</klasseID><tittel>T</tittel><mappe/>
<registrering><systemID>R-1</systemID></registrering>
<klasse><klasseID>010.1</klasseID></klasse>
</klasse><klasse><klasseID>020</klasseID><tittel>Empty</tittel></klasse>
</arkivdel></r>""", encoding='utf-8')
        kinds = ('class_folder_list','empty_class_list',
                 'class_registration_list','class_registration_conflict_list')
        tests = [{'test_id':f'kdrs.x{i}','source_xml':'arkivstruktur.xml',
                  'execution':{'kind':kind}} for i,kind in enumerate(kinds)]
        plan = StreamPlan(tests)
        self.assertFalse(plan.unsupported)
        plan.scan(self.xml_path)
        values = plan.results()
        self.assertEqual(values['kdrs.x0']['classes'][0]['folder_count'],1)
        self.assertIn('Empty', [x['title'] for x in values['kdrs.x1']['classes']])
        self.assertEqual(values['kdrs.x2']['classes'][0]['registration_count'],1)
        self.assertEqual(values['kdrs.x3']['registrations'][0]['system_id'],'R-1')

    def test_double_attribute_child_predicate(self):
        values = self.plan([{'id':'with_flow','type':'xpath',
            'expression':'count(//registrering[@type="journalpost"][dokumentflyt])'}])
        self.assertEqual(values['with_flow'],0)

    def test_deferred_parent_checks(self):
        self.xml_path.write_text("""<r><arkivdel><klasse><klasseID>1</klasseID>
<klasse/><mappe/><mappe/></klasse>
<registrering><registreringsID>R1</registreringsID></registrering>
<registrering><dokumentbeskrivelse/></registrering>
<dokumentbeskrivelse><systemID>D1</systemID></dokumentbeskrivelse>
</arkivdel></r>""",encoding='utf-8')
        metrics = [
            {'id':'conflict','type':'xpath','expression':'count(//klasse[klasse]/mappe)'},
            {'id':'no_desc','type':'xpath',
             'expression':'count(//registrering[not(dokumentbeskrivelse)]/registreringsID)'},
            {'id':'no_obj_with_id','type':'xpath',
             'expression':'count(//dokumentbeskrivelse[not(dokumentobjekt)]/systemID/text())'},
        ]
        actual = self.plan(metrics)
        tree=etree.parse(str(self.xml_path))
        for spec in metrics:
            self.assertEqual(actual[spec['id']],int(tree.xpath(spec['expression'])),spec['id'])

    def test_refuses_ancestor_child_predicate(self):
        with self.assertRaises(UnsupportedStreamMetric):
            Selector('//klasse[klasse]/mappe')

    def test_no_implicit_success_for_unimplemented_special(self):
        plan = StreamPlan([{'test_id':'kdrs.bad','source_xml':'arkivstruktur.xml',
                            'execution':{'kind':'unknown_special'}}])
        self.assertIn('kdrs.bad',plan.unsupported)


if __name__ == '__main__':
    unittest.main()
