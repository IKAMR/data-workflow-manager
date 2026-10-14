"""A18 U2 reporting regression: scope, data provenance, no invented totals."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from noark5_workflow.reporting import archive_u2_a18 as u2
from noark5_workflow.reporting import report_package_a16 as package
from noark5_workflow.reporting.job_summary_a16 import ReportOptions


class Job:
    def __init__(self, ident, folder):
        self.job_id = ident
        self.name = ident
        self.work_operations = str(folder)
        self.status = types.SimpleNamespace(value='Ferdig')
        self.progress = 1.0


def native():
    return {'summary': {'folder_count': 10, 'registration_count': 15},
            'archive_parts': [
                {'archive_part': {'system_id': 'AP-S', 'title': 'Saksarkiv'}, 'folder_count': 10,
                 'registration_count': 15},
                {'archive_part': {'system_id': 'AP-E', 'title': 'Elevarkiv'}, 'folder_count': None}],
            'technical_validation': {'summary': {'ok': 3,'error':0}}}


def evidence(resources):
    return {'kdrs_query': {'resources': resources}, 'arkade5': {'imports': []}}


def source(title, *, number=1, src='u2.txt'):
    return {'report_type': 'u02', 'archive_part_index': number,
            'archive_part_title': title, 'test_id': 'kdrs.c08', 'test_point': 'U2-08',
            'test_name': 'Mapper', 'source_file': src, 'source_sha256': 'a'*64,
            'source_import_id': 'imp-1', 'observations': [{'line': 1, 'text':'6 848 mapper'}]}


class U2ArchivePartTests(unittest.TestCase):
    def test_unique_title_links_one_archive_part_without_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            job = Job('JOB-002', td)
            model = u2.collect_u2_archive_parts([(job, native(), None, '')],
                        evidence_by_job={'JOB-002': evidence([source('Saksarkiv'),source('Unknown')])})
            a, b = model['archive_parts']
            self.assertEqual(a['u2_count'], 1)
            self.assertEqual(b['u2_count'], 0)
            self.assertEqual(len(model['unmatched_u2']), 1)
            self.assertEqual(a['metrics']['folder_count']['report'], 10)
            self.assertEqual(a['metrics']['registration_count']['report'], 15)
            self.assertNotIn('6848', u2.render_u2_archive_parts(model))
            self.assertIn('U2-resultater uten entydig', u2.render_u2_archive_parts(model))

    def test_ambiguous_duplicate_title_not_attributed(self):
        with tempfile.TemporaryDirectory() as td:
            job = Job('JOB-001', td)
            data = native()
            data['archive_parts'][1]['archive_part']['title']='Saksarkiv'
            model = u2.collect_u2_archive_parts([(job, data, None, '')],
                        evidence_by_job={'JOB-001': evidence([source('Saksarkiv')])})
            self.assertEqual([p['u2_count'] for p in model['archive_parts']], [0,0])
            self.assertEqual(len(model['unmatched_u2']), 1)

    def test_no_depot_report_keeps_unmatched_u2(self):
        with tempfile.TemporaryDirectory() as td:
            job=Job('JOB-002',td)
            model=u2.collect_u2_archive_parts([(job,None,None,'48 XPath-feil')],
                      evidence_by_job={'JOB-002':evidence([source('Saksarkiv')])})
            self.assertEqual(model['archive_parts'], [])
            self.assertEqual(len(model['unmatched_u2']), 1)
            self.assertIn('Ingen depotrapport',model['unmatched_u2'][0]['reason'])

    def test_verified_scoped_projection_can_change_one_part_only(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            job=Job('JOB-001',folder)
            data=native()
            report=folder/'depot_validation_report.json'
            report.write_text(json.dumps(data),encoding='utf-8')
            external=folder/'depot-external-evidence.json'
            external.write_bytes(b'origin')
            projection={'kind':'noark5_effective_evidence_projection',
                'native_report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),
                'evidence_companion_file':external.name,
                'evidence_companion_sha256':hashlib.sha256(external.read_bytes()).hexdigest(),
                'archive_parts':{'1':{
                    'archive_part':{'system_id':'AP-S','title':'Saksarkiv'},
                    'metrics':{'registration_count':{
                        'dwm_value':15,'effective_value':20,
                        'effective_source':'KDRS Query','status':'external_evidence_selected',
                        'evidence':{'source_sha256':'a'*64}}}}}}
            (folder/'depot-effective-evidence.json').write_text(json.dumps(projection),encoding='utf-8')
            ev={'JOB-001':evidence([source('Saksarkiv')])}
            m=u2.collect_u2_archive_parts([(job,data,report,'')],evidence_by_job=ev)
            a,b=m['archive_parts']
            self.assertEqual(a['metrics']['registration_count']['report'],20)
            self.assertEqual(a['metrics']['registration_count']['source'],'KDRS Query (verifisert)')
            self.assertEqual(b['metrics']['folder_count']['report'],None)
            self.assertIn('(KDRS)',u2.render_u2_archive_parts(m))
            external.write_text('changed',encoding='utf-8')
            m2=u2.collect_u2_archive_parts([(job,data,report,'')],evidence_by_job=ev)
            self.assertEqual(m2['archive_parts'][0]['metrics']['registration_count']['report'],15)
            self.assertTrue(m2['diagnostics'])

    def test_does_not_mix_jobs_with_same_title(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=Job('JOB-001',td),Job('JOB-002',td)
            model=u2.collect_u2_archive_parts([(a,native(),None,''),(b,native(),None,'')],
                     evidence_by_job={'JOB-001':evidence([source('Saksarkiv')]),
                                      'JOB-002':evidence([])})
            self.assertEqual(len(model['archive_parts']),4)
            self.assertEqual([p['u2_count'] for p in model['archive_parts']], [1,0,0,0])

    def test_package_main_and_json_use_same_u2_model(self):
        from noark5_workflow.reporting import job_summary_a16 as summary
        with tempfile.TemporaryDirectory() as td:
            job=Job('JOB-002',td)
            data=native()
            ev=evidence([source('Saksarkiv')])
            with patch.object(u2,'collect_job_evidence',return_value=ev),\
                 patch.object(summary,'_latest_report',return_value=(data,None,'')),\
                 patch.object(package,'_latest_report',return_value=(data,None,'')):
                package.write_report_package(td,[job],
                    ReportOptions(level='Medium',sections=('overview','totals','external'),archive_part_appendix=True),
                    formats=('html','json'))
            base=Path(td)
            main=(base/'index.html').read_text(encoding='utf-8')
            appendix=(base/'vedlegg-b-arkivdeler.html').read_text(encoding='utf-8')
            payload=json.loads((base/'index.json').read_text(encoding='utf-8'))
            self.assertIn('KDRS Query U2', main)
            self.assertIn('Elevarkiv',main)
            self.assertIn('U2-08',appendix)
            self.assertEqual(payload['kdrs_u2_archive_parts']['archive_parts'][0]['u2_count'],1)


if __name__ == '__main__':
    unittest.main()
