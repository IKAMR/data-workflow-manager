"""A10 regression tests. Pure contracts run without Qt or Windows installed."""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.run_display_v022_a10 import (
    ready_job_list, ready_label, readable_job_name, result_file_explanation,
)
from app.source_locator_v022_a10 import (
    find_source_candidates, source_within_info_parent, picker_start, is_info_xml,
)

ROOT = Path(__file__).resolve().parents[1]


class SourceLocatorA10Tests(unittest.TestCase):
    def test_both_real_info_xml_filename_forms(self):
        self.assertTrue(is_info_xml('info.xml'))
        self.assertTrue(is_info_xml('1525_004_96c7a0_info.xml'))
        self.assertFalse(is_info_xml('arkivstruktur.xml'))

    def test_only_matching_tree_and_never_last_job(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = root / '1525_004'
            second = root / '1525_006'
            path = first / '1525_004_info.xml'
            path.parent.mkdir()
            second.mkdir()
            path.write_text('<info/>', encoding='utf-8')
            target = first / 'content' / 'sip' / 'content'
            target.mkdir(parents=True)
            (target / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
            (second / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
            self.assertEqual(find_source_candidates(path), (target,))
            self.assertEqual(picker_start(path, home=second), first)
            self.assertTrue(source_within_info_parent(target, path))
            self.assertFalse(source_within_info_parent(second, path))

    def test_multiple_candidates_are_returned_without_choosing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            info = root / 'info.xml'
            info.write_text('<info/>', encoding='utf-8')
            for name in ('alpha', 'beta'):
                place = root / name
                place.mkdir()
                (place / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
            self.assertEqual({p.name for p in find_source_candidates(info)},
                             {'alpha','beta'})

    def test_limit_depth_excludes_distant_and_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            info = root / 'info.xml'
            info.write_text('<info/>', encoding='utf-8')
            shallow = root / 'content'
            shallow.mkdir()
            (shallow / 'arkivstruktur.xml').touch()
            deep = root / 'x' / 'y' / 'z'
            deep.mkdir(parents=True)
            (deep / 'arkivstruktur.xml').touch()
            work = root / 'repository_operations'
            work.mkdir()
            (work / 'arkivstruktur.xml').touch()
            self.assertEqual(find_source_candidates(info, max_depth=1), (shallow,))

    def test_invalid_context_returns_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'unknown.txt'
            p.write_text('x', encoding='utf-8')
            self.assertEqual(find_source_candidates(p), ())
            self.assertEqual(picker_start(p, home=folder), Path(folder))


class RunDisplayA10Tests(unittest.TestCase):
    @dataclass
    class Job:
        job_id: str
        name: str
        status: str

    def test_ready_count_follows_current_jobs(self):
        jobs = [self.Job('JOB-001','Arkiv A','Ferdig'),
                self.Job('JOB-002','Arkiv B','Klar'),
                self.Job('JOB-003','Arkiv C','Klar')]
        self.assertEqual(tuple(j.job_id for j in ready_job_list(jobs)),
                         ('JOB-002','JOB-003'))
        self.assertIn('(2)', ready_label(jobs))

    def test_results_are_file_counts_not_errors(self):
        self.assertIn('IKKE antall testfunn eller feil', result_file_explanation(0))
        self.assertIn('6 registrerte resultatfiler', result_file_explanation(6, 3))
        self.assertIn('tekniske loggadvarsler', result_file_explanation(6, 3))

    def test_new_job_name_uses_label_or_package_root(self):
        source = Path('root/1525_004_E-1525-2025-0001/content/sip/content')
        self.assertEqual(readable_job_name(str(source), '1525_004 WebSak'),
                         '1525_004 WebSak')
        self.assertEqual(readable_job_name(str(source)), '1525_004_E-1525-2025-0001')


class WiringA10Tests(unittest.TestCase):
    def test_entrypoint_uses_new_window(self):
        entry = (ROOT / 'gui_qt/__main__.py').read_text('utf-8')
        self.assertIn('from gui_qt.main_v022_a10 import DwmMainWindow', entry)
        self.assertNotIn('install_dropdown_positioning(application, window)\n    install_dropdown_positioning', entry)

    def test_after_processing_is_not_replaced(self):
        ui = (ROOT / 'gui_qt/main_v022_a10.py').read_text('utf-8')
        self.assertIn('self._start_worker(targets)', ui)
        self.assertNotIn('JobRunner(', ui)
        self.assertIn('self._v022_register_current', ui)
        self.assertIn('self._a3_accept_source(source)', ui)

    def test_no_global_popup_filter(self):
        popup = (ROOT / 'gui_qt/combo_anchor_v022_a10.py').read_text('utf-8')
        self.assertIn('popup.installEventFilter(anchor)', popup)
        self.assertNotIn('application.installEventFilter', popup)

    def test_profile_editor_has_vertical_splitter(self):
        ui = (ROOT / 'gui_qt/profile_editor_v022_a9.py').read_text('utf-8')
        self.assertIn('QSplitter(Qt.Orientation.Vertical', ui)
        self.assertIn('setChildrenCollapsible(False)', ui)


if __name__ == '__main__':
    unittest.main()
