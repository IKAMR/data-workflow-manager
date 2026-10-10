"""Multiple job roots from an existing .n5jobs; never search SIP payload."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import types

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'noark5_batch_overview_a6.py'
spec = importlib.util.spec_from_file_location('a8_jobs_report', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ActiveJobListReport(unittest.TestCase):
    def test_joblist_across_roots_and_missing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs=[]
            for i in range(1,4):
                source=root/f'kommune{i}'/f'uttak{i}'
                source.mkdir(parents=True)
                jobs.append({'job_id':f'JOB-{i:03d}','name':'sip',
                             'source_root':str(source),'work_operations':str(source/'repository_operations')})
                if i == 2:
                    continue
                p=source/'repository_operations'/'dwm'/'a01'/'noark5_reports'/'depot_validation'/f'JOB-{i:03d}__RUN-1'
                p.mkdir(parents=True)
                (p/'depot_validation_report.json').write_text(json.dumps({
                    'report_type':'noark5_depot_validation','summary':{'archive_part_count':1,'folder_count':i},
                    'archive_parts':[{'archive_part':{'title':'T'},'folder_count':i}],
                    'technical_validation':{'status':'ok'},'deviations':[]}),encoding='utf-8')
            joblist=root/'jobs.n5jobs'
            joblist.write_text(json.dumps({'jobs':jobs,'output_subfolder_rule':'a01'}),encoding='utf-8')
            fake=types.ModuleType('report_outputs')
            fake.html_to_pdf=lambda h,p:Path(p).write_bytes(b'%PDF stub')
            with patch.dict(sys.modules,{'tools.report_outputs':fake,'report_outputs':fake}):
                result=mod.main(['--source',str(root),'--output',str(root/'out'),
                                 '--joblist',str(joblist),'--select','JOB-001','JOB-002','JOB-003'])
            self.assertEqual(result,0)
            data=json.loads((root/'out'/'noark5-uttrekksoversikt.json').read_text(encoding='utf-8'))
            self.assertEqual(len(data['items']),2)
            self.assertEqual(len(data['missing_jobs']),1)
            self.assertEqual(data['missing_jobs'][0]['job'],'JOB-002')
            html=(root/'out'/'noark5-uttrekksoversikt.html').read_text(encoding='utf-8')
            self.assertIn('Jobber uten depotrapport',html)
            self.assertNotIn('før ekstern kildecontainer kan slettes',html)
