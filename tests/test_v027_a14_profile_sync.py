"""a14: new batch jobs take the modern run profile; old job histories stay."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import ast
import unittest

from app.noark5_batch_discovery_v027_a11 import (
    Candidate, create_direct_work_job,
)
from app.run_profiles_v022_a8 import builtin_profiles


class NewBatchJobProfileA14Tests(unittest.TestCase):
    def test_modern_profiles_include_siegfried(self):
        profiles = builtin_profiles()
        for p in profiles:
            with self.subTest(profile=p.profile_id):
                self.assertIn('siegfried_pronom_identification', p.operation_ids)

    def test_batch_applies_explicit_workflow_before_work_registration(self):
        with TemporaryDirectory() as temporary:
            package = Path(temporary) / '1525_004'
            source = package / 'content' / 'sip' / 'content'
            source.mkdir(parents=True)
            target = package / 'repository_operations' / 'dwm' / 'a01'
            selected = next(p for p in builtin_profiles()
                            if p.profile_id == 'dwm_complete')
            class FakeApi:
                def __init__(self):
                    self.calls = []
                    self.settings = {}
                    self.job = SimpleNamespace(work_operations=target,
                                               effective_work_operations=target)
                def create_job(self, **_kwargs):
                    self.calls.append('create')
                    return SimpleNamespace(job_id='JOB-001')
                def update_storage(self, job_id, fields):
                    self.calls.append('storage')
                    self.job.work_operations = Path(fields['work_operations'])
                def set_workflow(self, job_id, ids):
                    self.calls.append(('workflow', tuple(ids)))
                def use_selected_work_directly(self, job_id):
                    self.calls.append('direct')
                def job_details(self, job_id):
                    return SimpleNamespace(job=self.job)
                def remove_job(self, job_id):
                    self.calls.append('remove')
            api = FakeApi()
            id_ = create_direct_work_job(api, Candidate(source, package), target,
                                         workflow_ids=selected.operation_ids)
            self.assertEqual(id_, 'JOB-001')
            self.assertEqual(api.calls[0], 'create')
            self.assertEqual(api.calls[1], ('workflow', selected.operation_ids))
            self.assertEqual(api.calls[2], 'storage')
            self.assertEqual(api.calls[3], 'direct')
            self.assertTrue(target.is_dir())

    def test_advanced_legacy_button_is_rewired_to_modern_picker(self):
        text = (Path(__file__).resolve().parents[1] / 'gui_qt' /
                'additional_subjobs_v027_a14.py').read_text(encoding='utf-8')
        ast.parse(text)
        self.assertIn('preset.clicked.disconnect()', text)
        self.assertIn('preset.clicked.connect(window._a8_choose_run_profile)', text)
        self.assertIn('run_additional_subjob(', text)


if __name__ == '__main__':
    unittest.main()
