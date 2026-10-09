from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from noark5_workflow.external_evidence import kdrs_query_selection as m


class KdrsSelections(unittest.TestCase):
    def test_explicit_choice_and_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            evidence = [{'observation_id': 'o1', 'value': 123, 'label': 'Mapper',
                         'line': 'Mapper: 123', 'source_sha256': 'abc',
                         'source_file': 'U1.txt', 'report_type': 'u01',
                         'archive_part_title': None, 'test_id': 'legacy.u01'}]
            with patch.object(m, 'candidates', return_value=evidence):
                m.set_choice(td, 'folder_count', 'o1')
                self.assertEqual(m.selected_count(td, 'folder_count'), 123)
                self.assertEqual(m.load_choices(td)['folder_count']['source_sha256'], 'abc')
            with patch.object(m, 'candidates', return_value=[]):
                self.assertIsNone(m.selected_count(td, 'folder_count'))

    def test_no_silent_archive_part_as_whole(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(m, 'candidates', return_value=[{
                'observation_id': 'part', 'value': 12, 'archive_part_title': 'A',
            }]):
                with self.assertRaises(ValueError):
                    m.set_choice(td, 'folder_count', 'part')
