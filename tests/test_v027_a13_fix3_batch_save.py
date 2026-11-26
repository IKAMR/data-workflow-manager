"""Fix3 regression: batch import -> active Simple job -> persistent joblist."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.noark5_batch_discovery_v027_a11 import (
    activate_batch_job_in_window, create_direct_work_job, discover,
    suggest_batch_joblist_path,
)
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]


class SavedJobsAPI:
    def __init__(self):
        self.jobs = {}
        self.selected = None
        self.saved_path = None

    def create_job(self, *, source_extraction, name, profile_id):
        job_id = 'JOB-%03d' % (len(self.jobs) + 1)
        self.jobs[job_id] = SimpleNamespace(
            source_extraction=Path(source_extraction),
            name=name, profile_id=profile_id,
            work_root=None, work_operations=None,
        )
        return SimpleNamespace(job_id=job_id)

    def update_storage(self, job_id, fields):
        for key, value in fields.items():
            setattr(self.jobs[job_id], key, Path(value))

    def use_selected_work_directly(self, job_id):
        job = self.jobs[job_id]
        assert job.work_root == job.work_operations
        assert job.work_root.is_dir()

    def job_details(self, job_id):
        return SimpleNamespace(job=self.jobs[job_id])

    def remove_job(self, job_id):
        self.jobs.pop(job_id)

    def select_job(self, job_id):
        assert job_id in self.jobs
        self.selected = job_id

    def save_job_list(self, path):
        result = Path(path)
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(json.dumps({
            'jobs': [{
                'id': job_id,
                'source': str(job.source_extraction),
                'work_root': str(job.work_root),
                'work_operations': str(job.work_operations),
            } for job_id, job in self.jobs.items()],
        }), encoding='utf-8')
        self.saved_path = result
        return result


class BasicWindow:
    def __init__(self, api):
        self.api = api
        self._active_id = None
        self._basic_job_id = None
        self._basic_active = True
        self._v022_draft = True
        self._v022_loading_job = False
        self._basic_selection_edited = False
        self._a2_pending_dirty = False
        self.source = ''
        self.work = ''
        self.refreshes = 0
        self.selection = None

    def _load_basic_active_job(self):
        job = self.api.job_details(self._active_id).job
        self.source = str(job.source_extraction)
        self.work = str(job.work_operations)

    def _refresh(self, *, force):
        assert force
        self.refreshes += 1

    def _v022_refresh_selector(self, *, force):
        assert force
        self.selection = self._active_id if not self._v022_draft else None

    def _a2_refresh_overview(self):
        pass

    def _sync_basic_status(self):
        pass


class BatchSaveFix3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / '1525'
        self.root.mkdir()
        for num in ('004', '005', '006'):
            content = (self.root / ('1525_' + num + '_E-1525-2025-0001') /
                       'content' / 'sip' / 'content')
            content.mkdir(parents=True)
            (content / 'DOKUMENT').mkdir()
            (content / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
        self.found = discover(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_common_joblist_suggestion_is_persistent_and_not_in_work(self):
        path = suggest_batch_joblist_path(
            self.found, search_root=self.root,
            dwm_folder='dwm', run_folder='a01', version=VERSION,
        )
        self.assertEqual(path.parent.resolve(strict=False),
                         (self.root / 'Jobblister').resolve(strict=False))
        self.assertEqual(path.name,
                         '1525_004-006_dwm_a01_v' + VERSION + '.n5jobs')
        self.assertFalse(path.parent.exists())

    def test_configured_joblist_dir_wins(self):
        chosen = self.root / 'Own-Joblist-Directory'
        path = suggest_batch_joblist_path(
            self.found, search_root=self.root, settings={'job_list_dir': str(chosen)},
            version=VERSION,
        )
        self.assertEqual(path.parent.resolve(strict=False),
                         chosen.resolve(strict=False))
        self.assertFalse(chosen.exists())

    def test_existing_list_does_not_get_suggested_for_overwriting(self):
        first = suggest_batch_joblist_path(self.found, search_root=self.root, version=VERSION)
        first.parent.mkdir()
        first.write_text('historical list', encoding='utf-8')
        second = suggest_batch_joblist_path(self.found, search_root=self.root, version=VERSION)
        self.assertEqual(second.stem, first.stem + '_2')
        self.assertEqual(first.read_text(encoding='utf-8'), 'historical list')

    def test_three_jobs_become_visible_and_remain_in_saved_joblist(self):
        api = SavedJobsAPI()
        for candidate in self.found:
            target = candidate.package_root / 'repository_operations' / 'dwm' / 'a01'
            create_direct_work_job(api, candidate, target)
        self.assertEqual(len(api.jobs), 3)
        window = BasicWindow(api)
        activate_batch_job_in_window(window, 'JOB-001')
        self.assertEqual(window._active_id, 'JOB-001')
        self.assertEqual(window._basic_job_id, 'JOB-001')
        self.assertFalse(window._v022_draft)
        self.assertEqual(window.selection, 'JOB-001')
        self.assertEqual(window.source, str(self.found[0].source))
        self.assertEqual(window.work, str(self.found[0].package_root / 'repository_operations' / 'dwm' / 'a01'))
        output = suggest_batch_joblist_path(self.found, search_root=self.root, version=VERSION)
        api.save_job_list(output)
        stored = json.loads(output.read_text(encoding='utf-8'))['jobs']
        self.assertEqual(len(stored), 3)
        for entry in stored:
            self.assertEqual(entry['work_root'], entry['work_operations'])
            self.assertTrue(Path(entry['work_operations']).is_dir())
            self.assertTrue(Path(entry['source']).is_dir())

    def test_activation_does_not_try_to_load_qt_basic_form_in_advanced_mode(self):
        api = SavedJobsAPI()
        candidate = self.found[0]
        create_direct_work_job(api, candidate,
                               candidate.package_root / 'repository_operations' / 'dwm' / 'a01')
        window = BasicWindow(api)
        window._basic_active = False
        window._load_basic_active_job = lambda: self.fail('Basic form loaded in Advanced mode')
        activate_batch_job_in_window(window, 'JOB-001')
        self.assertEqual(window._active_id, 'JOB-001')
        self.assertFalse(window._v022_draft)

    def test_gui_uses_direct_save_and_restores_basic_active_state(self):
        gui = (ROOT / 'gui_qt' / 'batch_discovery_v027_a11.py').read_text(encoding='utf-8')
        self.assertIn('activate_batch_job_in_window(self.window, created[0])', gui)
        self.assertIn('suggest_batch_joblist_path(', gui)
        self.assertIn('BatchJobListSaveDialog(suggestion, self)', gui)
        self.assertIn('self.api.save_job_list(target)', gui)
        self.assertNotIn('self.window._save()', gui)
        self.assertIn("'Ikke n\\u00e5'", gui)


if __name__ == '__main__':
    unittest.main()
