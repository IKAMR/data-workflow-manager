from pathlib import Path
import ast
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# Run standalone delta tests without the whole repository checked out.
import types
fake_arkade = types.ModuleType('noark5_workflow.external_evidence.arkade5')
fake_arkade.list_arkade5_imports = lambda path: []
fake_arkade.load_arkade5_import = lambda work,import_id: {}
fake_pronom = types.ModuleType('noark5_workflow.external_evidence.arkade5_pronom')
fake_pronom.load_arkade5_pronom_statistics = lambda work,manifest: None
fake_pronom.summarize_arkade5_pronom_statistics = lambda normalized,manifest=None: {'available': False}
if not (ROOT/'noark5_workflow/external_evidence/arkade5.py').exists():
    sys.modules[fake_arkade.__name__] = fake_arkade
    sys.modules[fake_pronom.__name__] = fake_pronom
from noark5_workflow.external_evidence.arkade5_gui_data_a18 import build_arkade5_gui_snapshot

class ArkadeGuiEvidenceTests(unittest.TestCase):
    def test_no_import_returns_empty_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=build_arkade5_gui_snapshot(tmp)
        self.assertEqual(data['import_count'],0)
        self.assertEqual(data['pronom_imports'],0)

    def test_snapshot_includes_test_details_pronom_and_source(self):
        manifests=[{'import_id':'im-1','imported_at':'2026-10-14','source':{'original_name':'a.json','sha256':'abc'}}]
        normalized={'source_version':'2.13.1','summary':{'date_of_testing':'2026-10-14'}, 'tests':[
          {'test_id':'N5.47','test_name':'Kontroll','source_status':'error','number_of_errors':2,'results':[{'message':'Avvik A'}]},
          {'test_id':'N5.18','test_name':'Datoer','source_status':'ok','number_of_errors':0}]}
        pronom={'available':True,'statistics':{'total_files':17,'unidentified_files':1,'row_count':2,'rows':[]}}
        with patch('noark5_workflow.external_evidence.arkade5_gui_data_a18.list_arkade5_imports',return_value=manifests),\
             patch('noark5_workflow.external_evidence.arkade5_gui_data_a18.load_arkade5_import',return_value={'normalized':normalized}),\
             patch('noark5_workflow.external_evidence.arkade5_gui_data_a18.load_arkade5_pronom_statistics',return_value={'csv':{}}),\
             patch('noark5_workflow.external_evidence.arkade5_gui_data_a18.summarize_arkade5_pronom_statistics',return_value=pronom):
            result=build_arkade5_gui_snapshot('/tmp/work')
        self.assertEqual(result['readable_imports'],1)
        self.assertEqual(result['pronom_imports'],1)
        row=result['runs'][0]
        self.assertEqual(row['source_sha256'],'abc')
        self.assertEqual(row['source_version'],'2.13.1')
        self.assertEqual(row['tests'][0]['details']['results'][0]['message'],'Avvik A')

    def test_unreadable_import_is_visible_not_silently_lost(self):
        with patch('noark5_workflow.external_evidence.arkade5_gui_data_a18.list_arkade5_imports',return_value=[{'import_id':'bad'}]),\
             patch('noark5_workflow.external_evidence.arkade5_gui_data_a18.load_arkade5_import',side_effect=ValueError('Ugyldig data')):
            result=build_arkade5_gui_snapshot('/tmp/work')
        self.assertEqual(result['import_count'],1)
        self.assertEqual(result['readable_imports'],0)
        self.assertIn('Ugyldig',result['runs'][0]['diagnostic'])

    def test_result_center_preserves_kdrs_and_adds_arkade_controls(self):
        source=(ROOT/'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn('tabs.add("Eksterne kilder")', source)
        self.assertIn('text="Vis KDRS Query-resultater"', source)
        self.assertIn('text="Vis Arkade 5-tester"', source)
        self.assertIn('text="Vis PRONOM"', source)
        self.assertIn('open_arkade5_sources(', source)

    def test_issue_filter_keeps_real_arkade_failures(self):
        source=(ROOT/'gui/arkade5_external_sources_a18.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_test_rows')
        ns={}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'viewer','exec'),ns)
        run={'tests':[
            {'test_id':'N5.47','test_name':'feil','status':'error','errors':2},
            {'test_id':'N5.29','test_name':'advarsel','status':'warning','errors':0},
            {'test_id':'N5.18','test_name':'OK','status':'ok','errors':0}]}
        self.assertEqual([x['test_id'] for x in ns['_test_rows'](run,only_issues=True)],
                         ['N5.47','N5.29'])
        self.assertEqual([x['test_id'] for x in ns['_test_rows'](run,search='N5.18')],
                         ['N5.18'])

    def test_source_and_gui_are_read_only(self):
        source=(ROOT/'gui/arkade5_external_sources_a18.py').read_text(encoding='utf-8')
        self.assertIn('open_arkade5_sources',source)
        self.assertNotIn('import_arkade5_report(',source)
        self.assertNotIn('write_arkade5',source)

if __name__=='__main__':unittest.main()
