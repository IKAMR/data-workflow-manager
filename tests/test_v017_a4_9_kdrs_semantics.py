from __future__ import annotations
import unittest
from noark5_workflow.external_evidence.kdrs_query_semantics import extract_field_observations, attach_semantic_facts, reconcile_semantic_observations

class KdrsSemanticMappingTests(unittest.TestCase):
    def test_standard_not_a_random_number(self):
        rows=extract_field_observations('N5.10 Mapper pr. type; Alle: 2173\nsaksmappe: 2173\nElektr: 49926',report_type='standard',legacy_job_id='C08')
        facts=[f for r in rows for f in r['facts'] if f['mapping_status']=='exact']
        self.assertEqual([(f['metric_id'],f['value']) for f in facts],[('folder_count',2173),('case_folder_count',2173)])
    def test_u1_pairs_and_u2_parts(self):
        u1=extract_field_observations('U1. N5.101 test\nN5.16 Registreringer: 9918, Journalpost: 9860\nN5.26.01 Dokumentobjekt: 44202, @@',report_type='u01',legacy_job_id='U01')
        self.assertIn(('journalpost_count',9860),[(f['metric_id'],f['value']) for r in u1 for f in r['facts'] if f['mapping_status']=='exact'])
        u2=extract_field_observations('U2. N5.102 test\nArkivdel 1: Del A\n[.2] Mappe typer: @@, Alle: 1906 @@\nArkivdel 2: Del B\n[.2] Mappe typer: @@, Alle: 154 @@',report_type='u02',legacy_job_id='U02')
        self.assertEqual([(r['archive_part_index'],f['value']) for r in u2 for f in r['facts'] if f['metric_id']=='folder_count'],[(1,1906),(2,154)])
    def test_reconciliation_conflicts_are_not_silent(self):
        pool={'summary':{},'resources':[]}
        for rid,typ,legacy,raw in [('a','standard','C08','N5.10 Mapper pr. type; Alle: 10'),('b','u01','U01','N5.10/12/14 Mapper: 12; Sak: 12')]:
            pool['resources'].append({'resource_id':rid,'import_id':'same','source_file':rid+'.txt','source_sha256':rid,'report_type':typ,'legacy_test_id':legacy,'raw_text':raw})
        attach_semantic_facts(pool)
        outcome=reconcile_semantic_observations(pool)
        self.assertIn('folder_count',[x['metric_id'] for x in outcome['import_groups']['same']['conflicts']])
if __name__=='__main__':unittest.main()
