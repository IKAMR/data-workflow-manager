"""A16: large XPath masters and historical source identity; no normative pass."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noark5_workflow.reporting.qa_xpath_master_v023_a16 import (
    XPathMasterError, hash_file, project_xpath_master,
)
from app import noark5_xpath_source_audit_v023_a16 as audit


def json_events(value, prefix=''):
    """Tiny test-only ijson.parse replacement; models actual event contracts."""
    if isinstance(value, dict):
        yield (prefix, 'start_map', None)
        for key, entry in value.items():
            yield (prefix, 'map_key', key)
            yield from json_events(entry, prefix + '.' + key if prefix else key)
        yield (prefix, 'end_map', None)
    elif isinstance(value, list):
        yield (prefix, 'start_array', None)
        for entry in value:
            yield from json_events(entry, prefix + '.item')
        yield (prefix, 'end_array', None)
    else:
        typ = ('null' if value is None else 'boolean' if type(value) is bool else
               'string' if type(value) is str else 'integer' if type(value) is int else 'number')
        yield (prefix, typ, value)


class FakeJsonParser:
    class JSONError(ValueError):
        pass
    @staticmethod
    def parse(stream):
        doc = json.load(stream)
        yield from json_events(doc)


class A16Master(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'master-results.json'
        self.parser = patch.dict(sys.modules, {'ijson': FakeJsonParser})
        self.parser.start()
        self.addCleanup(self.parser.stop)

    def write(self, doc):
        self.path.write_text(json.dumps(doc), encoding='utf-8')

    def sample(self):
        return {'format_version': 1, 'source': {'execution_profile': 'normal'},
                'tests': [{'test_id': 'kdrs.c01', 'status': 'ok', 'name': 'Arkiv',
                           'test_point': 'N5.04', 'big_payload': ['not used']}]}

    def test_projection_omits_large_unneeded_payload(self):
        doc = self.sample()
        doc['tests'][0]['big_payload'] = [{'rows': 'x'*10000} for _ in range(20)]
        self.write(doc)
        result = project_xpath_master(self.path)
        self.assertEqual(result['tests'][0]['test_id'], 'kdrs.c01')
        self.assertEqual(result['tests'][0]['name'], 'Arkiv')
        self.assertNotIn('big_payload', result['tests'][0])
        self.assertLess(len(json.dumps(result)), 500)
        self.assertEqual(hash_file(self.path), sha256(self.path.read_bytes()).hexdigest())

    def test_large_master_over_old_20_mib_limit_still_projects(self):
        doc = self.sample()
        doc['tests'][0]['big_payload'] = [{'detail':'Q'*10_000} for _ in range(2100)]
        self.write(doc)
        self.assertGreater(self.path.stat().st_size, 20*1024*1024)
        got = project_xpath_master(self.path)
        self.assertEqual(len(got['tests']), 1)
        self.assertEqual(got['tests'][0]['status'], 'ok')

    def test_oversized_ignored_scalar_rejected_as_unsafe(self):
        doc = self.sample()
        doc['tests'][0]['big_payload'] = 'x'*(8*1024*1024+1)
        self.write(doc)
        with self.assertRaisesRegex(XPathMasterError, 'enkeltfelt'):
            project_xpath_master(self.path)

    def test_duplicate_test_id_rejected(self):
        doc = self.sample()
        doc['tests'].append({'test_id': 'kdrs.c01', 'status': 'ok'})
        self.write(doc)
        with self.assertRaisesRegex(XPathMasterError, 'duplisert'):
            project_xpath_master(self.path)

    def test_wrong_profile_rejected(self):
        doc = self.sample()
        doc['source']['execution_profile'] = 'advanced'
        self.write(doc)
        with self.assertRaisesRegex(XPathMasterError, 'kjøreprofil'):
            project_xpath_master(self.path)

    def test_missing_test_list_rejected(self):
        doc = self.sample()
        del doc['tests']
        self.write(doc)
        with self.assertRaises(XPathMasterError):
            project_xpath_master(self.path)

    def test_bad_scalar_type_and_oversize_rejected(self):
        doc = self.sample()
        doc['tests'][0]['test_id'] = 37
        self.write(doc)
        with self.assertRaisesRegex(XPathMasterError, 'test_id'):
            project_xpath_master(self.path)
        doc['tests'][0]['test_id'] = 'a'*(8*1024*1024+1)
        self.write(doc)
        with self.assertRaisesRegex(XPathMasterError, 'enkeltfelt'):
            project_xpath_master(self.path)

    def test_symlink_rejected(self):
        self.write(self.sample())
        other = self.path.with_name('linked.json')
        try:
            other.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest('Symlinks unavailable')
        with self.assertRaisesRegex(XPathMasterError, 'utrygg'):
            project_xpath_master(other)

    def test_missing_ijson_fails_closed_not_unbounded_json_load(self):
        self.write(self.sample())
        with patch.dict(sys.modules, {'ijson': None}):
            with self.assertRaisesRegex(XPathMasterError, 'ijson'):
                project_xpath_master(self.path)


class A16ActualIjson(unittest.TestCase):
    """Exercise the declared production parser when installed (e.g. Windows test.bat)."""

    def test_actual_ijson_parses_large_saved_master(self):
        try:
            import ijson  # noqa: F401
        except ImportError:
            self.skipTest('Production ijson parser is not installed in this Linux QA environment')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'master-results.json'
            raw = {'format_version':1, 'source':{'execution_profile':'normal'},
                   'tests':[{'test_id':'kdrs.c01', 'status':'ok',
                             'results':[{'detail':'x'*5000} for _ in range(4400)]}]}
            p.write_text(json.dumps(raw),encoding='utf-8')
            self.assertGreater(p.stat().st_size,20*1024*1024)
            projected=project_xpath_master(p)
            self.assertEqual(projected['tests'],[{'test_id':'kdrs.c01','status':'ok'}])


class A16SavedSnapshot(unittest.TestCase):
    """The normal Work bridge uses the streamed master in an actual job layout."""

    def test_over_20_mib_master_is_hashed_and_reconciled(self):
        from noark5_workflow.reporting import qa_work_snapshot_v022_a3 as bridge
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            uid = '12345678-1234-4234-9234-123456789012'
            run = 'JOB-001__20261120T120000Z-test'
            rel_report = f'noark5_reports/depot_validation/{run}/depot_validation_report.json'
            rel_master = f'noark5_tests/xpath/{run}/master-results.json'
            def write(relative, obj):
                p = root/relative
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(json.dumps(obj),encoding='utf-8')
                return p
            write('job.json', {'file_type':'dwm-work-job','format_version':1,
                               'job_uid':uid, 'job':{'job_id':'JOB-001', 'job_uid':uid,
                               'name':'Test', 'source_root':'C:\\temp\\test'}})
            master_path = write(rel_master, {'format_version':1,
                        'source':{'execution_profile':'normal'},
                        'tests':[{'test_id':'kdrs.c01','status':'ok',
                                  'big_ignored_payload':[{'detail':'x'*10_000} for _ in range(2100)]}]})
            report = write(rel_report, {'report_type':'noark5_depot_validation',
                        'summary':{'archive_part_count':1},
                        'technical_validation':{'status':'ok','tests':[{'test_id':'kdrs.c01','status':'ok'}]},
                        'archive_parts':[{'archive_part':{'system_id':'part-001','title':'A','status':'Avsluttet periode'}}],
                        'evidence':{'source_xpath_run':'C:\\temp\\'+run},
                        'external_validation':{'arkade5':{'imports':[]}}})
            def source(work, relative, *args, limit=20*1024*1024, **kw):
                path=root/relative
                if path.stat().st_size>limit:
                    raise ValueError('oversized source')
                return {'path':relative,'sha256':hash_file(path),'bytes':path.stat().st_size,
                        'state':'hashed_now'}
            with patch.dict(sys.modules,{'ijson':FakeJsonParser}), \
                 patch.object(bridge, '_source', side_effect=source) as hash_call, \
                 patch.object(bridge, '_find_depot', return_value=(report,rel_report)), \
                 patch.object(bridge, '_kdrs',return_value={'status':'not_selected'}), \
                 patch.object(bridge, '_assessments',return_value={'status':'not_registered'}), \
                 patch.object(bridge, '_parts',return_value=[{'system_id':'part-001','title':'A','status':'Avsluttet periode'}]), \
                 patch.object(bridge,'_count', side_effect=lambda n: n if type(n) is int else None), \
                 patch.object(bridge,'_extraction_label',return_value='utt-test'):
                got = bridge.build_saved_work_snapshot(root)
            self.assertEqual(got['work_identity']['job_uid'],uid)
            self.assertTrue(got['findings_complete'])
            self.assertEqual(got['dwm_technical']['status'],'ok')
            manifest=[x for x in got['evidence_manifest'] if x['kind']=='dwm_xpath_master'][0]
            self.assertEqual(manifest['sha256'],hash_file(master_path))
            self.assertGreater(manifest['bytes'],20*1024*1024)
            self.assertTrue(any(call.kwargs.get('limit',0) > 20*1024*1024
                                for call in hash_call.call_args_list))


class A16Audit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        self.kdrs = self.root/'docs/reference/kdrs-query'
        self.kdrs.mkdir(parents=True)
        self.doc = self.root/audit.CATALOG_REL
        self.doc.parent.mkdir(parents=True)
        self.catalog = []
        self.jobs = {}
        for profile, (filename, _sha) in audit.KDRS_FILES.items():
            if profile == 'Standard':
                rows = [('C01', 1), ('U01', 1), ('U02', 1)]
            elif profile == 'U1':
                rows = [('U01', 1)]
            else:
                rows = [('U02', 1)]
            source = '_PARAMETERS_\n'
            for job_id, enabled in rows:
                source += (f'[XML_QUERY]\njob_id={job_id}\njob_enabled={enabled}\n'
                           f'job_name=Test {job_id}\n#START#\ncount(//arkiv)\n#STOP#\n')
            self.jobs[profile] = source.encode('utf-8')
            (self.kdrs/filename).write_bytes(self.jobs[profile])
        self.catalog = [
            {'test_id': 'kdrs.'+x.lower(), 'status': 'active',
             'legacy': {'job_id': x, 'job_enabled': 3 if x.startswith('U') else 1}}
            for x in ('C01','U01','U02')
        ] + [{'test_id': 'kdrs.dwm.au', 'legacy': {'job_id': 'DWM-AU01', 'job_enabled': 1}}]
        self.doc.write_text(json.dumps({'catalog_id':'noark5-kdrs-query-2026-05-26',
                                        'tests':self.catalog}), encoding='utf-8')
        self.pins = {key: (filename, audit._blob(data))
                     for (key,(filename,_)),data in zip(audit.KDRS_FILES.items(),self.jobs.values())}
        self.pin_patch = patch.dict(audit.KDRS_FILES, self.pins, clear=True)
        self.pin_patch.start()
        self.addCleanup(self.pin_patch.stop)

    def test_legacy_identity_matches_without_fabricating_semantic_parity(self):
        report = audit.audit_sources(self.root)
        self.assertEqual(report['status'], 'identity_checked_with_open_semantic_qa')
        self.assertEqual(report['standard_legacy_jobs'], 3)
        self.assertEqual(report['catalog_tests'], 4)
        self.assertEqual(report['noark_xsd_status'], 'not_assessed')
        self.assertFalse(report['semantic_parity_verified'])
        self.assertFalse(report['normative_requirement_coverage_verified'])
        self.assertEqual({x['job_id'] for x in report['issues'] if x['kind']=='execution_hint_differs'},
                         {'U01','U02'})

    def test_changed_source_changes_status_and_fails_closed(self):
        path = self.kdrs/self.pins['Standard'][0]
        path.write_bytes(path.read_bytes()+b'\n# changed\n')
        report = audit.audit_sources(self.root)
        self.assertEqual(report['status'], 'incomplete_or_source_changed')
        self.assertEqual(report['kdrs_sources'][0]['status'], 'source_bytes_differ')

    def test_missing_catalog_job_flags_and_blocks_clean_status(self):
        doc = json.loads(self.doc.read_text())
        doc['tests'] = [x for x in doc['tests'] if x['legacy']['job_id'] != 'C01']
        self.doc.write_text(json.dumps(doc))
        report = audit.audit_sources(self.root)
        self.assertEqual(report['status'], 'incomplete_or_source_changed')
        self.assertIn('missing_catalog_mapping',{x['kind'] for x in report['issues']})

    def test_duplicate_legacy_id_in_catalog_rejected(self):
        doc = json.loads(self.doc.read_text())
        doc['tests'].append(dict(doc['tests'][0]))
        self.doc.write_text(json.dumps(doc))
        with self.assertRaisesRegex(audit.XPathSourceAuditError, 'duplisert'):
            audit.audit_sources(self.root)

    def test_output_atomic_and_reports_sources_without_approval(self):
        target = Path(self.tmp.name)/'out'
        self.assertEqual(audit.main(['--repo-root',str(self.root), '--output-dir',str(target)]), 0)
        doc = json.loads((target/'a16-xpath-source-audit.json').read_text())
        self.assertFalse(doc['automatic_approval'])
        self.assertIn('profile,job_id,', (target/'a16-kdrs-mapping.csv').read_text(encoding='utf-8-sig'))
        with self.assertRaisesRegex(audit.XPathSourceAuditError, 'finnes allerede'):
            audit.main(['--repo-root',str(self.root), '--output-dir',str(target)])

    def test_csv_formula_is_neutralized_without_changing_evidence(self):
        self.assertEqual(audit._csv_safe('  =1+2'), "'  =1+2")
        self.assertEqual(audit._csv_safe('+cmd'), "'+cmd")
        self.assertEqual(audit._csv_safe('Normal tekst'), 'Normal tekst')

    def test_pin_identifiers_are_immutable_git_blob_identifiers(self):
        self.assertEqual(audit.KDRS_COMMIT,
                         'a68d809ee04c8aceb75976c668bf9746e26d67cb')
        self.assertEqual(audit.NOARK_COMMIT,
                         '8d28e312e1e38af8cb93bfe05cecef11e09af34f')
        self.assertEqual(len(audit.XSD_BLOBS), 3)
        self.assertTrue(all(len(x) == 5 for x in audit.XSD_BLOBS.values()))
        self.assertEqual(audit._blob(b'hello'),
                         'b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0')

    def test_does_not_write_outputs_inside_source_checkout(self):
        with self.assertRaisesRegex(audit.XPathSourceAuditError,'utenfor kilderepoene'):
            audit.main(['--repo-root',str(self.root),'--output-dir',str(self.root/'outputs')])
        self.assertFalse((self.root/'outputs').exists())

    def test_optional_noark_inventory_all_files_are_pinned(self):
        nroot = Path(self.tmp.name)/'digital-archive-workflow'
        pins = {}
        for v in ('3.1','4.0','5.0'):
            identifiers = []
            for name in audit.XSD_NAMES:
                f = nroot/f'docs/kilder/noark/noark5/v{v}/schemas/{name}'
                f.parent.mkdir(parents=True, exist_ok=True)
                raw = f'{v} {name}'.encode('utf-8')
                f.write_bytes(raw)
                identifiers.append(audit._blob(raw))
            pins[v] = tuple(identifiers)
        with patch.dict(audit.XSD_BLOBS, pins, clear=True):
            report = audit.audit_sources(self.root,noark_root=nroot)
        self.assertEqual(report['noark_xsd_status'],'all_blobs_match')
        self.assertEqual(report['status'],'identity_checked_with_open_semantic_qa')
        self.assertFalse(report['semantic_parity_verified'])

    def test_optional_noark_inventory_does_not_conflate_versions(self):
        nroot = Path(self.tmp.name)/'digital-archive-workflow'
        original = audit.XSD_BLOBS
        inventory = {v: tuple('x'*40 for _ in range(5)) for v in original}
        # Controlled local test pins. The real implementation keeps the Git refs.
        with patch.dict(audit.XSD_BLOBS, inventory, clear=True):
            for v in ('3.1','4.0','5.0'):
                for name in audit.XSD_NAMES:
                    f = nroot/f'docs/kilder/noark/noark5/v{v}/schemas/{name}'
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text(f'{v} {name}', encoding='utf-8')
            report = audit.audit_sources(self.root,noark_root=nroot)
            self.assertEqual(len(report['noark_xsd_inventory']),15)
            self.assertEqual(report['noark_xsd_status'],'source_mismatch_or_missing')
            self.assertFalse(report['normative_requirement_coverage_verified'])

if __name__ == '__main__':
    unittest.main()
