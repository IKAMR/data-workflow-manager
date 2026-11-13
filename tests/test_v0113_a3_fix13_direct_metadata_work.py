"""Regression: a Basic direct Work must not acquire another /dwm level."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.dias_info_v0113_a2 import _copy_misplaced_metadata, _direct_context, current_values
from noark5_workflow.core.work_paths import resolve_dwm_work_root, resolve_work_operations_base


class BasicDirectMetadataTests(unittest.TestCase):
    class Job:
        job_id = 'JOB-001'
        def __init__(self, work):
            self.work_operations = work
        def get_operation_params(self, key):
            return {'mode': 'selected'} if key == '__dwm_work_layout__' else {}

    def test_selected_direct_work_before_job_json_and_scoped_to_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / 'dwm2' / 'a03'
            work.mkdir(parents=True)
            job = self.Job(work)
            settings = {'app_work_subfolder': 'dwm'}
            self.assertEqual(resolve_dwm_work_root(work, settings=settings), work / 'dwm')
            with _direct_context(job):
                self.assertEqual(resolve_dwm_work_root(work, settings=settings), work)
                self.assertEqual(resolve_work_operations_base(work, settings=settings), work)
                other = Path(tmp) / 'another-work'
                self.assertEqual(resolve_dwm_work_root(other, settings=settings), other / 'dwm')
            self.assertEqual(resolve_dwm_work_root(work, settings=settings), work / 'dwm')

    def test_misplaced_metadata_copied_without_changing_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / 'dwm2' / 'a03'
            wrong = work / 'dwm' / 'metadata'
            original = wrong / 'source_evidence' / 'original.xml'
            original.parent.mkdir(parents=True)
            original.write_bytes(b'<source>Original</source>')
            (wrong / 'depot_metadata.json').write_text(json.dumps({
                'file_type': 'dwm-depot-metadata', 'job_id': 'JOB-001',
                'current': {'label': 'Verified source'}, 'source_imports': [],
            }), encoding='utf-8')
            job = self.Job(work)
            with patch('settings.load_config', return_value={'app_work_subfolder': 'dwm'}):
                self.assertEqual(current_values(job)['label'], 'Verified source')
                _copy_misplaced_metadata(job)
            target = work / 'metadata'
            self.assertEqual((target / 'source_evidence' / 'original.xml').read_bytes(), original.read_bytes())
            self.assertEqual((target / 'depot_metadata.json').read_bytes(), (wrong / 'depot_metadata.json').read_bytes())
            self.assertTrue(original.is_file())

    def test_do_not_steal_metadata_of_another_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            wrong = work / 'dwm' / 'metadata'
            wrong.mkdir(parents=True)
            (wrong / 'depot_metadata.json').write_text(json.dumps({
                'file_type': 'dwm-depot-metadata', 'job_id': 'JOB-OTHER',
            }), encoding='utf-8')
            with patch('settings.load_config', return_value={'app_work_subfolder': 'dwm'}):
                with self.assertRaises(ValueError):
                    _copy_misplaced_metadata(self.Job(work))
            self.assertFalse((work / 'metadata').exists())

    def test_existing_correct_metadata_must_not_be_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            correct = work / 'metadata'
            correct.mkdir()
            (correct / 'depot_metadata.json').write_text('correct', encoding='utf-8')
            wrong = work / 'dwm' / 'metadata'
            wrong.mkdir(parents=True)
            (wrong / 'depot_metadata.json').write_text('wrong', encoding='utf-8')
            with patch('settings.load_config', return_value={'app_work_subfolder': 'dwm'}):
                _copy_misplaced_metadata(self.Job(work))
            self.assertEqual((correct / 'depot_metadata.json').read_text(), 'correct')


if __name__ == '__main__':
    unittest.main()
