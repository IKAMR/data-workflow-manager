"""v0.2.3-a1: no-Qt, no-real-archive tests for source-linked inspection."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.ks_inspector_v023_a1 import (
    WorkshopError, arkade_occurrences, inspect_xml_line, resolve_source_xml,
)

ROOT = Path(__file__).resolve().parents[1]


class InspectorTests(unittest.TestCase):
    def setUp(self):
        context = TemporaryDirectory()
        self.addCleanup(context.cleanup)
        self.root = Path(context.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.relative = 'external_evidence/arkade5/import-one/normalized/arkade5_results.json'
        self._xml()
        self.job = {'file_type':'dwm-work-job', 'job_uid':'uid-1',
                    'job':{'job_id':'JOB-003','source_extraction':str(self.source)}}
        self._save_job()
        self.test_data = {'format_version':2, 'source_system':'Arkade 5',
                          'tests': [
            {'test_id':'N5.15', 'results':[self._result('Saksmappestatus: Under behandling - Antall: 1',[9])]},
            {'test_id':'N5.22', 'results':[self._result('Journalstatus: Journalført - Antall: 1',[12])]},
            {'test_id':'N5.25', 'results':[self._result('Dokumentstatus: Under redigering - Antall: 1',[15])]}
        ]}
        self._save_evidence()

    def _xml(self):
        content = [
          '<?xml version="1.0" encoding="utf-8"?>', '<arkiv>', '<arkivdel>',
          '<systemID>AR-1</systemID>', '<tittel>STHA5</tittel>', '<mappe>',
          '<systemID>FOLD-001</systemID>', '<tittel>Første sak</tittel>',
          '<saksstatus>Under behandling</saksstatus>', '<registrering>',
          '<systemID>REG-001</systemID>', '<journalstatus>Journalført</journalstatus>',
          '<dokumentbeskrivelse>', '<systemID>DOC-001</systemID>',
          '<dokumentstatus>Under redigering</dokumentstatus>',
          '</dokumentbeskrivelse>', '</registrering>', '</mappe>',
          '</arkivdel>', '</arkiv>',
        ]
        self.source_file = self.source/'arkivstruktur.xml'
        self.source_file.write_text('\n'.join(content)+'\n',encoding='utf-8')

    def _save_job(self):
        (self.work/'job.json').write_text(json.dumps(self.job),encoding='utf-8')

    def _result(self,message,lines, *,typ='Error', scope='STHA5'):
        return {'result_type':typ,'message':message,'location':
                {'file_name':'arkivstruktur.xml','line_numbers':lines},
                'result_set_path':['Arkivdel (systemID, tittel): AR-1, '+scope]}

    def _save_evidence(self):
        file=self.work/self.relative
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(self.test_data,ensure_ascii=False),encoding='utf-8')
        self.snapshot = {'evidence_manifest':[{'path':self.relative,'sha256':sha256(file.read_bytes()).hexdigest()}]}
        self.snapshot['findings'] = [self._finding(t) for t in ('N5.15','N5.22','N5.25')]

    def _finding(self,tid):
        t=next(t for t in self.test_data['tests'] if t['test_id']==tid)
        d=t['results'][0]
        return {'source':'Arkade 5','test_id':tid,'severity':'ERROR',
                'message':d['message'],'context':' / '.join(d['result_set_path']),
                'lines':d['location']['line_numbers'],'source_ref':self.relative}

    def test_three_errors_are_source_bound_lines_not_recomputed(self):
        for tid,n in (('N5.15',9),('N5.22',12),('N5.25',15)):
            with self.subTest(test=tid):
                result=arkade_occurrences(self.work,self.snapshot, finding=self._finding(tid))
                self.assertEqual(len(result['rows']),1)
                self.assertEqual(result['rows'][0]['line'],n)
                self.assertEqual(result['groups'][0]['archive_part_id'],'AR-1')
                self.assertFalse(result['groups'][0]['count_mismatch'])

    def test_test_level_groups_multiple_n522_statuses(self):
        self.test_data['tests'][1]['results'].append(self._result('Journalstatus: Reservert - Antall: 2',[18,19]))
        self._save_evidence()
        result=arkade_occurrences(self.work,self.snapshot,test_id='N5.22')
        self.assertEqual(len(result['groups']),2)
        self.assertEqual(len(result['rows']),3)
        self.assertEqual([r['line'] for r in result['rows']],[12,18,19])

    def test_finding_scope_must_match_exact_message_and_archived_lines(self):
        wrong={**self._finding('N5.15'),'message':'Tilfeldig annen status'}
        with self.assertRaisesRegex(WorkshopError,'eksakt'):
            arkade_occurrences(self.work,self.snapshot,wrong)
        wrong={**self._finding('N5.15'),'lines':[555]}
        with self.assertRaises(WorkshopError):
            arkade_occurrences(self.work,self.snapshot,wrong)

    def test_all_original_status_values_and_ids_from_xml(self):
        for tid,line,expected_id in (('N5.15',9,'FOLD-001'),('N5.22',12,'REG-001'),('N5.25',15,'DOC-001')):
            with self.subTest(test=tid):
                result=inspect_xml_line(self.work,{'test_id':tid,'file':'arkivstruktur.xml','line':line})
                self.assertTrue(result['available'])
                self.assertEqual(result['metadata']['system_id'],expected_id)
                self.assertEqual(result['line'],line)
                self.assertIn(f'> {line:>9}:',result['excerpt'])
                self.assertIn('xpath',result['metadata'])

    def test_not_accessible_source_does_not_fake_xml_objects(self):
        self.source_file.unlink()
        row=arkade_occurrences(self.work,self.snapshot,test_id='N5.15')['rows'][0]
        result=inspect_xml_line(self.work,row)
        self.assertFalse(result['available'])
        self.assertNotIn('metadata',result)
        self.assertEqual(result['line'],9)

    def test_reported_aggregate_without_lines_is_not_fabricated(self):
        self.test_data['tests'][0]['results'][0]['location']['line_numbers']=[]
        self._save_evidence()
        result=arkade_occurrences(self.work,self.snapshot,test_id='N5.15')
        self.assertEqual(len(result['rows']),0)
        self.assertTrue(result['has_only_aggregate'])
        self.assertTrue(result['groups'][0]['count_mismatch'])

    def test_count_mismatch_is_explicitly_reported(self):
        self.test_data['tests'][0]['results'][0]['message']='Saksmappestatus: Under behandling - Antall: 19'
        self._save_evidence()
        result=arkade_occurrences(self.work,self.snapshot,test_id='N5.15')
        self.assertEqual(len(result['rows']),1)
        self.assertTrue(result['groups'][0]['count_mismatch'])

    def test_corrupted_evidence_hash_is_blocked(self):
        (self.work/self.relative).write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(WorkshopError,'endret'):
            arkade_occurrences(self.work,self.snapshot,test_id='N5.15')

    def test_not_manifest_bound_cannot_be_loaded(self):
        self.snapshot['evidence_manifest']=[]
        with self.assertRaisesRegex(WorkshopError,'ikke entydig bundet'):
            arkade_occurrences(self.work,self.snapshot,test_id='N5.15')

    def test_different_archive_job_cannot_provide_findings(self):
        self.snapshot['findings']=[{'source':'Arkade 5','test_id':'N5.99',
                                   'source_ref':self.relative}]
        with self.assertRaisesRegex(WorkshopError,'entydig'):
            arkade_occurrences(self.work,self.snapshot,test_id='N5.15')

    def test_invalid_report_format_is_rejected(self):
        self.test_data['source_system']='not Arkade'
        self._save_evidence()
        with self.assertRaisesRegex(WorkshopError,'Ukjent format'):
            arkade_occurrences(self.work,self.snapshot,test_id='N5.15')

    def test_unlinked_source_xml_is_not_scanned(self):
        self.job['job']['source_extraction']=str(self.root/'other')
        self._save_job()
        self.assertIsNone(resolve_source_xml(self.work,'arkivstruktur.xml'))
        self.assertIsNone(resolve_source_xml(self.work,'../../etc/passwd'))

    def test_original_source_and_evidence_remain_unchanged(self):
        before={p:sha256(p.read_bytes()).hexdigest() for p in (self.source_file,self.work/self.relative,self.work/'job.json')}
        row=arkade_occurrences(self.work,self.snapshot,test_id='N5.15')['rows'][0]
        inspect_xml_line(self.work,row)
        after={p:sha256(p.read_bytes()).hexdigest() for p in before}
        self.assertEqual(before,after)

    def test_cancelled_source_read_does_not_write(self):
        with self.assertRaisesRegex(WorkshopError,'avbrutt'):
            inspect_xml_line(self.work,{'file':'arkivstruktur.xml','line':9,'test_id':'N5.15'},cancel=lambda:True)

    def test_gui_entrypoints_are_deferred_and_basic_mode_uses_same_ks(self):
        entry=(ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        main=(ROOT/'gui_qt/main_v023_a1.py').read_text(encoding='utf-8')
        gui=(ROOT/'gui_qt/ks_inspector_v023_a1.py').read_text(encoding='utf-8')
        self.assertIn('from gui_qt.main_v023_a1 import DwmMainWindow',entry)
        self.assertIn('from gui_qt.main_v022_a12 import DwmMainWindow',main)
        self.assertIn('self._a12_open_ks_workshop', (ROOT/'gui_qt/main_v022_a12.py').read_text('utf-8'))
        for token in ('Inspiser valgt funn','Inspiser Arkade-test','Vis XML-kontekst',
                      '_inspect_finding','_inspect_test','_test_double_clicked'):
            self.assertIn(token,gui)
        self.assertNotIn('api.run_job(',main)
        self.assertNotIn('installEventFilter(',main)

    def test_version_is_a1_and_distribution_matches(self):
        from version import VERSION
        import tomllib
        self.assertEqual(VERSION,'0.2.3-a1')
        with (ROOT/'pyproject.toml').open('rb') as f:
            self.assertEqual(tomllib.load(f)['project']['version'],'0.2.3a1')


if __name__=='__main__':
    unittest.main()
