"""Permanent regression tests for safe multi-extraction discovery and Work choices."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.noark5_batch_discovery_v027_a11 import (
    Candidate, assign_work, discover, extraction_id, info_xml_candidates,
    rejected_sip_packages, resolve_info_xml, work_folder_alternatives,
    work_target_state,
)

ROOT = Path(__file__).resolve().parents[1]


class BatchDiscoveryA13Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / '1525'
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def package(self, number: str, *, valid: bool = True, docs: str = 'DOKUMENT') -> Path:
        package = self.root / f'1525_{number}_E-1525-2025-0001'
        source = package / 'content' / 'sip' / 'content'
        source.mkdir(parents=True)
        if valid:
            (source / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
            (source / docs).mkdir()
        return package

    def test_j19_003_rejected_004_to_006_accepted(self):
        excluded = self.package('003', valid=False)
        legacy = excluded / 'content' / '_work' / 'n5-u-dok'
        legacy.mkdir(parents=True)
        (legacy / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
        self.package('004')
        self.package('005', docs='dokumenter')
        self.package('006')
        found = discover(self.root)
        self.assertEqual([extraction_id(candidate) for candidate in found],
                         ['1525_004', '1525_005', '1525_006'])
        self.assertTrue(all(candidate.source.parts[-3:] == ('content', 'sip', 'content')
                            for candidate in found))
        rejected = rejected_sip_packages(self.root, found)
        self.assertEqual(len(rejected), 1)
        self.assertTrue(rejected[0][0].startswith('1525_003'))
        self.assertIn('DOKUMENT/dokumenter', rejected[0][1])

    def test_xml_in_work_or_without_document_folder_does_not_qualify(self):
        package = self.package('003', valid=False)
        misplaced = package / 'content' / '_work' / 'n5-u-dok'
        misplaced.mkdir(parents=True)
        (misplaced / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
        (misplaced / 'DOKUMENT').mkdir()
        sip = package / 'content' / 'sip' / 'content'
        (sip / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
        self.assertEqual(discover(self.root), ())
        self.assertIn('DOKUMENT/dokumenter', rejected_sip_packages(self.root, ())[0][1])

    def test_prefixed_info_xml_is_resolved_from_each_package_root(self):
        for number in ('004', '005', '006'):
            package = self.package(number)
            (package / f'1525_{number}_specific-uuid_info.xml').write_text('<info/>', encoding='utf-8')
        candidates = discover(self.root)
        for candidate in candidates:
            info = resolve_info_xml(candidate)
            self.assertIsNotNone(info)
            self.assertTrue(info.name.startswith(extraction_id(candidate)))
            self.assertEqual(len(info_xml_candidates(candidate)), 1)

    def test_unqualified_external_info_is_not_assigned_to_three_packages(self):
        for number in ('004', '005', '006'):
            self.package(number)
        info_root = self.root / 'external'
        info_root.mkdir()
        (info_root / 'info.xml').write_text('<info/>', encoding='utf-8')
        found = discover(self.root)
        self.assertTrue(all(resolve_info_xml(candidate, info_root) is None for candidate in found))
        (info_root / '1525_005_example_info.xml').write_text('<info/>', encoding='utf-8')
        match = {extraction_id(candidate): resolve_info_xml(candidate, info_root)
                 for candidate in found}
        self.assertIsNotNone(match['1525_005'])
        self.assertIsNone(match['1525_004'])
        self.assertIsNone(match['1525_006'])

    def test_ambiguous_info_requires_manual_choice(self):
        package = self.package('004')
        (package / 'info.xml').write_text('<a/>', encoding='utf-8')
        (package / '1525_004_abc_info.xml').write_text('<b/>', encoding='utf-8')
        candidate = discover(self.root)[0]
        self.assertEqual(len(info_xml_candidates(candidate)), 2)
        self.assertIsNone(resolve_info_xml(candidate))

    def test_alternative_dwm_names_and_per_package_planning(self):
        first = self.package('004')
        second = self.package('005')
        third = self.package('006')
        operations = first / 'repository_operations'
        (operations / 'dwm2' / 'a01').mkdir(parents=True)
        (operations / 'dwm2' / 'a01' / 'job.json').write_text('{}', encoding='utf-8')
        (operations / 'dwm4').mkdir()
        (operations / 'abstract').mkdir()
        (operations / 'customWork' / 'a11').mkdir(parents=True)
        (operations / 'customWork' / 'a11' / 'job.json').write_text('{}', encoding='utf-8')
        alternatives = work_folder_alternatives(first, 'dwm')
        self.assertEqual(alternatives, ('customWork', 'dwm2', 'dwm4'))
        found = discover(self.root)
        overrides = {candidate.source: 'dwm4' for candidate in found}
        plan = assign_work(found, dwm_folder='dwm', run_folder='a01', folder_overrides=overrides)
        # Windows TemporaryDirectory can use an 8.3 path; discover() expands it.
        # Compare canonical paths, not two spellings of the same directory.
        self.assertEqual([plan[c.source] for c in found], [
            pkg.resolve(strict=True) / 'repository_operations' / 'dwm4' / 'a01'
            for pkg in (first, second, third)
        ])
        self.assertTrue(all(not path.exists() for path in plan.values()))
        self.assertEqual(work_target_state(operations / 'dwm2' / 'a01'), 'occupied')
        self.assertEqual(work_target_state(operations / 'dwm4' / 'a01'), 'new')

    def test_new_and_empty_work_are_distinct(self):
        candidate = self.package('004')
        planned = candidate / 'repository_operations' / 'dwm' / 'a01'
        self.assertEqual(work_target_state(planned), 'new')
        planned.mkdir(parents=True)
        self.assertEqual(work_target_state(planned), 'empty')
        (planned / 'something.log').write_text('saved', encoding='utf-8')
        self.assertEqual(work_target_state(planned), 'occupied')

    def test_symlinked_dwm_parent_is_blocked(self):
        package = self.package('004')
        operations = package / 'repository_operations'
        operations.mkdir()
        foreign = self.root / 'foreign'
        foreign.mkdir()
        alias = operations / 'dwm'
        try:
            alias.symlink_to(foreign, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Directory symlinks are not permitted on this system')
        self.assertEqual(work_target_state(alias / 'a01'), 'blocked')

    def test_gui_exposes_directory_drop_and_explicit_work_selection(self):
        text = (ROOT / 'gui_qt' / 'batch_discovery_v027_a11.py').read_text(encoding='utf-8')
        for token in ('class DirectoryDropEdit', 'def dropEvent',
                      'class WorkFolderChoiceDialog', 'repeat_choice',
                      'work_target_state', 'info_xml_candidates',
                      "'Uttrekk'", "'DWM-mappe'", 'rejected_sip_packages'):
            self.assertIn(token, text)


if __name__ == '__main__':
    unittest.main()
