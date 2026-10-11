import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'tools' / 'noark5_batch_overview_a6.py'
spec = importlib.util.spec_from_file_location('a11_overview', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class A11ReportPrefixTests(unittest.TestCase):
    def test_gui_parses_and_passes_prefix(self):
        code=(ROOT / 'gui' / 'noark5_multi_overview_a65.py').read_text(encoding='utf-8')
        ast.parse(code)
        self.assertIn("'--prefix', prefix",code)
        self.assertIn("'report_prefix':self._prefix.get().strip()",code)
        self.assertIn('askyesno',code)

    def test_prefix_and_default_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            report=base/'dwm'/'noark5_reports'/'JOB-001__RUN-20261001'/'depot_validation_report.json'
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({'report_type':'noark5_depot_validation',
                'summary':{'archive_part_count':1,'folder_count':2},
                'archive_parts':[{'archive_part':{'title':'Del'},'folder_count':2}],
                'technical_validation':{'status':'error'},
                'deviations':[{'summary':'Testfeil','requires_review':True}]}))
            fake=types.ModuleType('report_outputs')
            fake.html_to_pdf=lambda *args: (_ for _ in ()).throw(OSError('simulert PDF-feil'))
            with patch.dict('sys.modules', {'tools.report_outputs':fake,'report_outputs':fake}):
                # PDF fails harmlessly if no converter; inspect three core outputs.
                self.assertEqual(mod.main(['--source',str(base/'dwm'),'--output',str(base/'out'),
                                           '--prefix','runde_01','--select','JOB-001']),0)
                for ext in ('html','json','csv'):
                    self.assertTrue((base/'out'/('runde_01_noark5-uttrekksoversikt.'+ext)).exists())
                self.assertEqual(mod.main(['--source',str(base/'dwm'),'--output',str(base/'out'),
                                           '--select','JOB-001']),0)
                for ext in ('html','json','csv'):
                    self.assertTrue((base/'out'/('noark5-uttrekksoversikt.'+ext)).exists())

    def test_invalid_prefix_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(mod.main(['--source',tmp,'--output',str(root/'out'),'--prefix','../foo']),2)
            self.assertFalse((root/'out').exists())

if __name__ == '__main__':
    unittest.main()
