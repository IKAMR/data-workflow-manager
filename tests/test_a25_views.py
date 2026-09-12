import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis.view_composer import compose_views, write_composed_views

ROOT=Path(__file__).parents[1]

class A25ViewTests(unittest.TestCase):
    def test_profile_declares_canonical_views(self):
        profile=json.loads((ROOT/'config/noark5/profile.json').read_text(encoding='utf-8'))
        self.assertEqual(profile['definitions']['views'], ['config/noark5/views/canonical_views.json'])
        self.assertTrue(profile['capabilities']['result_composition'])

    def test_view_definitions_have_no_xpath_expressions(self):
        data=json.loads((ROOT/'config/noark5/views/canonical_views.json').read_text(encoding='utf-8'))
        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertNotIn(key.lower(), {'xpath', 'expression', 'select'})
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(data)

    def test_composer_uses_canonical_results(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); results=root/'results'; results.mkdir()
            index={'execution_profile':'normal','summary':{'ok':2},'tests':[
                {'test_id':'kdrs.c01','legacy_job_id':'C01','test_point':'N5.01','status':'ok'},
                {'test_id':'kdrs.c02','legacy_job_id':'C02','test_point':'N5.02','status':'ok'},
            ]}
            (root/'index.json').write_text(json.dumps(index),encoding='utf-8')
            (results/'kdrs_c01.json').write_text(json.dumps({'values':{'archive_count':1}}),encoding='utf-8')
            (results/'kdrs_c02.json').write_text(json.dumps({'values':{
                'archive_part_records':[{'system_id':'A','title':'Del A'}],
                '_archive_parts':[{'archive_part':{'system_id':'A'},'values':{'folder_count':4}}],
                '_reconciliation_summary':{'status':'match'},
            }}),encoding='utf-8')
            definition={'definition_id':'x','input':{'required_execution_profile':'normal'},'views':[
                {'id':'whole','scope':'whole_extraction','sections':[{'id':'x','fields':[{'id':'archives','source':{'test_id':'kdrs.c01','path':'archive_count'}}]}]},
                {'id':'parts','scope':'archive_part','identity_source':{'test_id':'kdrs.c02','path':'archive_part_records','identity_key':'system_id'},'sections':[{'id':'x','fields':[{'id':'folders','source':{'test_id':'kdrs.c02','path':'folder_count'}}]}]},
                {'id':'validation','scope':'result_set','mode':'validation_evidence'}
            ]}
            composed=compose_views(root,definition)
            self.assertEqual(composed['views'][0]['sections'][0]['fields'][0]['value'],1)
            self.assertEqual(composed['views'][1]['archive_parts'][0]['sections'][0]['fields'][0]['value'],4)
            self.assertEqual(composed['views'][2]['execution_profile'],'normal')

    def test_composer_rejects_regression_as_production_view_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'results').mkdir()
            (root/'index.json').write_text(json.dumps({'execution_profile':'regression','tests':[]}),encoding='utf-8')
            with self.assertRaises(ValueError):
                compose_views(root,{'input':{'required_execution_profile':'normal'},'views':[]})

if __name__=='__main__': unittest.main()
