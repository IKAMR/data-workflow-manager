import unittest
import tempfile
import json
from pathlib import Path
from noark5_workflow.external_evidence.evidence_projection_a5 import effective_projection,write_effective_projection

class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.native = {'report_type':'noark5_depot_validation',
          'summary':{'folder_count':None,'registration_count':0},
          'archive_parts':[{'archive_part':{'title':'A'},'folder_count':3},
                           {'archive_part':{'title':'B'},'folder_count':None}]}
    def test_scope_and_unknown_and_zero(self):
        annex={'records':[{'scope_key':'whole:folder_count','status':'external_evidence_selected','effective_source':'KDRS Query','effective_value':100,'evidence':{'source_file':'u1.txt'}},
          {'scope_key':'part:2:folder_count','status':'scope_review_required','scope_review':'archive_part_title_mismatch','effective_source':'KDRS Query','effective_value':4,'evidence':{'source_file':'u2.txt'}},
          {'scope_key':'part:1:folder_count','status':'external_evidence_selected','effective_source':'KDRS Query','effective_value':15,'evidence':{'source_file':'u2.txt'}}]}
        result=effective_projection(self.native,annex)
        self.assertEqual(result['whole']['folder_count']['effective_value'],100)
        self.assertEqual(result['whole']['registration_count']['effective_value'],0)
        self.assertEqual(result['archive_parts']['1']['metrics']['folder_count']['effective_value'],15)
        self.assertIsNone(result['archive_parts']['2']['metrics']['folder_count']['effective_value'])
        self.assertEqual(self.native['archive_parts'][0]['folder_count'],3)
    def test_invalid_and_duplicate_scope_not_applied(self):
        rows=[{'scope_key':'part:100:folder_count','status':'external_evidence_selected','effective_source':'KDRS Query','effective_value':999,'evidence':{}},
              {'scope_key':'whole:folder_count','status':'external_evidence_selected','effective_source':'KDRS Query','effective_value':True,'evidence':{}},
              {'scope_key':'whole:folder_count','status':'external_evidence_selected','effective_source':'KDRS Query','effective_value':12,'evidence':{}}]
        result=effective_projection(self.native,{'records':rows})
        self.assertIsNone(result['whole']['folder_count']['effective_value'])
        self.assertNotIn('100', result['archive_parts'])
    def test_files_and_hash_and_non_destructive(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); report=base/'depot.json'; annex=base/'depot-external-evidence.json'
            report.write_text(json.dumps(self.native),encoding='utf-8')
            annex.write_text(json.dumps({'records':[]}),encoding='utf-8')
            original=report.read_bytes()
            output=write_effective_projection(report,annex)
            value=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(value['native_report_sha256'],__import__('hashlib').sha256(original).hexdigest())
            self.assertEqual(report.read_bytes(),original)
if __name__=='__main__':unittest.main()
