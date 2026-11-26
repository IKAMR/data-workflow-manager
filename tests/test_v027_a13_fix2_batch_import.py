"""Regression for Basic's exact Work path and compact batch dialog."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.noark5_batch_discovery_v027_a11 import (
    assign_work, create_direct_work_job, discover, work_target_state,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeBasicAPI:
    def __init__(self, fail_at=None):
        self.jobs = {}
        self.fail_at = fail_at
        self.recorded = []

    def create_job(self, *, source_extraction, name, profile_id):
        self.recorded.append('create')
        job_id = f'JOB-{len(self.jobs)+1:03d}'
        self.jobs[job_id] = SimpleNamespace(
            source_extraction=Path(source_extraction),
            work_root=None, work_operations=None, name=name,
            profile_id=profile_id,
        )
        return SimpleNamespace(job_id=job_id)

    def update_storage(self, job_id, paths):
        self.recorded.append('storage')
        for key, value in paths.items():
            setattr(self.jobs[job_id], key, Path(value))

    def use_selected_work_directly(self, job_id):
        self.recorded.append('direct')
        job = self.jobs[job_id]
        # Reproduce the real Basic API guards, including the original failure.
        if job.work_root != job.work_operations:
            raise ValueError('Basic krever at valgt Work brukes direkte, uten ekstra nivåer.')
        if not job.work_operations.is_dir():
            raise ValueError('Work-mappen må eksistere.')
        if self.fail_at == job_id:
            raise RuntimeError('Simulert feil etter Work-oppsett')

    def job_details(self, job_id):
        return SimpleNamespace(job=self.jobs[job_id])

    def remove_job(self, job_id):
        self.recorded.append('rollback')
        self.jobs.pop(job_id, None)


class BasicBatchImportFixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / '1525'
        self.root.mkdir()
        for number in ('004', '005', '006'):
            pkg = self.root / f'1525_{number}_E-1525-2025-0001'
            source = pkg / 'content' / 'sip' / 'content'
            source.mkdir(parents=True)
            (source / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
            (source / 'DOKUMENT').mkdir()
        self.found = discover(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_three_jobs_import_in_direct_work_without_extra_folder(self):
        choices = {c.source: 'dwm' for c in self.found}
        mapping = assign_work(self.found, folder_overrides=choices, run_folder='a01')
        api = FakeBasicAPI()
        for candidate in self.found:
            job_id = create_direct_work_job(api, candidate, mapping[candidate.source])
            job = api.jobs[job_id]
            self.assertEqual(job.work_root, mapping[candidate.source])
            self.assertEqual(job.work_operations, mapping[candidate.source])
            self.assertTrue(job.work_operations.is_dir())
            self.assertEqual(work_target_state(job.work_operations), 'empty')
        self.assertEqual(len(api.jobs), 3)
        self.assertEqual(api.recorded, ['create', 'storage', 'direct'] * 3)

    def test_existing_old_work_is_unchanged(self):
        pkg = self.found[0].package_root
        previous = pkg / 'repository_operations' / 'dwm4' / 'a02'
        previous.mkdir(parents=True)
        (previous / 'job.json').write_text('existing job', encoding='utf-8')
        new_target = pkg / 'repository_operations' / 'dwm' / 'a01'
        api = FakeBasicAPI()
        create_direct_work_job(api, self.found[0], new_target)
        self.assertEqual((previous / 'job.json').read_text(encoding='utf-8'), 'existing job')
        self.assertTrue(new_target.is_dir())

    def test_occupied_work_is_blocked_before_creating_job(self):
        pkg = self.found[0].package_root
        occupied = pkg / 'repository_operations' / 'dwm' / 'a01'
        occupied.mkdir(parents=True)
        (occupied / 'job.json').write_text('old', encoding='utf-8')
        api = FakeBasicAPI()
        with self.assertRaises(ValueError):
            create_direct_work_job(api, self.found[0], occupied)
        self.assertEqual(api.jobs, {})
        self.assertEqual((occupied / 'job.json').read_text(encoding='utf-8'), 'old')

    def test_existing_empty_work_can_be_selected_directly(self):
        target = self.found[0].package_root / 'repository_operations' / 'dwm' / 'a01'
        target.mkdir(parents=True)
        api = FakeBasicAPI()
        create_direct_work_job(api, self.found[0], target)
        self.assertTrue(target.is_dir())
        self.assertEqual(len(api.jobs), 1)

    def test_failed_registration_rolls_back_new_empty_work_and_job(self):
        pkg = self.found[0].package_root
        target = pkg / 'repository_operations' / 'dwm' / 'a01'
        api = FakeBasicAPI(fail_at='JOB-001')
        with self.assertRaisesRegex(RuntimeError, 'Simulert'):
            create_direct_work_job(api, self.found[0], target)
        self.assertFalse(target.exists())
        self.assertEqual(api.jobs, {})
        self.assertEqual(api.recorded, ['create', 'storage', 'direct', 'rollback'])

    def test_failed_metadata_callback_removes_only_new_empty_work(self):
        target = self.found[0].package_root / 'repository_operations' / 'dwm' / 'a01'
        def raise_error(_):
            raise RuntimeError('metadata parse failed')
        api = FakeBasicAPI()
        with self.assertRaisesRegex(RuntimeError, 'metadata parse failed'):
            create_direct_work_job(api, self.found[0], target, on_created=raise_error)
        self.assertFalse(target.exists())
        self.assertFalse(api.jobs)

    def test_effective_nested_work_is_rejected_without_writing_metadata(self):
        target = self.found[0].package_root / 'repository_operations' / 'dwm' / 'a01'
        class NestedWorkAPI(FakeBasicAPI):
            def job_details(self, job_id):
                job = self.jobs[job_id]
                job.effective_work_operations = job.work_operations / 'extra'
                return SimpleNamespace(job=job)
        api = NestedWorkAPI()
        saved = []
        with self.assertRaisesRegex(ValueError, 'Effektiv Work'):
            create_direct_work_job(api, self.found[0], target,
                                   on_created=lambda _: saved.append(True))
        self.assertEqual(saved, [])
        self.assertEqual(api.jobs, {})
        self.assertFalse(target.exists())

    def test_gui_has_compact_multiline_rows_and_selection_buttons(self):
        gui = (ROOT / 'gui_qt' / 'batch_discovery_v027_a11.py').read_text(encoding='utf-8')
        self.assertIn('QTableWidget(0, 4)', gui)
        self.assertIn("'Source / info.xml', 'Work / status'", gui)
        self.assertIn("QPushButton('Velg alle')", gui)
        self.assertIn("QPushButton('Fjern alle')", gui)
        self.assertIn('self.table.setRowHeight(row, 68)', gui)
        self.assertIn("'work_root': str(target)", (ROOT / 'app' / 'noark5_batch_discovery_v027_a11.py').read_text(encoding='utf-8'))
        self.assertIn('create_direct_work_job(self.api, candidate, target', gui)


if __name__ == '__main__':
    unittest.main()
