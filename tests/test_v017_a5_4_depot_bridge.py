import unittest
from noark5_workflow.external_evidence.evidence_report_bridge_a5 import read_dwm_values,reconcile_depot_report


def report():
    return {'report_type':'noark5_depot_validation','depot_report_model_format_version':2,
      'summary':{'folder_count':None,'archive_part_count':2,'registration_count':0},
      'archive_parts':[{'archive_part':{'system_id':'a','title':'First'},'folder_count':None},
                       {'archive_part':{'system_id':'b','title':'Second'},'folder_count':0}]}

def source(value,index,title):
    return {'resource_id':'r','source_system':'KDRS Query','source_sha256':'hash',
      'source_file':'u02.txt','report_type':'u02','semantic_lines':[{'facts':[{
        'mapping_status':'exact','value_kind':'count','metric_id':'folder_count',
        'archive_part_index':index,'archive_part_title':title,'value':value,
        'source_line_number':3,'source_sha256':'hash','source_resource_id':'r'}]}]}

class BridgeTests(unittest.TestCase):
    def test_missing_dwm_is_not_zero(self):
        values, parts = read_dwm_values(report())
        self.assertIsNone(values['whole:folder_count'])
        self.assertIsNone(values['part:1:folder_count'])
        self.assertEqual(values['part:2:folder_count'],0)
        self.assertEqual(parts[2]['title'],'Second')
    def test_no_automatic_promotion(self):
        a=reconcile_depot_report(report(),{'resources':[source(42,1,'First')]},{})
        row=next(r for r in a['records'] if r['scope_key']=='part:1:folder_count')
        self.assertEqual(row['external_unique_values'],[42])
        self.assertIsNone(row['effective_value'])
        self.assertEqual(row['dwm_comparison'],'unknown')
    def test_mismatched_part_title_requires_review(self):
        pool={'resources':[source(42,1,'Wrong')]}
        from noark5_workflow.external_evidence.evidence_decisions_a5 import exact_candidates
        candidate=__import__('noark5_workflow.external_evidence.evidence_decisions_a5',fromlist=['exact_candidates']).exact_candidates(pool,'folder_count',part_index=1)[0]
        row=next(r for r in reconcile_depot_report(report(),pool,{'part:1:folder_count':{**candidate,'reason':'missing_dwm_test'}})['records'] if r['scope_key']=='part:1:folder_count')
        self.assertEqual(row['status'],'scope_review_required')
        self.assertIsNone(row['effective_value'])
    def test_invalid_report_rejected(self):
        with self.assertRaises(ValueError):read_dwm_values({'report_type':'something_else'})

if __name__=='__main__':unittest.main()
