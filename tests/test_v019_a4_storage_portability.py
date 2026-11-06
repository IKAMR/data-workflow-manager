"""v0.1.9-a4: root-relative storage moves without changing source evidence.

Uses only small synthetic Work/Source trees. No network drive or GUI required.
"""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4

from app.application_api import DwmApiError
from app.storage_portability_v019_a4 import (
    PORTABLE_FILE, apply_root_rebase, preview_root_rebase,
    rebase_storage_path,
)
from noark5_workflow.core.job import Job, JobBatch, JobStatus
from noark5_workflow.core.work_job_store import WorkJobStore

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchFixture:
    """Narrow real-Work test adapter; a3 relink operates on these methods."""
    def __init__(self, job, manifest):
        self._guard = threading.Lock()
        self._batch = JobBatch()
        self._batch.add(job)
        self._work_references = {job.job_id: manifest}
        self._unavailable_work_ids = frozenset()
        self._active_job_id = job.job_id
        self._path = manifest.parent.parent / 'lists' / 'jobs.n5jobs'
        self._dirty = False
        self._running = False
        self.events = []

    def _assert_idle(self):
        if self._running:
            raise DwmApiError('Kjøring pågår')

    def _require_job(self, job_id):
        found = self._batch.get(job_id)
        if found is None:
            raise DwmApiError('Ukjent jobb')
        return found

    def _view(self, job, position):
        return SimpleNamespace(job_id=job.job_id, name=job.name,
                               status=job.status.value, progress=job.progress,
                               effective_work_operations=str(self._work_references[job.job_id].parent))

    def _emit(self, kind, job=None, *, message='', progress=None):
        self.events.append((kind, message))


class PortableStorageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.old = self.folder / 'drive-old'
        self.new = self.folder / 'drive-new'
        self.package = self.old / 'package-001'
        self.source = self.package / 'content' / 'sip' / 'content'
        self.source.mkdir(parents=True)
        (self.source / 'info.xml').write_text('<info>same-source</info>', encoding='utf-8')
        (self.source / 'unchanged.xml').write_text('<archive/>', encoding='utf-8')
        self.work = self.package / 'repository_operations' / 'dwm'
        self.work.mkdir(parents=True)
        self.aip = self.package / 'aip'
        self.aip.mkdir()
        self.job = Job(
            job_id='JOB-001', name='Uttrekk 001', profile_id='noark5',
            source_root=self.package, source_extraction=self.source,
            work_root=self.package, work_content=self.package / 'content',
            work_operations=self.work.parent, archive_root=self.aip,
            output_root=self.aip, workflow_ids=['metadata_inventory'],
        )
        self.job.job_uid = str(uuid4())
        self.job.status = JobStatus.OK
        self.job.progress = 1.0
        self.job.next_operation_index = 1
        ref = WorkJobStore(self.work).write(self.job, event_kind='run.finished')
        self.api = WorkbenchFixture(self.job, ref)

    def _move(self):
        self.old.rename(self.new)
        return self.new / 'package-001' / 'repository_operations' / 'dwm'

    def test_windows_root_relative_mapping_is_boundary_aware(self):
        self.assertEqual(
            rebase_storage_path(r'D:\arkiv\uttrekk\info.xml', r'D:\arkiv', r'F:\arkiv'),
            (r'F:\arkiv\uttrekk\info.xml', 'uttrekk/info.xml'),
        )
        self.assertIsNone(rebase_storage_path(r'D:\arkiver\file', r'D:\arkiv', r'F:\arkiv'))
        self.assertIsNone(rebase_storage_path(r'G:\arkiv\file', r'D:\arkiv', r'F:\arkiv'))
        self.assertEqual(rebase_storage_path(r'D:\info', 'D:\\', 'F:\\'), (r'F:\info', 'info'))

    def test_windows_short_and_long_parent_alias_survive_second_rebase(self):
        # The historical a3 Work relink normalizes the 8.3 parent name in
        # job.json.  A later preview may receive an offline old root written
        # with its original short parent name. This simulates Windows even
        # when the test suite itself runs on Linux.
        short = r'C:\Users\TORBJO~1.AAS\AppData\Local\Temp\tmp001\drive-new'
        long = (r'C:\Users\torbjorn.aasen\AppData\Local\Temp\tmp001'
                r'\drive-new\package-001\repository_operations\dwm\job.json')
        destination = r'C:\Users\TORBJO~1.AAS\AppData\Local\Temp\tmp001\drive-third'

        def expand_existing_short_parent(value):
            return PureWindowsPath(str(value).replace('TORBJO~1.AAS', 'torbjorn.aasen'))

        with patch('app.storage_portability_v019_a4._windows_canonical',
                   side_effect=expand_existing_short_parent):
            target = rebase_storage_path(long, short, destination)
            self.assertEqual(target, (
                destination + r'\package-001\repository_operations\dwm\job.json',
                'package-001/repository_operations/dwm/job.json',
            ))
            # An unrelated account/root must never be relinked by alias logic.
            unrelated = long.replace('torbjorn.aasen', 'different.account')
            self.assertIsNone(rebase_storage_path(unrelated, short, destination))

    def test_a3_work_operations_suffix_survives_windows_83_alias(self):
        # After a real root move, an a3 Work reference may be canonical-long
        # but the saved work_operations role still uses the old 8.3 spelling.
        # Do not produce a new root from a guessed or unrelated suffix.
        from app.job_connections_v019_a3 import _suffix_after_base
        old_ref_root = Path('/temp/long-parent/drive-new/package/repository_operations/dwm')
        base_short = Path('/temp/short-parent/drive-new/package/repository_operations')
        self.assertIsNone(_suffix_after_base(old_ref_root, base_short))

        def expand_parent(value):
            return Path(str(value).replace('short-parent', 'long-parent'))

        with patch('app.job_connections_v019_a3._canonical_work_path',
                   side_effect=expand_parent):
            self.assertEqual(_suffix_after_base(old_ref_root, base_short), Path('dwm'))
            different_base = Path('/temp/another-user/drive-new/package/repository_operations')
            self.assertIsNone(_suffix_after_base(old_ref_root, different_base))

    def test_unknown_and_unsafe_root_stops_before_mutation(self):
        self.new.mkdir()
        for old in ('', '../relative', str(self.old / '..')):
            with self.subTest(old=old), self.assertRaises(DwmApiError):
                preview_root_rebase(self.api, old, self.new)
        with self.assertRaises(DwmApiError):
            preview_root_rebase(self.api, self.old, self.old)
        with self.assertRaises(DwmApiError):
            preview_root_rebase(self.api, self.old, self.old / 'nested')

    def test_preview_uses_relative_roles_without_writing_work(self):
        moved_work = self._move()
        before = {p.name: p.read_bytes() for p in moved_work.iterdir() if p.is_file()}
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertFalse(plan.errors, plan.errors)
        self.assertEqual(len(plan.jobs), 1)
        self.assertGreaterEqual(plan.role_count, 6)
        roles = {role.field: role for role in plan.jobs[0].roles}
        self.assertEqual(roles['source_extraction'].relative, 'package-001/content/sip/content')
        self.assertEqual(roles['work_operations'].relative, 'package-001/repository_operations')
        self.assertEqual(roles['archive_root'].relative, 'package-001/aip')
        self.assertEqual(before, {p.name: p.read_bytes() for p in moved_work.iterdir() if p.is_file()})
        self.assertFalse(self.api._dirty)
        self.assertEqual(self.api._work_references['JOB-001'].parent.resolve(strict=False), self.work.resolve(strict=False))

    def test_confirmed_rebase_restores_complete_work_and_portable_bindings(self):
        moved_work = self._move()
        plan = preview_root_rebase(self.api, self.old, self.new)
        with self.assertRaises(DwmApiError):
            apply_root_rebase(self.api, plan)
        updated = apply_root_rebase(self.api, plan, consent=True)
        self.assertEqual(updated, ('JOB-001',))
        actual = WorkJobStore(moved_work).load()
        self.assertEqual(actual.job_uid, self.job.job_uid)
        self.assertEqual(actual.status, JobStatus.OK)
        self.assertEqual(actual.next_operation_index, 1)
        for field in ('source_root', 'source_extraction', 'work_root', 'work_content',
                      'work_operations', 'archive_root', 'output_root'):
            self.assertTrue(Path(getattr(actual, field)).resolve(strict=False).is_relative_to(self.new.resolve(strict=False)), field)
        self.assertTrue(self.api._dirty)
        self.assertTrue(self.api._work_references['JOB-001'].is_file())
        portable = json.loads((moved_work / PORTABLE_FILE).read_text(encoding='utf-8'))
        self.assertEqual(portable['job_uid'], actual.job_uid)
        self.assertEqual(portable['roots'][0]['roles']['source_extraction']['relative'],
                         'package-001/content/sip/content')
        self.assertEqual((self.new/'package-001/content/sip/content/unchanged.xml').read_text(), '<archive/>')
        self.assertFalse(self.old.exists())

    def test_rechecking_a_stale_preview_prevents_partial_writes(self):
        moved_work = self._move()
        plan = preview_root_rebase(self.api, self.old, self.new)
        manifest = moved_work / 'job.json'
        manifest.write_text(manifest.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaisesRegex(DwmApiError, 'endret'):
            apply_root_rebase(self.api, plan, consent=True)
        self.assertFalse(self.api._dirty)
        self.assertEqual(self.api._work_references['JOB-001'].parent.resolve(strict=False), self.work.resolve(strict=False))

    def test_unchanged_original_work_blocks_copy_as_relocation(self):
        shutil.copytree(self.old, self.new)
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertTrue(plan.errors)
        with self.assertRaises(DwmApiError):
            apply_root_rebase(self.api, plan, consent=True)
        self.assertTrue(self.work.exists())
        self.assertFalse((self.new/'package-001/repository_operations/dwm'/PORTABLE_FILE).exists())

    def test_wrong_work_uid_never_replaces_stored_identity(self):
        moved = self._move()
        p = moved / 'job.json'
        payload = json.loads(p.read_text(encoding='utf-8'))
        payload['job_uid'] = str(uuid4())
        p.write_text(json.dumps(payload), encoding='utf-8')
        preview = preview_root_rebase(self.api, self.old, self.new)
        self.assertTrue(preview.errors)
        self.assertFalse(self.api._dirty)

    def test_missing_new_source_blocks_entire_batch(self):
        moved = self._move()
        shutil.rmtree(self.new / 'package-001/content/sip/content')
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertTrue(any('Source' in s for s in plan.errors), plan.errors)
        with self.assertRaises(DwmApiError):
            apply_root_rebase(self.api, plan, consent=True)
        self.assertFalse((moved / PORTABLE_FILE).exists())

    def test_missing_aip_is_reported_but_never_created(self):
        self._move()
        shutil.rmtree(self.new / 'package-001/aip')
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertFalse(plan.errors, plan.errors)
        self.assertTrue(any('archive_root' in warning for warning in plan.warnings))
        apply_root_rebase(self.api, plan, consent=True)
        self.assertFalse((self.new / 'package-001/aip').exists())
        actual = WorkJobStore(self.new/'package-001/repository_operations/dwm').load()
        self.assertEqual(actual.archive_root.resolve(strict=False),
                         (self.new/'package-001/aip').resolve(strict=False))

    def test_active_source_or_aip_cannot_overlap_new_work(self):
        self.job.archive_root = self.work
        self.job.output_root = self.work
        WorkJobStore(self.work).write(self.job)
        self._move()
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertTrue(any('overlapper Work' in msg for msg in plan.errors), plan.errors)

    def test_storage_on_other_disk_remains_unmodified(self):
        external = self.folder / 'AIP-extern'
        external.mkdir()
        self.job.archive_root = external
        self.job.output_root = external
        WorkJobStore(self.work).write(self.job)
        moved = self._move()
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertNotIn('archive_root', [x.field for x in plan.jobs[0].roles])
        apply_root_rebase(self.api, plan, consent=True)
        recovered = WorkJobStore(moved).load()
        self.assertEqual(recovered.archive_root, external)
        self.assertEqual(recovered.output_root, external)

    def test_two_jobs_reconnect_from_one_root_with_independent_work(self):
        second_package = self.old / 'package-002'
        second_source = second_package / 'content' / 'sip' / 'content'
        second_source.mkdir(parents=True)
        (second_source / 'info.xml').write_text('<info>other-job</info>', encoding='utf-8')
        second_work = second_package / 'repository_operations' / 'dwm'
        second_work.mkdir(parents=True)
        second_aip = second_package / 'aip'
        second_aip.mkdir()
        second = Job(
            job_id='JOB-002', name='Uttrekk 002', profile_id='noark5',
            source_root=second_package, source_extraction=second_source,
            work_root=second_package, work_operations=second_work.parent,
            archive_root=second_aip, workflow_ids=['metadata_inventory'],
        )
        second.job_uid = str(uuid4())
        second.status = JobStatus.FAILED
        second_ref = WorkJobStore(second_work).write(second, event_kind='run.error')
        self.api._batch.add(second)
        self.api._work_references['JOB-002'] = second_ref
        self._move()
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertFalse(plan.errors, plan.errors)
        self.assertEqual(len(plan.jobs), 2)
        self.assertEqual(apply_root_rebase(self.api, plan, consent=True), ('JOB-001', 'JOB-002'))
        first_job = WorkJobStore(self.new/'package-001/repository_operations/dwm').load()
        second_job = WorkJobStore(self.new/'package-002/repository_operations/dwm').load()
        self.assertNotEqual(first_job.job_uid, second_job.job_uid)
        self.assertEqual(first_job.status, JobStatus.OK)
        self.assertEqual(second_job.status, JobStatus.FAILED)
        self.assertEqual(second_job.source_extraction.resolve(),
                         (self.new/'package-002/content/sip/content').resolve())

    def test_second_portable_root_move_keeps_previous_relative_record(self):
        self._move()
        first = preview_root_rebase(self.api, self.old, self.new)
        apply_root_rebase(self.api, first, consent=True)
        third = self.folder / 'drive-third'
        self.new.rename(third)
        second = preview_root_rebase(self.api, self.new, third)
        self.assertFalse(second.errors, second.errors)
        apply_root_rebase(self.api, second, consent=True)
        path = third / 'package-001/repository_operations/dwm' / PORTABLE_FILE
        contents = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(contents['roots']), 2)
        self.assertEqual(contents['roots'][-1]['current_root'], str(third))
        self.assertEqual(WorkJobStore(path.parent).load().job_uid, self.job.job_uid)

    def test_work_on_external_root_does_not_move_when_only_source_changes(self):
        external = self.folder / 'work-external' / 'repository_operations' / 'dwm'
        external.mkdir(parents=True)
        self.job.work_root = external.parent.parent
        self.job.work_operations = external.parent
        new_ref = WorkJobStore(external).write(self.job, event_kind='work.moved')
        self.api._work_references['JOB-001'] = new_ref
        self.old.rename(self.new)
        preview = preview_root_rebase(self.api, self.old, self.new)
        self.assertFalse(preview.errors, preview.errors)
        self.assertEqual(preview.jobs[0].work_manifest_before, preview.jobs[0].work_manifest_after)
        apply_root_rebase(self.api, preview, consent=True)
        self.assertEqual(self.api._work_references['JOB-001'], new_ref)
        job = WorkJobStore(external).load()
        self.assertTrue(job.source_extraction.is_relative_to(self.new))
        self.assertEqual(job.work_operations, external.parent)

    def test_source_info_xml_mismatch_is_blocking(self):
        self.new.mkdir()
        shutil.copytree(self.package, self.new / 'package-001')
        wrong = self.new / 'package-001/content/sip/content/info.xml'
        wrong.write_text('<info>different</info>', encoding='utf-8')
        # Old Work still exists, but metadata mismatch must also be visible.
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertTrue(any('info.xml' in e for e in plan.errors), plan.errors)

    def test_relative_portable_manifest_owner_is_checked(self):
        moved = self._move()
        path = moved / PORTABLE_FILE
        path.write_text(json.dumps({'file_type':'bad','job_uid':self.job.job_uid}), encoding='utf-8')
        plan = preview_root_rebase(self.api, self.old, self.new)
        self.assertTrue(any('oversikt' in e for e in plan.errors), plan.errors)

    def test_gui_remains_optional_and_uses_a3_recovery(self):
        source = (ROOT / 'gui_qt/main_window.py').read_text(encoding='utf-8')
        gui = (ROOT / 'gui_qt/storage_roots_v019_a4.py').read_text(encoding='utf-8')
        launcher = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        ast.parse(source)
        ast.parse(gui)
        self.assertIn('"Omkoble lagringsrot for flere jobber…"', source)
        self.assertIn('StorageRootsDialog', source)
        self.assertIn('app.workbench_api_v019_a4', launcher)
        self.assertIn('preview_storage_root_rebase', gui)
        self.assertIn('rebase_storage_root', gui)
        self.assertNotIn('customtkinter', gui)


if __name__ == '__main__':
    unittest.main()
