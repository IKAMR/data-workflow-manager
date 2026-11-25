"""Source-bound Noark object navigation, cache integrity and A4 ledger reuse."""
from __future__ import annotations

import ast
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from app.noark_object_browser_v027_a5 import (
    ObjectIndexError, INDEX_DIR, _root, build_object_index, current_source_status,
    find_cached_index, linked_delivery_findings, object_comments,
    object_details, object_page, save_object_comment,
)

ROOT = Path(__file__).resolve().parents[1]

XML = '''<?xml version="1.0" encoding="UTF-8"?>
<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <systemID>ark-A</systemID><tittel>Kommunearkiv</tittel>
    <arkivdel>
      <systemID>part-A</systemID><tittel>2002–2012</tittel>
      <klassifikasjonssystem><klasse>
        <mappe xsi:type="saksmappe">
          <systemID>case-001</systemID><tittel>Vurdering av byggesak</tittel>
          <saksstatus>Under behandling</saksstatus>
          <registrering xsi:type="journalpost">
            <systemID>reg-001</systemID><registreringsID>2026/19-1</registreringsID>
            <journalstatus>Journalført</journalstatus>
            <tittel>Mottatt brev</tittel>
            <dokumentbeskrivelse><systemID>doc-1</systemID></dokumentbeskrivelse>
          </registrering>
          <registrering><systemID>reg-002</systemID><tittel>Intern merknad</tittel></registrering>
        </mappe>
      </klasse></klassifikasjonssystem>
    </arkivdel>
    <arkivdel>
      <systemID>part-B</systemID><tittel>2013–2026</tittel>
      <mappe><systemID>case-002</systemID><tittel>Kultur</tittel>
        <registrering><systemID>reg-003</systemID><tittel>Ferdig</tittel></registrering>
      </mappe>
    </arkivdel>
</arkiv>
'''


class A5ObjectIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.work = root / 'work'
        self.work.mkdir()
        self.source_dir = root / 'source'
        self.source_dir.mkdir()
        self.source = self.source_dir / 'arkivstruktur.xml'
        self.source.write_bytes(XML.encode('utf-8'))
        self.uid = '00000000-0000-4000-8000-000000000005'
        self.job = self.work / 'job.json'
        self.job.write_text(json.dumps({
            'file_type': 'dwm-work-job', 'job_uid': self.uid,
            'job': {'job_id': 'JOB-001', 'source_extraction': str(self.source_dir)},
        }), encoding='utf-8')
        folder = self.work / 'noark5_reports/depot_validation/JOB-001__run'
        folder.mkdir(parents=True)
        self.report_path = folder / 'depot_validation_report.json'
        self.report = {'report_type': 'noark5_depot_validation',
                       'delivery_validation': {'complete': True,
                           'source_sha256': sha256(self.source.read_bytes()).hexdigest()}}
        self._write_report()
        self.snapshot = SimpleNamespace(
            work=self.work, report_path=self.report_path, job_uid=self.uid,
            report=self.report, findings_complete=True, findings=(
                {'metadata_id': 'M053', 'object_id': 'reg-001',
                 'archive_part_id': 'part-A', 'message': 'Journalpost krever kontroll'},
                {'metadata_id': 'M053', 'object_id': 'reg-001',
                 'archive_part_id': 'part-B', 'message': 'Feil arkivdel'},
                {'metadata_id': 'M052', 'object_id': 'case-002',
                 'archive_part_id': 'part-B', 'message': 'Saksstatus til vurdering'},
            ))

    def _write_report(self):
        self.report_path.write_text(json.dumps(self.report, ensure_ascii=False), encoding='utf-8')

    @contextmanager
    def source_stub(self, path=None):
        fake = ModuleType('app.ks_xml_evidence_v023_a19')
        fake.resolve_source_xml = lambda _work, name: (self.source if path is None else None if path is False else path)
        with patch.dict(sys.modules, {'app.ks_xml_evidence_v023_a19': fake}):
            yield

    def indexed(self):
        with self.source_stub():
            return build_object_index(self.snapshot)

    def test_four_levels_are_real_objects_with_verified_source_and_paging(self):
        meta = self.indexed()
        self.assertTrue(meta['complete'])
        self.assertEqual(meta['source_binding'], 'work_sha256_verified')
        self.assertEqual(meta['row_count'], 8)
        self.assertEqual(meta['counts_by_kind'], {
            'arkiv': 1, 'arkivdel': 2, 'mappe': 2, 'registrering': 3,
        })
        root = object_page(self.snapshot, meta)
        self.assertEqual(root['total'], 1)
        archive = root['rows'][0]
        self.assertEqual(archive['native_id'], 'ark-A')
        self.assertEqual(archive['children'], 2)
        parts = object_page(self.snapshot, meta, parent_id=archive['id'], page_size=1)
        self.assertEqual(parts['pages'], 2)
        self.assertEqual(parts['rows'][0]['native_id'], 'part-A')
        second = object_page(self.snapshot, meta, parent_id=archive['id'], page_size=1, page=1)
        self.assertEqual(second['rows'][0]['native_id'], 'part-B')
        case = object_page(self.snapshot, meta, parent_id=parts['rows'][0]['id'])['rows'][0]
        self.assertEqual(case['native_id'], 'case-001')
        self.assertEqual(case['xsi_type'], 'saksmappe')
        self.assertEqual(case['status'], 'Under behandling')
        regs = object_page(self.snapshot, meta, parent_id=case['id'])
        self.assertEqual([x['native_id'] for x in regs['rows']], ['reg-001', 'reg-002'])
        self.assertEqual(regs['rows'][0]['xsi_type'], 'journalpost')
        self.assertEqual(regs['rows'][0]['fields']['registreringsID'], '2026/19-1')
        self.assertGreater(regs['rows'][0]['line'], 1)
        details = object_details(self.snapshot, meta, regs['rows'][0]['id'])
        self.assertEqual([x['kind'] for x in details['ancestors']],
                         ['arkiv', 'arkivdel', 'mappe'])
        self.assertEqual(details['children'], 0)  # documents are next stage

    def test_standard_xml_root_is_arkiv_not_the_filename(self):
        # Nasjonalarkivet's Noark 5 3.1/4.0/5.0 schema declares
        # xs:element name="arkiv" as the document root.
        self.assertIn(b'<arkiv xmlns=', self.source.read_bytes())
        meta = self.indexed()
        self.assertEqual(meta['counts_by_kind']['arkiv'], 1)
        self.assertEqual(object_page(self.snapshot, meta)['rows'][0]['native_id'],
                         'ark-A')

    def test_nested_archive_is_a_real_level_before_arkivdel(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur">
  <systemID>top-archive</systemID><tittel>Hovedarkiv</tittel>
  <arkiv><systemID>sub-archive</systemID><tittel>Underarkiv</tittel>
    <arkivdel><systemID>sub-part</systemID><tittel>Arkivdel</tittel>
      <mappe><systemID>sub-case</systemID><tittel>Sak</tittel>
        <registrering><systemID>sub-reg</systemID></registrering>
      </mappe>
    </arkivdel>
  </arkiv>
</arkiv>'''
        self.source.write_bytes(xml.encode('utf-8'))
        self.report['delivery_validation']['source_sha256'] = sha256(self.source.read_bytes()).hexdigest()
        self._write_report()
        meta = self.indexed()
        self.assertEqual(meta['row_count'], 5)
        self.assertEqual(meta['counts_by_kind']['arkiv'], 2)
        top = object_page(self.snapshot, meta)['rows'][0]
        sub = object_page(self.snapshot, meta, parent_id=top['id'])['rows'][0]
        self.assertEqual(sub['kind'], 'arkiv')
        self.assertEqual(sub['native_id'], 'sub-archive')
        part = object_page(self.snapshot, meta, parent_id=sub['id'])['rows'][0]
        self.assertEqual(part['native_id'], 'sub-part')
        case = object_page(self.snapshot, meta, parent_id=part['id'])['rows'][0]
        reg = object_page(self.snapshot, meta, parent_id=case['id'])['rows'][0]
        self.assertEqual([x['native_id'] for x in object_details(
            self.snapshot, meta, reg['id'])['ancestors']],
            ['top-archive', 'sub-archive', 'sub-part', 'sub-case'])

    def test_filename_mistaken_for_xml_root_is_rejected_without_cache(self):
        self.source.write_text(
            '<arkivstruktur><arkiv><systemID>x</systemID></arkiv></arkivstruktur>',
            encoding='utf-8')
        self.report['delivery_validation']['source_sha256'] = sha256(self.source.read_bytes()).hexdigest()
        self._write_report()
        with self.source_stub(), self.assertRaisesRegex(ObjectIndexError, 'forventer <arkiv>'):
            build_object_index(self.snapshot)
        self.assertEqual(list((self.work / INDEX_DIR).glob('*.json')), [])
        self.assertEqual(list((self.work / INDEX_DIR).glob('*.sqlite')), [])

    def test_search_is_only_on_the_selected_parent_and_is_casefolded(self):
        meta = self.indexed()
        archive = object_page(self.snapshot, meta)['rows'][0]
        part_a = object_page(self.snapshot, meta, parent_id=archive['id'])['rows'][0]
        case = object_page(self.snapshot, meta, parent_id=part_a['id'])['rows'][0]
        match = object_page(self.snapshot, meta, parent_id=case['id'], search='JOURNALFØRT')
        self.assertEqual([item['native_id'] for item in match['rows']], ['reg-001'])
        self.assertEqual(object_page(self.snapshot, meta, parent_id=part_a['id'],
                                     search='reg-001')['total'], 0)

    def test_verified_identity_links_only_exact_delivery_findings(self):
        meta = self.indexed()
        archive = object_page(self.snapshot, meta)['rows'][0]
        part_a = object_page(self.snapshot, meta, parent_id=archive['id'])['rows'][0]
        case = object_page(self.snapshot, meta, parent_id=part_a['id'])['rows'][0]
        reg = object_page(self.snapshot, meta, parent_id=case['id'])['rows'][0]
        result = linked_delivery_findings(self.snapshot, meta, reg['id'])
        self.assertTrue(result['complete'])
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(result['rows'][0]['archive_part_id'], 'part-A')

    def test_duplicate_system_id_never_creates_cross_object_finding_match(self):
        xml = XML.replace('<systemID>reg-003</systemID>', '<systemID>reg-001</systemID>')
        self.source.write_bytes(xml.encode('utf-8'))
        self.report['delivery_validation']['source_sha256'] = sha256(self.source.read_bytes()).hexdigest()
        self._write_report()
        meta = self.indexed()
        archive = object_page(self.snapshot, meta)['rows'][0]
        part_a = object_page(self.snapshot, meta, parent_id=archive['id'])['rows'][0]
        case = object_page(self.snapshot, meta, parent_id=part_a['id'])['rows'][0]
        reg = object_page(self.snapshot, meta, parent_id=case['id'])['rows'][0]
        result = linked_delivery_findings(self.snapshot, meta, reg['id'])
        self.assertFalse(result['complete'])
        self.assertFalse(object_details(self.snapshot, meta, reg['id'])['id_is_unique'])

    def test_unknown_source_hash_is_not_claimed_as_verified_evidence(self):
        self.report['delivery_validation']['complete'] = False
        self._write_report()
        meta = self.indexed()
        self.assertEqual(meta['source_binding'], 'current_source_only')
        root = object_page(self.snapshot, meta)['rows'][0]
        self.assertFalse(linked_delivery_findings(self.snapshot, meta, root['id'])['complete'])

    def test_mismatched_source_sha_fails_closed_without_partial_index(self):
        self.report['delivery_validation']['source_sha256'] = 'f' * 64
        self._write_report()
        with self.source_stub(), self.assertRaisesRegex(ObjectIndexError, 'SHA-256'):
            build_object_index(self.snapshot)
        folder = self.work / INDEX_DIR
        self.assertEqual(list(folder.glob('*.json')), [])
        self.assertEqual(list(folder.glob('*.sqlite')), [])

    def test_report_revision_change_invalidates_index_and_cache(self):
        meta = self.indexed()
        self.report['extra'] = 'changed'
        self._write_report()
        with self.assertRaises(ObjectIndexError):
            object_page(self.snapshot, meta)
        with self.source_stub():
            self.assertIsNone(find_cached_index(self.snapshot))

    def test_changed_source_prevents_cache_reuse(self):
        meta = self.indexed()
        self.source.write_bytes(self.source.read_bytes() + b'  ')
        with self.source_stub():
            self.assertIsNone(find_cached_index(self.snapshot))
            self.assertIn('endret', current_source_status(self.snapshot, meta))

    def test_disconnected_source_cannot_be_mistaken_for_live_evidence(self):
        meta = self.indexed()
        with self.source_stub(path=False):
            cached = find_cached_index(self.snapshot)
            self.assertEqual(cached, meta)
            self.assertIn('frakoblet', current_source_status(self.snapshot, cached))
            self.assertEqual(build_object_index(self.snapshot), meta)
            self.assertEqual(object_page(self.snapshot, meta)['total'], 1)

    def test_broken_xml_and_cancellation_do_not_publish_results(self):
        self.source.write_text('<arkiv><arkivdel></arkiv>', encoding='utf-8')
        self.report['delivery_validation']['source_sha256'] = sha256(self.source.read_bytes()).hexdigest()
        self._write_report()
        with self.source_stub(), self.assertRaises(ObjectIndexError):
            build_object_index(self.snapshot)
        self.assertFalse(list((self.work / INDEX_DIR).glob('*.json')))
        self.assertFalse(list((self.work / INDEX_DIR).glob('*.sqlite')))
        with self.source_stub(), self.assertRaisesRegex(ObjectIndexError, 'avbrutt'):
            build_object_index(self.snapshot, cancelled=lambda: True)

    def test_modified_sqlite_is_not_accepted_for_a_new_page(self):
        meta = self.indexed()
        database = self.work / meta['index_relative_path']
        with database.open('ab') as out:
            out.write(b'unexpected extra bytes')
        with self.assertRaisesRegex(ObjectIndexError, 'endret'):
            object_page(self.snapshot, meta)

    def test_symlink_index_directory_is_never_written(self):
        outside = self.work.parent / 'outside'
        outside.mkdir()
        link = self.work / 'noark5_evidence'
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Symlinks ikke støttet av denne Windows-brukeren')
        with self.source_stub(), self.assertRaisesRegex(ObjectIndexError, 'Utrygg'):
            build_object_index(self.snapshot)
        self.assertEqual(list(outside.iterdir()), [])

    def test_missing_qt_uid_recovers_only_from_exact_work_and_report_manifest(self):
        # In a2 the GUI may open this report without passing a job_uid.
        # The persisted Work UID is authoritative only when the report
        # manifest and the selected JOB-ID confirm that same Work job.
        manifest = self.report_path.parent / 'artifact_manifest.json'
        manifest.write_text(json.dumps({'job_uid': self.uid, 'job_id': 'JOB-001'}),
                            encoding='utf-8')
        old = SimpleNamespace(**{**self.snapshot.__dict__,
                                 'job_uid': '', 'job_id': 'JOB-001'})
        self.assertEqual(_root(old)[2], self.uid)
        with self.source_stub():
            meta = build_object_index(old)
        self.assertEqual(meta['job_uid'], self.uid)
        self.assertEqual(object_page(old, meta)['total'], 1)

    def test_missing_uid_without_manifest_is_not_guessed(self):
        old = SimpleNamespace(**{**self.snapshot.__dict__,
                                 'job_uid': '', 'job_id': 'JOB-001'})
        with self.assertRaisesRegex(ObjectIndexError, 'jobbmanifest'):
            _root(old)
        self.assertFalse((self.work / INDEX_DIR).exists())

    def test_missing_uid_with_foreign_manifest_or_job_id_is_rejected(self):
        manifest = self.report_path.parent / 'artifact_manifest.json'
        manifest.write_text(json.dumps({'job_uid': 'foreign', 'job_id': 'JOB-001'}),
                            encoding='utf-8')
        old = SimpleNamespace(**{**self.snapshot.__dict__,
                                 'job_uid': '', 'job_id': 'JOB-001'})
        with self.assertRaisesRegex(ObjectIndexError, 'jobbmanifest'):
            _root(old)
        manifest.write_text(json.dumps({'job_uid': self.uid, 'job_id': 'JOB-001'}),
                            encoding='utf-8')
        wrong_local = SimpleNamespace(**{**old.__dict__, 'job_id': 'JOB-002'})
        with self.assertRaisesRegex(ObjectIndexError, 'JOB-ID'):
            _root(wrong_local)

    def test_nonempty_conflicting_uid_still_fails_closed(self):
        foreign = SimpleNamespace(**{**self.snapshot.__dict__,
                                     'job_uid': 'different-job-uid'})
        with self.assertRaisesRegex(ObjectIndexError, 'forskjellige jobbidentiteter'):
            _root(foreign)

    def test_wrong_job_and_unsafe_queries_are_rejected(self):
        wrong = SimpleNamespace(**{**self.snapshot.__dict__, 'job_uid': 'OTHER'})
        with self.source_stub(), self.assertRaises(ObjectIndexError):
            build_object_index(wrong)
        meta = self.indexed()
        with self.assertRaises(ObjectIndexError):
            object_page(self.snapshot, meta, page_size=10000)
        with self.assertRaises(ObjectIndexError):
            object_page(self.snapshot, meta, parent_id=999999)
        with self.assertRaises(ObjectIndexError):
            object_page(self.snapshot, {**meta, 'index_relative_path': '../../wrong.sqlite'})

    def test_large_registration_list_is_fully_indexed_and_sidewise_filtered(self):
        xml = ('<arkiv><systemID>a</systemID><arkivdel>'
               '<systemID>p</systemID><mappe><systemID>m</systemID>'
               + ''.join(f'<registrering><systemID>r-{i:04d}</systemID>'
                         f'<tittel>Journal {i:04d}</tittel></registrering>'
                         for i in range(3500))
               + '</mappe></arkivdel></arkiv>')
        self.source.write_bytes(xml.encode('utf-8'))
        self.report['delivery_validation']['source_sha256'] = sha256(self.source.read_bytes()).hexdigest()
        self._write_report()
        progress = []
        with self.source_stub():
            meta = build_object_index(self.snapshot, progress=progress.append)
        self.assertEqual(meta['counts_by_kind']['registrering'], 3500)
        self.assertGreaterEqual(len(progress), 3)
        self.assertEqual(progress[-1], meta['row_count'])
        archive = object_page(self.snapshot, meta)['rows'][0]
        part = object_page(self.snapshot, meta, parent_id=archive['id'])['rows'][0]
        case = object_page(self.snapshot, meta, parent_id=part['id'])['rows'][0]
        page = object_page(self.snapshot, meta, parent_id=case['id'], page_size=100, page=34)
        self.assertEqual(page['total'], 3500)
        self.assertEqual(len(page['rows']), 100)
        self.assertEqual(page['rows'][0]['native_id'], 'r-3400')
        self.assertEqual(object_page(self.snapshot, meta, parent_id=case['id'],
                                     search='r-2499')['total'], 1)

    def test_modification_during_indexing_cannot_publish_partial_cache(self):
        xml = ('<arkiv><arkivdel><mappe>'
               + '<registrering><systemID>x</systemID></registrering>' * 2500
               + '</mappe></arkivdel></arkiv>')
        self.source.write_bytes(xml.encode('utf-8'))
        self.report['delivery_validation']['source_sha256'] = sha256(self.source.read_bytes()).hexdigest()
        self._write_report()
        changes = []
        def mutate(n):
            if not changes:
                changes.append(n)
                with self.source.open('ab') as out:
                    out.write(b' changed')
        with self.source_stub(), self.assertRaisesRegex(ObjectIndexError, 'Source'):
            build_object_index(self.snapshot, progress=mutate)
        self.assertTrue(changes)
        self.assertEqual(list((self.work / INDEX_DIR).glob('*.json')), [])
        self.assertEqual(list((self.work / INDEX_DIR).glob('*.sqlite')), [])

    def test_source_and_report_bytes_unchanged_and_cache_is_stable(self):
        before_source = self.source.read_bytes()
        before_report = self.report_path.read_bytes()
        meta = self.indexed()
        with self.source_stub():
            again = build_object_index(self.snapshot)
        self.assertEqual(meta, again)
        self.assertEqual(self.source.read_bytes(), before_source)
        self.assertEqual(self.report_path.read_bytes(), before_report)
        self.assertTrue((self.work / meta['index_relative_path']).is_file())

    def test_object_comments_use_same_work_ledger_with_structural_identity(self):
        meta = self.indexed()
        obj = object_page(self.snapshot, meta)['rows'][0]
        fake = ModuleType('noark5_workflow.analysis.depot_annotations')
        seen = {}

        def save(path, **kwargs):
            seen['saved'] = (path, kwargs)
            return {'annotation_id': 'a5-1'}

        def read(path, **kwargs):
            seen['read'] = (path, kwargs)
            return [{'text': 'For undersøking'}]

        fake.record_depot_annotation = save
        fake.list_depot_annotations = read
        with patch.dict(sys.modules, {
            'noark5_workflow': ModuleType('noark5_workflow'),
            'noark5_workflow.analysis': ModuleType('noark5_workflow.analysis'),
            'noark5_workflow.analysis.depot_annotations': fake,
        }):
            result = save_object_comment(self.snapshot, meta, obj['id'],
                                         text='For undersøking', kind='question', user=object())
            comments = object_comments(self.snapshot, meta, obj['id'])
        self.assertEqual(result['annotation_id'], 'a5-1')
        self.assertEqual(comments[0]['text'], 'For undersøking')
        self.assertEqual(seen['saved'][1]['view_id'], 'analysis')
        self.assertEqual(seen['saved'][1]['target_type'], 'noark5_object')
        self.assertEqual(seen['saved'][1]['target_id'], seen['read'][1]['target_id'])
        self.assertEqual(self.report_path.read_bytes(), json.dumps(self.report, ensure_ascii=False).encode('utf-8'))


class A5WiringTests(unittest.TestCase):
    def test_maintains_complete_a4_gui_and_installs_a5_after_a4(self):
        path = ROOT / 'gui_qt/__main__.py'
        source = path.read_text(encoding='utf-8')
        ast.parse(source)
        self.assertLess(source.index('install_analysis_workspace_v4(window)'),
                        source.index('install_analysis_workspace_v5(window)'))
        self.assertIn("if hasattr(window, '_toolbar'):", source)
        new = (ROOT / 'gui_qt/noark_object_browser_v027_a5.py').read_text(encoding='utf-8')
        ast.parse(new)
        self.assertIn('AnalysisWorkspaceDialogV5(AnalysisWorkspaceDialogV4)', new)
        self.assertIn('window._analysis_dialog_class = AnalysisWorkspaceDialogV5', new)
        self.assertIn('QThread', new)
        self.assertIn('QTimer.singleShot(0, self._start)', new)
        self.assertNotIn('QMessageBox.question(', new)
        self.assertIn('classic', new.lower())

    def test_runtime_and_distribution_version_are_consistent_without_alpha_lock(self):
        import tomllib
        from version import VERSION
        with (ROOT / 'pyproject.toml').open('rb') as reader:
            distribution = tomllib.load(reader)['project']['version']
        self.assertEqual(distribution, VERSION.replace('-a', 'a'))
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.7', 5)


if __name__ == '__main__':
    unittest.main()
