from pathlib import Path
import tempfile
import unittest
from noark5_workflow.external_evidence.evidence_report_a5 import evidence_annex


def resource(value, source, part=None):
    return {'source_system': 'KDRS Query', 'resource_id': source,
            'source_sha256': source+'123', 'source_import_id': source,
            'source_file': source+'.txt', 'report_type': 'u02' if part else 'standard',
            'semantic_lines': [{'facts': [{'mapping_status': 'exact', 'metric_id': 'case_count',
            'value_kind':'count','archive_part_index':part,'value':value,
            'source_sha256':source+'123','source_resource_id':source,'source_line_number':1}]}]}

class EvidenceAnnexTests(unittest.TestCase):
    def test_conflict_keeps_all_candidates_without_automatic_override(self):
        pool={'resources':[resource(10,'one'),resource(11,'two')]}
        r=evidence_annex(pool, {}, dwm_values={'whole:case_count':9})['records'][0]
        self.assertEqual(r['external_comparison'],'conflict')
        self.assertEqual(r['dwm_comparison'],'conflict')
        self.assertEqual(r['effective_value'],9)
        self.assertEqual(len(r['external_candidates']),2)
    def test_archive_parts_not_summed_or_merged(self):
        pool={'resources':[resource(2,'one',1),resource(3,'two',2)]}
        rows=evidence_annex(pool,{})['records']
        self.assertEqual([r['scope_key'] for r in rows],['part:1:case_count','part:2:case_count'])
        self.assertEqual([r['external_unique_values'] for r in rows],[[2],[3]])
    def test_valid_selected_evidence_is_traceable(self):
        pool={'resources':[resource(42,'one')]}
        from noark5_workflow.external_evidence.evidence_decisions_a5 import exact_candidates
        c=exact_candidates(pool,'case_count')[0]
        annex=evidence_annex(pool,{'whole:case_count':{**c,'reason':'missing_dwm_test','note':'verified'}})
        row=annex['records'][0]
        self.assertEqual(row['effective_value'],42)
        self.assertEqual(row['evidence']['source_sha256'],'one123')
        self.assertEqual(row['status'],'external_evidence_selected')
    def test_no_false_dwm_comparison_when_not_loaded(self):
        r=evidence_annex({'resources':[resource(8,'one')]},{})['records'][0]
        self.assertEqual(r['dwm_comparison'],'unknown')
        self.assertIsNone(r['effective_value'])

if __name__ == '__main__': unittest.main()
