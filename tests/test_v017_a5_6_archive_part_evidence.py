import unittest
from noark5_workflow.external_evidence.archive_part_evidence_a5 import available_archive_parts,part_evidence_lines
from noark5_workflow.external_evidence.evidence_report_bridge_a5 import reconcile_depot_report

class PartEvidenceTests(unittest.TestCase):
    def test_browser_shows_scope_and_provenance(self):
        annex={'records':[{'archive_part_index':1,'dwm_archive_part':{'title':'Arkivdel A'},'metric_id':'folder_count','dwm_value':None,'effective_value':12345,'status':'external_evidence_selected','external_comparison':'agreement','dwm_comparison':'unknown','evidence':{'source':'KDRS Query','source_file':'u2.txt','source_sha256':'abc','source_line_number':88,'reason':'missing_dwm_test','note':'verifisert'}}]}
        self.assertEqual(available_archive_parts(annex),[(1,'Arkivdel A')])
        text='\n'.join(part_evidence_lines(annex,1))
        for value in ('12 345','KDRS Query','u2.txt','abc','88','missing_dwm_test'):
            self.assertIn(value,text)
        self.assertEqual(available_archive_parts({'records':[{'archive_part_index':2,'dwm_archive_part':None}]}),[])
    def test_out_of_range_scope_never_promoted(self):
        native={'report_type':'noark5_depot_validation','summary':{},'archive_parts':[{'archive_part':{'title':'A'}}]}
        # Inject a well-formed decision and exact external observation scoped to part 2.
        fact={'mapping_status':'exact','metric_id':'folder_count','value_kind':'count','archive_part_index':2,'value':100,'source_sha256':'abc','source_resource_id':'r','source_line_number':5,'archive_part_title':'B'}
        pool={'resources':[{'resource_id':'r','source_system':'KDRS Query','source_sha256':'abc','report_type':'u02','semantic_lines':[{'facts':[fact]}]}]}
        decisions={'part:2:folder_count':{'id':'r:exact:5:folder_count','source_sha256':'abc','value':100,'source_import_id':None,'reason':'missing_dwm_test'}}
        result=reconcile_depot_report(native,pool,decisions)
        row=next(x for x in result['records'] if x['scope_key']=='part:2:folder_count')
        self.assertEqual(row['status'],'scope_review_required')
        self.assertIsNone(row['effective_value'])
        self.assertEqual(row['scope_review'],'archive_part_index_out_of_range')
    def test_gui_includes_part_browser(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn('command=self._show_a5_part_evidence',source)
        self.assertIn('self._update_a5_part_options()',source)

if __name__=='__main__':unittest.main()
