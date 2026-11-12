"""v0.1.13-a2: shared DIAS metadata and safe Basic wiring."""
from __future__ import annotations

import ast
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

from app.dias_info_v0113_a2 import (
    DIAS_LINK_LABEL_DELIVERYSPECIFICATION, candidate_info_xml,
    linked_values, original_evidence_path, persist_metadata, current_values,
)
from noark5_workflow.operations.dias_mets import METS_NS, build_submission_description
from noark5_workflow.reporting.depot_metadata import load_depot_metadata

ROOT = Path(__file__).resolve().parents[1]


class DiasMetadataTests(unittest.TestCase):
    def test_link_both_directions_and_no_mutation(self):
        source = {'label': 'A', 'archive_description': 'Old', 'recipient': 'IKAMR'}
        self.assertTrue(DIAS_LINK_LABEL_DELIVERYSPECIFICATION)
        linked = linked_values(source)
        self.assertEqual(linked['label'], 'A')
        self.assertEqual(linked['archive_description'], 'A')
        self.assertEqual(linked['recipient'], 'IKAMR')
        self.assertEqual(source['archive_description'], 'Old')
        self.assertEqual(linked_values(source, 'archive_description')['label'], 'Old')

    def test_original_preserved_and_working_copy_independent(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'Source'
            source.mkdir()
            original = source / 'info.xml'
            metadata = {
                'label': 'Mottatt LABEL',
                'archive_description': 'Mottatt LABEL',
                'submission_agreement': 'Avtale 2026',
                'archivist_org': 'Arkiv', 'submitter_org': 'Depot',
            }
            build_submission_description(metadata).write(original, encoding='utf-8', xml_declaration=True)
            before = original.read_bytes()
            work = base / 'Work'
            work.mkdir()
            job = SimpleNamespace(job_id='JOB-001', work_operations=work, work_root=work,
                                  source_extraction=source)
            result, working = persist_metadata(job, {**metadata, 'label': 'Ny LABEL'}, original)
            self.assertTrue(result.is_file())
            self.assertTrue(working.is_file())
            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(current_values(job)['label'], 'Ny LABEL')
            self.assertEqual(current_values(job)['archive_description'], 'Ny LABEL')
            self.assertEqual(ET.parse(working).getroot().get('LABEL'), 'Ny LABEL')
            stored = load_depot_metadata(job)
            self.assertEqual(len(stored['source_imports']), 1)
            preserved = original_evidence_path(job)
            self.assertIsNotNone(preserved)
            self.assertEqual(preserved.read_bytes(), before)
            self.assertNotEqual(preserved.resolve(), working.resolve())
            found = candidate_info_xml(source)
            self.assertIsNotNone(found)
            self.assertTrue(found.samefile(original))
            # An edit must not silently create a second source import.
            persist_metadata(job, {**metadata, 'label': 'Enda nyere'}, None)
            self.assertEqual(len(load_depot_metadata(job)['source_imports']), 1)
            self.assertEqual(original.read_bytes(), before)

    def test_startup_keeps_stable_qt_subclass(self):
        entry = (ROOT / 'gui_qt' / '__main__.py').read_text('utf-8')
        basic = (ROOT / 'gui_qt' / 'basic_main_v0113_a2.py').read_text('utf-8')
        ast.parse(entry)
        ast.parse(basic)
        self.assertIn('from gui_qt.basic_main_v0113_a2 import DwmMainWindow', entry)
        self.assertIn('class DwmMainWindow(_StableBasicWindow):', basic)
        self.assertNotIn('setattr(ResultCenterWindow', basic)
        self.assertIn('self._a2_save_metadata(job)', basic)
        self.assertIn('return super()._run_selected()', basic)


if __name__ == '__main__':
    unittest.main()
