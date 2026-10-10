import unittest
import tempfile
from pathlib import Path
import json
from noark5_workflow.external_evidence.evidence_html_a5 import render_evidence_html, write_evidence_html

class EvidenceHTMLTests(unittest.TestCase):
    def test_html_escaping_scope_and_thousands(self):
        project={'kind':'noark5_effective_evidence_projection','whole':{
          'folder_count':{'dwm_value':None,'effective_value':66834,'effective_source':'KDRS Query',
              'status':'external_evidence_selected','evidence':{'source_file':'a<b.txt','line':4}}},
          'archive_parts':{'1':{'archive_part':{'title':'A & B','system_id':'1234'},'metrics':{
              'folder_count':{'dwm_value':2,'effective_value':10,'effective_source':'DWM','status':'original_or_unknown'}}}}}
        html=render_evidence_html(project)
        self.assertIn('66 834',html)
        self.assertIn('a&lt;b.txt',html)
        self.assertIn('A &amp; B',html)
        self.assertNotIn('a<b.txt',html)
        self.assertIn('Arkivdel 1',html)
        self.assertIn('Ukjent',html)
    def test_source_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'depot-effective-evidence.json'
            f.write_text(json.dumps({'kind':'noark5_effective_evidence_projection','whole':{},'archive_parts':{}}))
            before=f.read_bytes()
            result=write_evidence_html(f)
            self.assertTrue(result.is_file())
            self.assertEqual(before,f.read_bytes())
    def test_invalid_project_rejected(self):
        with self.assertRaises(ValueError): render_evidence_html({})

if __name__=='__main__': unittest.main()
