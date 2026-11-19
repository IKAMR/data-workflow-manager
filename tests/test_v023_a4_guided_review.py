"""v0.2.3-a4: linear workflow and immutable evidence/review boundaries."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
import zipfile

from app.ks_guided_v023_a4 import (
    ordered_findings, find_index, metadata_for_test, inspect_relation,
    review_evidence_note,
)
from app.basic_selection_guard_v023_a4 import same_storage_path, saved_job_decision

ROOT = Path(__file__).resolve().parents[1]


class GuidedOrderingTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'finding_key': 'r1', 'severity': 'REVIEW', 'test_id': 'period'},
            {'finding_key': 'e1', 'severity': 'ERROR', 'test_id': 'N5.15'},
            {'finding_key': 'e2', 'severity': 'ERROR', 'test_id': 'N5.22'},
            {'finding_key': 'r2', 'severity': 'REVIEW', 'test_id': 'format'},
            {'finding_key': 'e3', 'severity': 'ERROR', 'test_id': 'N5.22'},
            {'finding_key': 'e4', 'severity': 'ERROR', 'test_id': 'N5.22'},
            {'finding_key': 'e5', 'severity': 'ERROR', 'test_id': 'N5.25'},
        ]

    def test_five_error_rows_not_177_tests_or_three_unique_ids(self):
        keys = [r['finding_key'] for r in ordered_findings(self.rows)]
        self.assertEqual(keys, ['e1', 'e2', 'e3', 'e4', 'e5'])
        self.assertEqual(find_index(ordered_findings(self.rows), 'e3'), 2)

    def test_all_preserves_distinct_findings_and_priority(self):
        rows = ordered_findings(self.rows, errors_only=False)
        self.assertEqual([r['finding_key'] for r in rows],
                         ['e1', 'e2', 'e3', 'e4', 'e5', 'r1', 'r2'])
        self.assertEqual(find_index(rows, 'does-not-exist'), -1)

    def test_status_or_user_comments_do_not_mutate_source_rows(self):
        original = [dict(x) for x in self.rows]
        _ = ordered_findings(self.rows, errors_only=False)
        self.assertEqual(self.rows, original)


class FieldLinkTests(unittest.TestCase):
    def setUp(self):
        self.bundle = {'versions': {'5.0': {'metadata': [
            {'metadata_id': 'M052', 'name': 'saksstatus', 'source_id': 'metadatakatalog'},
            {'metadata_id': 'M053', 'name': 'journalstatus', 'source_id': 'metadatakatalog'},
            {'metadata_id': 'M054', 'name': 'dokumentstatus', 'source_id': 'metadatakatalog'},
            {'metadata_id': 'M300', 'name': 'dokumentmedium', 'source_id': 'metadatakatalog'},
        ], 'value_sets': {
            'M052_saksstatus': {'values': ['Under behandling', 'Avsluttet', 'Utgår']},
        }}}}
        self.bundle['versions']['5.0']['metadata'][0]['registered_value_set_id'] = 'M052_saksstatus'

    def test_status_fields_are_resolved_from_actual_registry(self):
        for tid, mid, field in (('N5.15', 'M052', 'saksstatus'),
                                ('N5.22', 'M053', 'journalstatus'),
                                ('N5.25', 'M054', 'dokumentstatus')):
            with self.subTest(tid=tid):
                result = metadata_for_test(tid, self.bundle, '5.0')
                self.assertEqual(result['metadata_id'], mid)
                self.assertEqual(result['xml_field'], field)
        self.assertNotIn('M300', [metadata_for_test(t, self.bundle, '5.0')['metadata_id']
                                   for t in ('N5.15', 'N5.22', 'N5.25')])

    def test_absent_or_duplicate_registry_link_is_not_invented(self):
        self.assertEqual(metadata_for_test('N5.15', None, '5.0')['metadata_id'], '')
        self.assertEqual(metadata_for_test('N5.15', self.bundle, '4.0')['state'], 'not_registered')
        other = {'versions': {'5.0': {'metadata': [
            {'metadata_id': 'M052', 'name': 'saksstatus'},
            {'metadata_id': 'M999', 'name': 'saksstatus'},
        ]}}}
        self.assertEqual(metadata_for_test('N5.15', other, '5.0')['state'], 'ambiguous')
        self.assertEqual(metadata_for_test('N5.01', self.bundle, '5.0')['state'], 'not_mapped')

    def test_standard_value_is_not_delivery_approval(self):
        link = metadata_for_test('N5.15', self.bundle, '5.0')
        delivery = {'delivery_values': ['Avsluttet', 'Utgår']}
        result = inspect_relation('Under behandling', link, delivery)
        self.assertEqual(result['registered_code'], 'registrert')
        self.assertEqual(result['delivery_allowed'], 'nei etter registrert avleveringsbetingelse')
        self.assertTrue(result['technical_result_unchanged'])
        self.assertEqual(inspect_relation('Under behandling', link, None)['delivery_allowed'],
                         'ikke kildeavklart')

    def test_review_evidence_includes_exact_anchor_and_sha_not_approval(self):
        finding = {'test_id': 'N5.15', 'source': 'Arkade 5',
                   'message': 'Saksstatus: Under behandling - Antall: 19',
                   'source_ref': 'external_evidence/arkade5/20261118/normalized/arkade5_results.json'}
        anchor = {'line': 274533, 'file': 'arkivstruktur.xml',
                  'archive_part_title': 'STHA5 Stranda Hamnevesen'}
        xml = {'available': True, 'metadata': {'system_id': '7ee42c53-test',
                'element': 'saksstatus', 'xml_value': 'Under behandling',
                'xpath': '/arkiv[1]/mappe[1]/saksstatus[1]'}}
        note = review_evidence_note(finding, source_sha256='a' * 64,
                                    anchor=anchor, xml=xml,
                                    metadata=metadata_for_test('N5.15', self.bundle, '5.0'),
                                    delivery={'delivery_values': ['Avsluttet', 'Utgår']})
        for expected in ('N5.15', '274533', 'STHA5', 'M052', '7ee42c53-test',
                         'Under behandling', 'ikke vedtak', 'a' * 64):
            self.assertIn(expected, note)
        self.assertNotIn('Automatisk godkjent', note)


class MultiJobSafetyTests(unittest.TestCase):
    def setUp(self):
        self.jobs = [SimpleNamespace(job_id=f'JOB-{i:03d}',
             source_extraction=fr'I:\Noark5\1525\Source{i}',
             work_operations=fr'I:\Noark5\1525\Work{i}',
             effective_work_operations=fr'I:\Noark5\1525\Work{i}')
             for i in (1, 2, 3)]

    def decision(self, *, selected='JOB-002', actual='JOB-002',
                 source=r'I:\Noark5\1525\Source2', work=r'I:\Noark5\1525\Work2',
                 edited=False, dirty=False, draft=False):
        return saved_job_decision(self.jobs, selected_job_id=selected,
                                  actual_active_id=actual, source=source, work=work,
                                  edited=edited, metadata_dirty=dirty, draft=draft)

    def test_three_jobs_same_joblist_unchanged_selected_job_is_reused(self):
        self.assertEqual(self.decision(), 'reuse')
        self.assertTrue(same_storage_path(r'i:\noark5\1525\Source2',
                                          r'I:\Noark5\1525\Source2'))

    def test_stale_form_from_previous_job_can_be_restored_without_rebinding(self):
        self.assertEqual(self.decision(source=r'I:\Noark5\1525\Source1',
                                       work=r'I:\Noark5\1525\Work1'), 'restore')
        self.assertEqual(self.decision(source=r'I:\Noark5\1525\Source3',
                                       work=r'I:\Noark5\1525\Work3'), 'restore')

    def test_genuine_user_edits_never_auto_restored(self):
        self.assertEqual(self.decision(source=r'I:\Noark5\1525\Source1',
                                       work=r'I:\Noark5\1525\Work1', edited=True), 'register')
        self.assertEqual(self.decision(dirty=True), 'register')

    def test_unknown_paths_and_mismatched_job_id_block(self):
        self.assertEqual(self.decision(source=r'I:\Noark5\1525\unknown'), 'blocked')
        self.assertEqual(self.decision(actual='JOB-001'), 'blocked')
        self.assertEqual(self.decision(selected='JOB-999'), 'blocked')
        self.assertEqual(self.decision(draft=True), 'register')

    def test_no_shared_work_or_source_mutations(self):
        original = [(j.job_id, j.source_extraction, j.work_operations) for j in self.jobs]
        self.decision(source=r'I:\Noark5\1525\Source1', work=r'I:\Noark5\1525\Work1')
        self.assertEqual([(j.job_id, j.source_extraction, j.work_operations) for j in self.jobs], original)


class A4IntegrationContract(unittest.TestCase):
    def test_entrypoint_and_release_metadata(self):
        import tomllib
        from version import VERSION
        self.assertGreaterEqual(int(VERSION.rsplit('-a', 1)[1]), 4)
        with (ROOT / 'pyproject.toml').open('rb') as f:
            self.assertEqual(tomllib.load(f)['project']['version'], VERSION.replace('-a', 'a'))
        entry = (ROOT / 'gui_qt/__main__.py').read_text('utf-8')
        self.assertIn('from gui_qt.main_v023_a4 import DwmMainWindow', entry)
        self.assertNotIn('from gui_qt.main_v023_a3 import DwmMainWindow\n', entry)

    def test_guided_qt_panel_is_lazy_no_new_runner_or_ledger(self):
        gui = (ROOT / 'gui_qt/ks_guided_v023_a4.py').read_text('utf-8')
        for expected in ('Veiledet KS', 'Lagre og neste',
                         'v023_a4_source_occurrences', 'v023_a4_review_comment',
                         'v023_a4_field_and_rule', 'arkade_occurrences(',
                         'save_review(', '_XmlReader(', 'load_reference_bundle()',
                         'requestInterruption()', '_guided_can_leave('):
            self.assertIn(expected, gui)
        for forbidden in ('api.run_job(', 'record_review(', 'write_text(', 'write_bytes(',
                          'source.copy(', 'shutil.copy'):
            self.assertNotIn(forbidden, gui)

    def test_multijob_guard_does_not_rebind_work_or_ignore_user_edits(self):
        gui = (ROOT / 'gui_qt/main_v023_a4.py').read_text('utf-8')
        self.assertIn('saved_job_decision(', gui)
        self.assertIn('_load_basic_active_job()', gui)
        self.assertIn('super()._v022_register_current(show_errors=show_errors)', gui)
        for forbidden in ('api.update_storage(', 'api.create_job(', 'api.remove_job('):
            self.assertNotIn(forbidden, gui)



class MultiJobGuiMethodTests(unittest.TestCase):
    """Exercise the real a4 override with a fake inherited Qt-free window."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        import sys
        from unittest.mock import patch
        cls._stub_base = type('PreviousMain', (), {
            '_v022_register_current': lambda self, show_errors=True: self._calls.append('guarded') or False,
        })
        cls._fake_module = __import__('types').ModuleType('gui_qt.main_v023_a3')
        cls._fake_module.DwmMainWindow = cls._stub_base
        cls._patcher = patch.dict(sys.modules, {'gui_qt.main_v023_a3': cls._fake_module})
        cls._patcher.start()
        name = 'gui_qt.main_v023_a4_testonly'
        spec = importlib.util.spec_from_file_location(name, ROOT / 'gui_qt/main_v023_a4.py')
        cls._mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls._mod)

    @classmethod
    def tearDownClass(cls):
        cls._patcher.stop()

    def setUp(self):
        jobs = [SimpleNamespace(job_id=f'JOB-{n:03d}',
                                source_extraction=f'I:\\Noark5\\Source{n}',
                                work_operations=f'I:\\Noark5\\Work{n}',
                                effective_work_operations=f'I:\\Noark5\\Work{n}') for n in (1, 2, 3)]
        self.window = self._mod.DwmMainWindow()
        self.window._calls = []
        self.window._basic_active = True
        self.window._active_id = 'JOB-002'
        self.window._v022_loading_job = False
        self.window._v022_draft = False
        self.window._basic_selection_edited = False
        self.window._a2_pending_dirty = False
        self.window._basic_legacy_layout = False
        self.window.basic_source_path = SimpleNamespace(text=lambda: 'I:\\Noark5\\Source2')
        self.window.basic_work_path = SimpleNamespace(text=lambda: 'I:\\Noark5\\Work2')
        self.window.api = SimpleNamespace(
            workspace=lambda: SimpleNamespace(jobs=jobs, active_job_id='JOB-002'),
            job_details=lambda jid: SimpleNamespace(job=next(j for j in jobs if j.job_id == jid)),
        )
        self.window._v022_save_joblist_to_existing_file = lambda: self.window._calls.append('save-list') or True
        self.window._v022_refresh_selector = lambda force=False: self.window._calls.append('refresh')

        def load():
            self.window._calls.append('restore-selected')
            self.window.basic_source_path = SimpleNamespace(text=lambda: 'I:\\Noark5\\Source2')
            self.window.basic_work_path = SimpleNamespace(text=lambda: 'I:\\Noark5\\Work2')
        self.window._load_basic_active_job = load

    def test_unchanged_job_needs_only_save_not_re_registration(self):
        self.assertTrue(self.window._v022_register_current())
        self.assertEqual(self.window._calls, ['save-list'])

    def test_stale_job1_source_work_restored_before_saving_job2(self):
        self.window.basic_source_path = SimpleNamespace(text=lambda: 'I:\\Noark5\\Source1')
        self.window.basic_work_path = SimpleNamespace(text=lambda: 'I:\\Noark5\\Work1')
        self.assertTrue(self.window._v022_register_current())
        self.assertEqual(self.window._calls, ['restore-selected', 'refresh', 'save-list'])

    def test_actual_edits_use_previous_guard_not_silent_save(self):
        self.window._basic_selection_edited = True
        self.assertFalse(self.window._v022_register_current())
        self.assertEqual(self.window._calls, ['guarded'])

    def test_legacy_layout_keeps_old_guard(self):
        self.window._basic_legacy_layout = True
        self.assertFalse(self.window._v022_register_current())
        self.assertEqual(self.window._calls, ['guarded'])


if __name__ == '__main__':
    unittest.main()
