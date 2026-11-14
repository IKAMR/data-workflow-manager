"""QA content annex: source provenance and strict separation from approval."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from noark5_workflow.analysis.canonical_qa_content_v0115_a13 import render_content_annex


class QaContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.arkade = 'external_evidence/arkade5/run/normalized/arkade5_results.json'
        self.pronom = 'external_evidence/arkade5/run/normalized/pronom_statistics.json'
        self.parts = 'Arkivdel (systemID, tittel): 11111111-1111-1111-1111-111111111111, Elektronisk 1'
        self.report = {'format_version':2, 'evidence_type':'external_validation_report',
                       'summary': {'archive_creators':'Example arkivskaper', 'archival_period':'2005 - 2024'},
                       'tests': [
                           {'test_id':'N5.06','results':[{'message':'Status for '+self.parts+': Avsluttet periode', 'result_set_path':[]}]},
                           {'test_id':'N5.10','results':[{'message':'Antall: 9', 'result_set_path':[self.parts]}]},
                           {'test_id':'N5.15','results':[{'result_type':'Error','message':'4 under behandling','result_set_path':[self.parts]}]},
                       ]}
        self.pronom_doc = {'evidence_type':'arkade5_pronom_format_statistics', 'csv':{'rows':[
            {'Format-ID':'fmt/354','Filtype':'PDF/A','Formatversjon':'1b','RAF-220301':'Gyldig','Antall':'3'},
            {'Format-ID':'fmt/17','Filtype':'PDF','Formatversjon':'1.3','RAF-220301':'Ikke gyldig','Antall':'1'},
        ]}}
        self.canonical = {'extraction': {'stable_id':'job-1', 'delivery_id': None}, 'observations':[
            {'test_id':'kdrs.c02', 'numeric_values': {'archive_part_count':1, 'folder_count':9}}]}
        self.external = {'analysis': {'sources': []}, 'sources':{}}
        for rel, doc, fmt in [(self.arkade,self.report,'arkade_normalized_v2'),
                              (self.pronom,self.pronom_doc,'arkade_pronom_statistics_v1')]:
            path = self.work / rel
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(doc),encoding='utf-8')
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.external['analysis']['sources'].append({'evidence': {'work_relative_path': rel, 'sha256': sha},
                                                          'analysis': {'source_format': fmt}})
            self.external['sources'][rel] = 'analyzed'

    def test_reports_archive_part_and_file_formats_separately(self):
        html, summary = render_content_annex(self.work, self.external, self.canonical)
        self.assertEqual(summary['archive_parts_listed'],1)
        self.assertIn('Elektronisk 1',html)
        self.assertIn('Avsluttet periode',html)
        self.assertIn('4 under behandling',html)
        self.assertIn('<td>9</td>',html)
        self.assertIn('fmt/354',html)
        self.assertIn('Sum i valgt formatstatistikk:</b> 4 filer',html)
        self.assertIn('ikke</b> dokumentasjon',html)
        self.assertIn('Ikke dokumentert',html)

    def test_modified_external_evidence_is_not_reported(self):
        (self.work / self.arkade).write_text('{"changed":true}',encoding='utf-8')
        html, summary = render_content_annex(self.work, self.external, self.canonical)
        self.assertEqual(summary['archive_parts_listed'],0)
        self.assertNotIn('Elektronisk 1',html)
        self.assertTrue(summary['pronom_statistics_present'])

    def test_unselected_source_is_not_reported(self):
        self.external['sources'][self.arkade]='not_analyzed'
        html, summary = render_content_annex(self.work,self.external,self.canonical)
        self.assertEqual(summary['archive_parts_listed'],0)
        self.assertNotIn('Elektronisk 1',html)

    def test_escapes_untrusted_archive_title(self):
        self.report['tests'][0]['results'][0]['message']='Status for '+self.parts.replace('Elektronisk 1','<script>alert(1)</script>')+': Aktiv periode'
        path=self.work/self.arkade
        path.write_text(json.dumps(self.report),encoding='utf-8')
        self.external['analysis']['sources'][0]['evidence']['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        html,_=render_content_annex(self.work,self.external,self.canonical)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)

    def test_does_not_invent_unreported_per_part_period(self):
        html,_=render_content_annex(self.work,self.external,self.canonical)
        self.assertIn('ikke</b> dokumentasjon på perioder for hver arkivdel',html)
        self.assertNotIn('kravoppfyllelse er godkjent',html.lower())

    def test_stale_pronom_hash_is_not_reported(self):
        self.external['analysis']['sources'][1]['evidence']['sha256']='bad'
        html,summary=render_content_annex(self.work,self.external,self.canonical)
        self.assertFalse(summary['pronom_statistics_present'])
        self.assertNotIn('fmt/354',html)

if __name__ == '__main__':
    unittest.main()
