from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from noark5_workflow.analysis.xpath_test_engine import run_catalog

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'config/noark5/tests/xpath_catalog_2026_05_26.json'

class A20XpathCatalogTests(unittest.TestCase):
    def test_catalog_has_all_legacy_jobs(self):
        c=json.loads(CAT.read_text(encoding='utf-8'))
        ids={t['legacy']['job_id'] for t in c['tests']}
        expected={'C01','C02','C03','C05','C06','C07','C08','C09','C10','C11','C11.01','C12','C13','C14','C15','C16','C17','C18','C18.01','C19','C20','C21','C22','C23','C24','C25','F01','F02','F03','F04','F05','F06','F07','F08','F09','F10','F11','F12','F13','H01','H02','H03','H04','H05','H06','H07','I01','I02','J01','L02','U01','U02','C05.01_R3','C09_R4','C10_R5','C13.01','C15.01','C16_R6','C16.01_R7'}
        self.assertEqual(expected,ids)
        self.assertEqual(59,len(ids))

    def test_every_test_has_traceability_and_tags(self):
        c=json.loads(CAT.read_text(encoding='utf-8'))
        for t in c['tests']:
            self.assertTrue(t['test_id'])
            self.assertTrue(t['legacy']['job_id'])
            self.assertEqual('IKAMR/KDRS_Query:doc/xml-queries_noark5_2026-05-26.txt',t['legacy']['master_source'])
            self.assertIn('source_xml',t)
            self.assertIsInstance(t['tags'],list)
            self.assertIn('execution',t)

    def test_runner_writes_one_result_per_selected_normal_definition(self):
        xml='<arkiv><arkivdel><mappe/><registrering/></arkivdel></arkiv>'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'src'; out=Path(tmp)/'out'
            root.mkdir()
            (root/'arkivstruktur.xml').write_text(xml,encoding='utf-8')
            index=run_catalog(CAT,root,out,include_disabled=True,execution_profile='normal')
            c=json.loads(CAT.read_text(encoding='utf-8'))
            normal_selected=[
                t for t in c['tests']
                if t.get('lifecycle',{}).get('role') != 'development_regression_reference'
            ]
            self.assertEqual(len(normal_selected),len(index['tests']))
            self.assertEqual('normal',index['execution_profile'])
            self.assertEqual(
                {'kdrs.u01','kdrs.u02'},
                {item['test_id'] for item in index['excluded_tests']},
            )
            self.assertTrue((out/'definitions.json').is_file())
            self.assertTrue((out/'index.json').is_file())
            self.assertEqual(len(normal_selected),len(list((out/'results').glob('*.json'))))

    def test_runner_regression_profile_writes_all_definitions(self):
        xml='<arkiv><arkivdel><mappe/><registrering/></arkivdel></arkiv>'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'src'; out=Path(tmp)/'out'
            root.mkdir()
            (root/'arkivstruktur.xml').write_text(xml,encoding='utf-8')
            index=run_catalog(CAT,root,out,include_disabled=True,execution_profile='regression')
            c=json.loads(CAT.read_text(encoding='utf-8'))
            self.assertEqual(len(c['tests']),len(index['tests']))
            self.assertEqual('regression',index['execution_profile'])
            self.assertEqual([],index['excluded_tests'])
            self.assertEqual(len(c['tests']),len(list((out/'results').glob('*.json'))))

    def test_u1_u2_are_separate_scopes(self):
        c=json.loads(CAT.read_text(encoding='utf-8'))
        by={t['legacy']['job_id']:t for t in c['tests']}
        self.assertEqual('whole_extraction',by['U01']['scope'])
        self.assertEqual('archive_part',by['U02']['scope'])

    def test_xpath_operation_is_registered_exactly_once(self):
        from noark5_workflow.profile import NOARK5_PROFILE
        operation_ids = [
            factory().definition.operation_id
            for factory in NOARK5_PROFILE.operation_factories
        ]
        self.assertEqual(
            1,
            operation_ids.count("run_noark5_xpath_tests_2026"),
        )

if __name__=='__main__': unittest.main()
