from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from noark5_workflow.external_evidence.evidence_decisions_a5 import (
    exact_candidates, select_evidence, load_decisions, report_evidence)


def sample():
    return {'resources': [{'source_system': 'KDRS Query', 'import_id': 'job-002',
        'source_sha256': 'digest-a', 'resource_id': 'r1', 'source_file': 'U2.txt',
        'report_type': 'u02', 'semantic_lines': [{ 'facts': [
        {'mapping_status':'exact','metric_id':'folder_count','value_kind':'count',
         'value':100,'archive_part_index':1,'archive_part_title':'Del A',
         'source_line_number':8},
        {'mapping_status':'exact','metric_id':'folder_count','value_kind':'count',
         'value':50,'archive_part_index':2,'source_line_number':9},
        {'mapping_status':'context_only','metric_id':'folder_count','value_kind':'count',
         'value':9000,'archive_part_index':None,'source_line_number':10}]}]}]}

class EvidenceDecisions(unittest.TestCase):
    def test_part_scope_is_strict(self):
        self.assertEqual(exact_candidates(sample(),'folder_count'), [])
        self.assertEqual([x['value'] for x in exact_candidates(sample(),'folder_count',part_index=1)], [100])
        self.assertEqual([x['value'] for x in exact_candidates(sample(),'folder_count',part_index=2)], [50])

    def test_explicit_selection_does_not_change_dwm(self):
        with tempfile.TemporaryDirectory() as td:
            bank=sample()
            before=report_evidence(bank,{},metric='folder_count',part_index=1,dwm_value=92)
            self.assertEqual(before['effective_value'],92)
            option=exact_candidates(bank,'folder_count',part_index=1)[0]
            select_evidence(td,bank,metric='folder_count',part_index=1,
                            evidence_id=option['id'],reason='invalid_dwm_result',note='Validated')
            result=report_evidence(bank,load_decisions(td),metric='folder_count',part_index=1,dwm_value=92)
            self.assertEqual((result['effective_value'],result['dwm_value']), (100,92))
            self.assertEqual(result['evidence']['source_sha256'],'digest-a')
            bank['resources'][0]['source_sha256']='changed'
            stale=report_evidence(bank,load_decisions(td),metric='folder_count',part_index=1,dwm_value=92)
            self.assertEqual(stale['status'],'stale_evidence_selection')
            self.assertEqual(stale['effective_value'],92)

    def test_missing_or_unmapped_evidence_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                select_evidence(td,sample(),metric='folder_count',part_index=None,
                                evidence_id='r1:exact:8:folder_count',reason='missing_dwm_test')
            with self.assertRaises(ValueError):
                select_evidence(td,sample(),metric='folder_count',part_index=1,
                                evidence_id='r1:exact:8:folder_count',reason='unsupported')

if __name__=='__main__': unittest.main()
