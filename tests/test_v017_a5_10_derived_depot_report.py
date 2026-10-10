import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from noark5_workflow.external_evidence.effective_depot_report_a5 import derive_effective_report, write_derived_depot_report
from noark5_workflow.external_evidence.evidence_projection_a5 import write_effective_projection


class DerivedReportTests(unittest.TestCase):
    def setUp(self):
        self.native = {'report_type':'noark5_depot_validation',
          'summary':{'folder_count':None,'registration_count':0},
          'archive_parts':[{'archive_part':{'system_id':'A','title':'En'},'folder_count':3}]}
        self.annex = {'records':[
          {'scope_key':'whole:folder_count','status':'external_evidence_selected',
           'effective_source':'KDRS Query','effective_value':66834,'evidence':{'source_file':'s.txt'}},
          {'scope_key':'part:1:folder_count','status':'external_evidence_selected',
           'effective_source':'KDRS Query','effective_value':40,'evidence':{'source_file':'u2.txt'}}]}

    def test_derived_with_scope_original_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); report=root/'depot.json'; annex=root/'depot-external-evidence.json'
            report.write_text(json.dumps(self.native),encoding='utf8')
            annex.write_text(json.dumps(self.annex),encoding='utf8')
            original=report.read_bytes()
            projection=write_effective_projection(report,annex)
            derived=write_derived_depot_report(report,projection)
            data=json.loads(derived.read_text(encoding='utf8'))
            self.assertEqual(data['summary']['folder_count'],66834)
            self.assertEqual(data['summary']['registration_count'],0)
            self.assertEqual(data['archive_parts'][0]['folder_count'],40)
            self.assertEqual(len(data['external_evidence_application']['applied']),2)
            self.assertEqual(report.read_bytes(),original)

    def test_stale_report_and_annex_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); report=root/'depot.json'; annex=root/'depot-external-evidence.json'
            report.write_text(json.dumps(self.native),encoding='utf8')
            annex.write_text(json.dumps(self.annex),encoding='utf8')
            projection=write_effective_projection(report,annex)
            report.write_text(json.dumps({'report_type':'noark5_depot_validation','summary':{},'archive_parts':[]}),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'endret'):write_derived_depot_report(report,projection)
            report.write_text(json.dumps(self.native),encoding='utf8')
            annex.write_text('{}',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'endret'):write_derived_depot_report(report,projection)

    def test_identity_and_changed_original_rejected(self):
        from noark5_workflow.external_evidence.evidence_projection_a5 import effective_projection
        projection=effective_projection(self.native,self.annex)
        native2=json.loads(json.dumps(self.native))
        native2['archive_parts'][0]['archive_part']['system_id']='B'
        with self.assertRaisesRegex(ValueError,'Arkivdelidentitet'):derive_effective_report(native2,projection)
        native3=json.loads(json.dumps(self.native))
        native3['summary']['folder_count']=10
        with self.assertRaisesRegex(ValueError,'endret'):derive_effective_report(native3,projection)

    def test_gui_connected(self):
        gui=(Path(__file__).parents[1]/'gui/depot_result_center_v017_a1.py').read_text(encoding='utf8')
        self.assertIn('write_derived_depot_report(report_path, projection_path)',gui)

if __name__=='__main__':unittest.main()
