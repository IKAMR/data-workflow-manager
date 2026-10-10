import unittest
from pathlib import Path
from noark5_workflow.external_evidence.archive_part_evidence_a5 import archive_part_summary

class ArchiveEvidenceTabTests(unittest.TestCase):
    def test_part_evidence_is_distinct_and_formatted(self):
        projection={'archive_parts':{'1':{'metrics':{'folder_count':{
            'status':'external_evidence_selected','dwm_value':None,'effective_value':66834,
            'effective_source':'KDRS Query','evidence':{'source_file':'KDRS.txt','test_id':'T01','line':3}}}},
            '2':{'metrics':{}}}}
        lines=archive_part_summary(projection,1)
        self.assertIn('66 834',lines[0]);self.assertIn('DWM Ukjent',lines[0])
        self.assertIn('KDRS.txt',lines[1]);self.assertEqual(archive_part_summary(projection,2),[])
    def test_gui_uses_scope_identity_and_keeps_original_data(self):
        source=(Path(__file__).parents[1]/'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn("sid == str(candidate.get('system_id')",source)
        self.assertIn('Ekstern evidens – valgt arkivdel',source)
        self.assertIn('self._render_a5_archive_evidence(index)',source)
        self.assertNotIn('subprocess',source)
if __name__=='__main__':unittest.main()
