"""Permanent regression tests for scoped Analyse comments and additive routing."""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from app.analysis_workspace_v027_a2 import AnalysisSnapshot
from app.analysis_annotations_v027_a4 import (
    VIEW_ID, Target, make_target, parse_target, control_context,
    value_groups, item_findings, comment_matches, comment_badge,
    comment_counts, comment_export_rows, read_comments, save_comment,
)

ROOT = Path(__file__).resolve().parents[1]


def note(target: Target, *, value='Merknad', view_id=VIEW_ID, status='active'):
    return {
        'annotation_id': 'note-id', 'annotation_type': 'note', 'status': status,
        'text': value, 'created_at': '2026-11-24T23:00:00+01:00',
        'user': {'user_id': 'u-1', 'username': 'tester', 'name': 'Test Bruker'},
        'target': {'view_id': view_id, 'target_id': target.id,
                   'target_type': 'analysis_' + target.level,
                   'target_label': 'M053'},
    }


class A4CommentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        report_dir = self.work / 'noark5_reports' / 'depot_validation' / 'JOB-001__run'
        report_dir.mkdir(parents=True)
        self.report_path = report_dir / 'depot_validation_report.json'
        self.report_path.write_text('{"report_type":"noark5_depot_validation"}\n', encoding='utf-8')
        self.snapshot = AnalysisSnapshot(
            work=self.work, job_id='JOB-001', job_name='Demo', job_uid='uuid-demo',
            report_path=self.report_path,
            report={'archive_parts': [
                {'archive_part': {'system_id': 'part-A', 'title': 'Papir'}},
                {'archive_part': {'system_id': 'part-B', 'title': 'Elektronisk'}},
            ]}, metadata={}, findings=(
                {'metadata_id': 'M053', 'archive_part_id': 'part-B',
                 'value': 'Journalført', 'object_id': 'reg-1',
                 'finding_uid': 'a' * 64},
                {'metadata_id': 'M053', 'archive_part_id': 'part-B',
                 'value': 'Journalført', 'object_id': 'reg-2',
                 'finding_uid': 'b' * 64},
                {'metadata_id': 'M052', 'archive_part_id': 'part-A',
                 'value': 'Under behandling', 'object_id': 'sak-1',
                 'finding_uid': 'c' * 64},
            ), findings_complete=True, format_statistics={},
        )
        self.m053 = {'metadata_id': 'M053', 'label': 'Journalstatus'}
        self.m052 = {'metadata_id': 'M052', 'label': 'Saksstatus'}
        self.m053_id = 'metadata:M053'

    def test_stable_structured_target_and_unicode_value(self):
        value = make_target('group', 'part:part-B', 'Metadata og verdier',
                            self.m053_id, 'Journalført / Å')
        self.assertEqual(parse_target(value.id), value)
        self.assertEqual(parse_target('not a valid a4 target'), None)
        self.assertIsNone(parse_target('analysis-a4:["item"]'))
        with self.assertRaises(ValueError):
            make_target('item', 'extract', 'Metadata og verdier', self.m053_id)
        with self.assertRaises(ValueError):
            make_target('group', 'extract', 'Metadata og verdier', self.m053_id)

    def test_metadata_scope_is_native_part_and_format_cannot_borrow_part(self):
        self.assertEqual(control_context(self.snapshot, 'metadata', self.m053, 1),
                         ('Metadata og verdier', self.m053_id, 'part:part-B'))
        self.assertEqual(control_context(self.snapshot, 'metadata', self.m053, None)[-1],
                         'extract')
        self.assertEqual(control_context(self.snapshot, 'format', {'puid': 'fmt/354'}, 1)[-1],
                         'extract')
        self.assertEqual(control_context(self.snapshot, 'part', 0, None)[-1],
                         'part:part-A')
        with self.assertRaises(ValueError):
            control_context(self.snapshot, 'unknown', 0, None)

    def test_groups_and_items_come_only_from_real_source_findings(self):
        self.assertEqual(value_groups(self.snapshot, 'metadata', self.m053, 'part:part-B'),
                         (('Journalført', 2),))
        self.assertEqual(value_groups(self.snapshot, 'metadata', self.m053, 'part:part-A'), ())
        actual = item_findings(self.snapshot, 'metadata', self.m053,
                               'part:part-B', 'Journalført')
        self.assertEqual([item['finding_uid'] for item in actual], ['a' * 64, 'b' * 64])
        self.assertEqual(item_findings(self.snapshot, 'format', {'puid': 'fmt/354'}, 'extract'), ())
        incomplete = self.snapshot.__class__(**{
            **self.snapshot.__dict__, 'findings_complete': False,
        })
        self.assertEqual(value_groups(incomplete, 'metadata', self.m053, 'extract'), ())
        self.assertEqual(item_findings(incomplete, 'metadata', self.m053, 'extract'), ())

    def test_whole_extraction_groups_include_documented_valid_values(self):
        # Archived aggregate distribution can support a value-group comment
        # even where the value has no delivery deviation.
        record = {**self.m053, 'production_distribution': {
            'Arkivert': 410, 'Journalført': 20, 'Utgår': 37,
            'Ingen': 0,
        }}
        self.assertEqual(value_groups(self.snapshot, 'metadata', record, 'extract'),
                         (('Arkivert', 410), ('Utgår', 37), ('Journalført', 20)))
        # No per-part count may be inferred from those aggregate totals.
        self.assertEqual(value_groups(self.snapshot, 'metadata', record, 'part:part-B'),
                         (('Journalført', 2),))
        self.assertEqual(value_groups(self.snapshot, 'metadata', record, 'part:part-A'), ())

    def test_single_findings_are_not_inherited_by_other_parts(self):
        value = make_target('item', 'part:part-B', 'Metadata og verdier',
                            self.m053_id, 'Journalført', 'a' * 64)
        comments = [note(value)]
        self.assertEqual(comment_matches(self.snapshot, 'metadata', self.m053, 0, comments), ())
        own = comment_matches(self.snapshot, 'metadata', self.m053, 1, comments)
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0][0], 'child')
        self.assertEqual(len(comment_matches(self.snapshot, 'metadata', self.m053, None, comments)), 1)
        self.assertEqual(comment_matches(self.snapshot, 'metadata', self.m052, None, comments), ())

    def test_shared_control_and_area_annotations_apply_without_copying(self):
        global_note = note(make_target('control', 'extract', 'Metadata og verdier',
                                       self.m053_id))
        area_note = note(make_target('area', 'extract', 'Metadata og verdier'))
        result = comment_matches(self.snapshot, 'metadata', self.m053, 1,
                                 [global_note, area_note])
        self.assertEqual(comment_counts(result), (0, 2, 0))
        self.assertIn('💬 2', comment_badge(result))
        other = comment_matches(self.snapshot, 'metadata', self.m052, 1,
                                [global_note, area_note])
        self.assertEqual(len(other), 1)  # broad area note only
        self.assertEqual(len([global_note, area_note]), 2)  # no per-item copies

    def test_group_rolls_up_and_does_not_spread_to_other_control(self):
        group = note(make_target('group', 'part:part-B', 'Metadata og verdier',
                                 self.m053_id, 'Journalført'))
        result = comment_matches(self.snapshot, 'metadata', self.m053, 1, [group])
        self.assertEqual(comment_counts(result), (0, 0, 1))
        self.assertFalse(comment_matches(self.snapshot, 'metadata', self.m052, 1, [group]))
        self.assertFalse(comment_matches(self.snapshot, 'metadata', self.m053, 0, [group]))

    def test_legacy_views_and_closed_comments_do_not_leak_into_filter(self):
        target = make_target('control', 'extract', 'Metadata og verdier', self.m053_id)
        comments = [note(target, view_id='legacy'), note(target, status='closed')]
        self.assertFalse(comment_matches(self.snapshot, 'metadata', self.m053, None, comments))

    def test_export_projection_contains_scope_author_and_factual_target(self):
        value = make_target('item', 'part:part-B', 'Metadata og verdier',
                            self.m053_id, 'Journalført', 'a' * 64)
        result = comment_export_rows([note(value, value='Må vurderes')])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['level'], 'item')
        self.assertEqual(result[0]['scope'], 'part:part-B')
        self.assertEqual(result[0]['user'], 'tester')
        self.assertEqual(result[0]['text'], 'Må vurderes')

    def test_existing_ledger_is_called_without_replacing_results(self):
        original = self.report_path.read_bytes()
        received = {}
        fake = ModuleType('noark5_workflow.analysis.depot_annotations')

        def fake_read(path, *, view_id):
            received['read'] = (path, view_id)
            return [note(make_target('control', 'extract', 'Metadata og verdier',
                                     self.m053_id))]

        def fake_save(path, **kwargs):
            received['save'] = (path, kwargs)
            return {'annotation_id': 'new-1', **kwargs}

        fake.list_depot_annotations = fake_read
        fake.record_depot_annotation = fake_save
        target = make_target('control', 'extract', 'Metadata og verdier', self.m053_id)
        with patch.dict(sys.modules, {'noark5_workflow': ModuleType('noark5_workflow'),
                                      'noark5_workflow.analysis': ModuleType('noark5_workflow.analysis'),
                                      'noark5_workflow.analysis.depot_annotations': fake}):
            self.assertEqual(len(read_comments(self.report_path)), 1)
            saved = save_comment(self.snapshot, target, 'M053', 'Vurder nærmere', 'question',
                                 SimpleNamespace(name='tester'))
        self.assertEqual(received['read'][1], VIEW_ID)
        self.assertEqual(received['save'][1]['view_id'], VIEW_ID)
        self.assertEqual(received['save'][1]['target_type'], 'analysis_control')
        self.assertEqual(received['save'][1]['target_id'], target.id)
        self.assertEqual(saved['annotation_type'], 'question')
        self.assertEqual(self.report_path.read_bytes(), original)

    def test_writes_outside_selected_work_and_symlinks_are_rejected(self):
        target = make_target('area', 'extract', 'Metadata og verdier')
        foreign = self.work.parent / 'foreign_report.json'
        altered = self.snapshot.__class__(**{
            **self.snapshot.__dict__, 'report_path': foreign,
        })
        with self.assertRaises((ValueError, FileNotFoundError)):
            save_comment(altered, target, 'M053', 'comment', 'note', object())
        sidecar = self.report_path.with_name('depot_annotations.json')
        try:
            sidecar.symlink_to(self.report_path)
        except (OSError, NotImplementedError):
            return  # Windows may disallow symlinks for a non-admin process.
        with self.assertRaises(ValueError):
            save_comment(self.snapshot, target, 'M053', 'comment', 'note', object())


class A4WiringTests(unittest.TestCase):
    def test_a4_is_last_in_analysis_chain_and_classic_is_retained(self):
        main = (ROOT / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        ast.parse(main)
        self.assertLess(main.index('install_analysis_workspace_v3(window)'),
                        main.index('install_analysis_workspace_v4(window)'))
        a2 = (ROOT / 'gui_qt/analysis_workspace_v027_a2.py').read_text(encoding='utf-8')
        self.assertIn('Resultatvisninger (klassisk)', a2)
        self.assertIn('window._analysis_classic_result_center = legacy', a2)
        a4 = (ROOT / 'gui_qt/analysis_workspace_v027_a4.py').read_text(encoding='utf-8')
        ast.parse(a4)
        self.assertIn('window._analysis_dialog_class = AnalysisWorkspaceDialogV4', a4)
        self.assertIn('Med kommentarer', a4)
        self.assertIn('QTextCursor', a4)
        a3 = (ROOT / 'gui_qt/analysis_workspace_v027_a3.py').read_text(encoding='utf-8')
        self.assertIn('YearBarChart', a3)
        self.assertIn('QSplitter', a3)
        self.assertIn('annual_chart_data', a3)

    def test_distribution_version_matches_runtime_without_alpha_lock(self):
        from version import VERSION
        import tomllib
        with (ROOT / 'pyproject.toml').open('rb') as reader:
            self.assertEqual(tomllib.load(reader)['project']['version'],
                             VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
