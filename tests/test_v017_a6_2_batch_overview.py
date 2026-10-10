import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'noark5_batch_overview_a6.py'
spec=importlib.util.spec_from_file_location('a6_overview',MODULE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class BatchOverviewTests(unittest.TestCase):
    def test_missing_vs_zero(self):
        self.assertIsNone(mod.get_count(None))
        self.assertIsNone(mod.get_count({'status':'value_missing'}))
        self.assertEqual(mod.get_count(0),0)
    def test_native_report_and_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for job,num in [('JOB-001',2),('JOB-002',3)]:
                folder=root/'dwm'/'noark5_reports'/f'{job}__RUN-20261001'
                folder.mkdir(parents=True)
                (folder/'depot_validation_report.json').write_text(json.dumps({
                    'report_type':'noark5_depot_validation',
                    'summary':{'archive_part_count':1,'folder_count':num},
                    'archive_parts':[{'archive_part':{'title':'Del'},'folder_count':num}],
                    'technical_validation':{'status':'error'},
                    'deviations':[{'summary':'Testfeil','requires_review':True}],
                }))
            out=root/'out'
            self.assertEqual(mod.main(['--source',str(root/'dwm'),'--output',str(out),'--select','JOB-001']),0)
            data=json.loads((out/'noark5-uttrekksoversikt.json').read_text())
            self.assertEqual(len(data['items']),1)
            self.assertEqual(data['items'][0]['archive_parts'][0]['folder_count'],2)
            # Report remains explicit about evidence status without unrelated deletion disclaimer.
            html=(out/'noark5-uttrekksoversikt.html').read_text()
            self.assertIn('GO-vurdering',html)
            self.assertNotIn('før ekstern kildecontainer kan slettes',html)
    def test_selection_unknown_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(mod.main(['--source',tmp,'--output',str(root/'out'),'--select','JOB-999']),2)
            self.assertFalse((root/'out').exists())

if __name__=='__main__':unittest.main()
