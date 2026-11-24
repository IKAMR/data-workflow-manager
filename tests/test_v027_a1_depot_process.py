"""v0.2.7-a1: source-bound, read-only depot process overview."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from app import depot_process_v027_a1 as M


class DepotProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name) / 'work'
        self.work.mkdir()
        self.uid = 'uid-1547-007'
        self._write('job.json', {
            'file_type': 'dwm-work-job', 'job_uid': self.uid,
            'job': {'job_id': 'JOB-003'},
        })
        self.report_rel = 'noark5_reports/depot_validation/JOB-003__run/depot_validation_report.json'

    def _write(self, rel, value):
        target = self.work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False) + '\n', encoding='utf-8')
        return target

    def _shot(self):
        return SimpleNamespace(
            job=SimpleNamespace(work=self.work, job_uid=self.uid,
                                job_id='JOB-003', name='1547_007 Forum Winsak'),
            results=SimpleNamespace(depot_report_path=None, artifacts=()),
            depot=None,
        )

    def _report(self, parts=()):
        return self._write(self.report_rel, {
            'report_type': 'noark5_depot_validation',
            'summary': {'archive_part_count': len(parts)},
            'technical_validation': {'status': 'ok', 'tests': []},
            'archive_parts': list(parts),
            'deviations': [],
        })

    def _rows(self, shots=None):
        with (patch.object(M, '_depot_assessment', return_value=('Ikke vurdert', ())),
              patch.object(M, '_part_decisions', return_value=({}, ()))):
            return M.build_depot_process_rows(shots or [self._shot()])

    def test_without_report_never_reports_zero_or_approval(self):
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].technical, 'Ukjent')
        self.assertEqual(rows[0].archive_part_count, None)
        self.assertEqual(rows[0].findings, 'A260 ikke dokumentert')
        self.assertEqual(rows[0].assessment, 'Ikke verifisert')
        self.assertTrue(rows[0].warnings)

    def test_one_extraction_and_native_archive_parts(self):
        self._report((
            {'archive_part': {'system_id': 'A-1', 'title': 'Personalsaker'}, 'status': 'ok'},
            {'archive_part': {'system_id': 'A-2', 'title': 'Saksarkiv'}, 'status': 'warning'},
        ))
        rows = self._rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].archive_part_count, 2)
        self.assertEqual(rows[0].technical, 'ok')
        self.assertEqual(rows[1].key, (self.uid, 'A-1'))
        self.assertEqual(rows[2].technical, 'warning')
        self.assertEqual(rows[2].evidence, 'A230 på uttrekksnivå')
        self.assertIn('ikke dokumentert', rows[2].findings)

    def test_duplicate_native_archive_part_identity_is_not_decidable(self):
        self._report((
            {'archive_part': {'system_id': 'DUP', 'title': 'En'}},
            {'archive_part': {'system_id': 'DUP', 'title': 'To'}},
        ))
        with (patch.object(M, '_depot_assessment', return_value=('Ikke vurdert', ())),
              patch.object(M, '_part_decisions', return_value=(
                  {'DUP': {'current': {'status': 'accepted'}}}, ()))):
            rows = M.build_depot_process_rows([self._shot()])
        self.assertEqual(len(rows), 3)
        self.assertNotEqual(rows[1].system_id, rows[2].system_id)
        self.assertIn('Kan ikke vurderes', rows[1].assessment)
        self.assertIn('Kan ikke vurderes', rows[2].assessment)

    def test_part_decision_never_promotes_the_whole_extraction(self):
        self._report(({'archive_part': {'system_id': 'A-1', 'title': 'Saksarkiv'}},))
        with (patch.object(M, '_depot_assessment', return_value=('Ikke vurdert', ())),
              patch.object(M, '_part_decisions', return_value=(
                  {'A-1': {'current': {'status': 'accepted_with_deviation'}}}, ()))):
            rows = M.build_depot_process_rows([self._shot()])
        self.assertEqual(rows[0].assessment, 'Ikke vurdert')
        self.assertIn('Akseptert med avvik', rows[1].assessment)

    def test_failed_current_job_is_not_confused_with_older_ok_report(self):
        self._report()
        self._write('job-state.json', {
            'file_type': 'dwm-work-job-state', 'job_uid': self.uid,
            'state': {'status': 'failed', 'next_operation_index': 14},
            'last_run_id': 'run-after-report',
        })
        rows = self._rows()
        self.assertEqual(rows[0].run_status, 'failed')
        self.assertEqual(rows[0].technical, 'ok')
        self.assertNotEqual(rows[0].run_status, rows[0].technical)

    def test_other_jobs_state_cannot_be_used_as_current(self):
        self._report()
        self._write('job-state.json', {
            'file_type': 'dwm-work-job-state', 'job_uid': 'another-job',
            'state': {'status': 'completed'},
        })
        rows = self._rows()
        self.assertEqual(rows[0].run_status, 'Ukjent')
        self.assertIn('Jobbstatus krever kontroll', ' '.join(rows[0].warnings))

    def test_evidence_missing_source_names_are_visible(self):
        self._write('noark5_evidence/evidence-audit.json', {
            'model_id': 'dwm.noark5.evidence-audit.a7.v1', 'job_uid': self.uid,
            'status': 'missing_expected_sources', 'missing_source_families': ['arkade_pronom'],
        })
        status, audit_sha, warnings = M._audit(self.work, self.uid)
        self.assertIn('arkade_pronom', status, str(warnings))
        self.assertEqual(len(audit_sha), 64)
        self.assertFalse(warnings)

    def test_a230_and_a260_with_redirected_work_parent(self):
        """Parent aliases/junctions must not invalidate real Work evidence.

        The original code compared a fully resolved candidate with an
        unresolved Work root. This fails on redirected Windows temp folders.
        """
        report = self._report()
        audit = self._write('noark5_evidence/evidence-audit.json', {
            'model_id': 'dwm.noark5.evidence-audit.a7.v1',
            'job_uid': self.uid, 'status': 'sources_linked_needs_review',
            'missing_source_families': [],
        })
        self._valid_a260(M._hash(report), M._hash(audit))
        link = Path(self.temporary.name) / 'redirected-parent'
        try:
            link.symlink_to(self.work.parent, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest('Mangler tillatelse til å lage kataloglenke: ' + str(exc))
        via_alias = link / self.work.name
        self.assertNotEqual(via_alias, via_alias.resolve())
        label, digest, problems = M._audit(via_alias, self.uid)
        self.assertIn('Kilder koblet', label, str(problems))
        self.assertEqual(digest, M._hash(audit))
        self.assertFalse(problems)
        count_label, count_problems = M._a260(via_alias, self.uid,
                                               M._hash(report), digest)
        self.assertIn('1 (komplett A260-register)', count_label, str(count_problems))
        self.assertFalse(count_problems)

    def test_symlink_as_work_root_is_not_allowed(self):
        link = Path(self.temporary.name) / 'root-link'
        try:
            link.symlink_to(self.work, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest('Mangler tillatelse til å lage kataloglenke: ' + str(exc))
        with self.assertRaisesRegex(ValueError, 'Ugyldig Work-katalog'):
            M._safe_path(link, 'job.json')

    def test_a230_other_job_is_not_accepted(self):
        self._write('noark5_evidence/evidence-audit.json', {
            'model_id': 'dwm.noark5.evidence-audit.a7.v1', 'job_uid': 'uid-other',
            'status': 'sources_linked_needs_review', 'missing_source_families': [],
        })
        status, digest, warnings = M._audit(self.work, self.uid)
        self.assertEqual(status, 'A230 krever kontroll')
        self.assertFalse(digest)
        self.assertTrue(warnings)

    def _valid_a260(self, report_sha: str, audit_sha: str):
        base = 'noark5_evidence/a260_exports_v023_a6/20261124-a/'
        blob = self._write(base + 'funn.jsonl', {'test_id': 'T', 'source': 'DWM'})
        csv = self.work / base / 'funn.csv'
        csv.write_text('a;b\r\n1;2\r\n', encoding='utf-8')
        summary = {'total': 1, 'errors': 1, 'automatic_approval': False}
        self._write(base + 'manifest.json', {
            'model_id': 'dwm.noark5.a260.complete-findings.a6.v1',
            'job_uid': self.uid, 'depot_report_sha256': report_sha,
            'summary': summary,
            'files': {'funn.jsonl': {'bytes': blob.stat().st_size, 'sha256': M._hash(blob)},
                      'funn.csv': {'bytes': csv.stat().st_size, 'sha256': M._hash(csv)}},
        })
        self._write('noark5_evidence/qa-basis-draft.json', {
            'model_id': 'dwm.noark5.qa-basis.draft.a7.v1', 'job_uid': self.uid,
            'automatic_approval': False, 'evidence_audit_sha256': audit_sha,
            'findings': summary, 'export_manifest': base + 'manifest.json',
            'exports': {'jsonl': base + 'funn.jsonl', 'csv': base + 'funn.csv'},
        })
        return blob, csv

    def test_a260_is_counted_only_with_full_hash_integrity(self):
        report = self._report()
        audit = self._write('noark5_evidence/evidence-audit.json', {'status': 'sources_linked_needs_review'})
        files = self._valid_a260(M._hash(report), M._hash(audit))
        label, warnings = M._a260(self.work, self.uid, M._hash(report), M._hash(audit))
        self.assertIn('1 (komplett A260-register)', label, str(warnings))
        self.assertFalse(warnings)
        files[0].write_text('endret', encoding='utf-8')
        label, warnings = M._a260(self.work, self.uid, M._hash(report), M._hash(audit))
        self.assertEqual(label, 'A260 krever kontroll')
        self.assertTrue(warnings)

    def test_a260_from_previous_depot_revision_is_not_current(self):
        report = self._report()
        audit = self._write('noark5_evidence/evidence-audit.json', {'status': 'sources_linked_needs_review'})
        self._valid_a260(M._hash(report), M._hash(audit))
        label, warnings = M._a260(self.work, self.uid, '0' * 64, M._hash(audit))
        self.assertEqual(label, 'A260 krever kontroll')
        self.assertTrue(warnings)

    def test_a260_without_a230_is_not_proven_complete(self):
        report = self._report()
        audit = self._write('noark5_evidence/evidence-audit.json', {'status': 'sources_linked_needs_review'})
        self._valid_a260(M._hash(report), M._hash(audit))
        label, warnings = M._a260(self.work, self.uid, M._hash(report), '')
        self.assertEqual(label, 'A260 krever kontroll')
        self.assertTrue(warnings)

    def test_safe_work_paths_reject_escape_or_symlink(self):
        for relative in ('../outside', '/absolute', 'C:/file', 'a//b', 'a\\b'):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                M._safe_path(self.work, relative)
        outside = Path(self.temporary.name) / 'outside'
        outside.write_text('not work', encoding='utf-8')
        link = self.work / 'alias'
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            pass
        else:
            with self.assertRaises(ValueError):
                M._safe_path(self.work, 'alias')

    def test_streaming_large_report_is_used_instead_of_12mb_limit(self):
        self._report(({'archive_part': {'system_id': 'A1', 'title': 'En'}},))
        report = self.work / self.report_rel
        fake = ModuleType('noark5_workflow.reporting.qa_depot_stream_v023_a17')
        fake.project_depot_report = lambda path: (
            {'report_type': 'noark5_depot_validation',
             'archive_parts': [{'archive_part': {'system_id': 'A1', 'title': 'En'}}],
             'technical_validation': {'status': 'ok'}, 'summary': {}}, M._hash(path))
        with (patch.object(M, 'MAX_SMALL_REPORT', 5),
              patch.dict(sys.modules, {'noark5_workflow.reporting.qa_depot_stream_v023_a17': fake}),
              patch.object(M, '_depot_assessment', return_value=('Ikke vurdert', ())),
              patch.object(M, '_part_decisions', return_value=({}, ()))):
            rows = M.build_depot_process_rows([self._shot()])
        self.assertEqual(len(rows), 2)
        self.assertIn('strømmelesing', rows[0].basis)
        self.assertEqual(rows[0].archive_part_count, 1)

    def test_invalid_latest_report_keeps_older_but_marks_staleness(self):
        old = self._report()
        newer = self._write('noark5_reports/depot_validation/JOB-003__z/depot_validation_report.json',
                            {'report_type': 'unsupported'})
        import os
        os.utime(old, ns=(1_000_000_000, 1_000_000_000))
        os.utime(newer, ns=(2_000_000_000, 2_000_000_000))
        rows = self._rows()
        self.assertEqual(rows[0].report_path, old.resolve())
        self.assertIn('Nyere depotrapport', ' '.join(rows[0].warnings))

    def test_job_uid_deduplicates_identical_work(self):
        self._report()
        rows = self._rows([self._shot(), self._shot()])
        self.assertEqual(len(rows), 1)

    def test_wrong_work_uid_fails_closed(self):
        self._report()
        bad = self._shot()
        bad.job.job_uid = 'other-job'
        rows = self._rows([bad])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].assessment, 'Ikke verifisert')
        self.assertTrue(rows[0].warnings)

    def test_corrupt_arkivdel_sidecar_never_looks_unreviewed(self):
        self._report(({'archive_part': {'system_id': 'A-1', 'title': 'Ett'}},))
        with (patch.object(M, '_depot_assessment', return_value=('Ikke vurdert', ())),
              patch.object(M, '_part_decisions', return_value=(
                  {}, ('Arkivdelvurderingene gjelder en annen rapportrevisjon',)))):
            rows = M.build_depot_process_rows([self._shot()])
        self.assertIn('kontroller rapportrevisjon', rows[1].assessment)
        self.assertTrue(rows[1].warnings)

    def test_incomplete_depot_report_never_reports_zero_parts(self):
        self._write(self.report_rel, {'report_type': 'noark5_depot_validation'})
        rows = self._rows()
        self.assertIsNone(rows[0].archive_part_count)
        self.assertEqual(rows[0].assessment, 'Ikke verifisert')
        self.assertIn('kan ikke leses', rows[0].basis)

    def test_startup_installer_is_guarded_by_real_qt_window(self):
        import ast
        root = Path(__file__).resolve().parents[1]
        main = (root / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        tree = ast.parse(main)
        name = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        guarded = [n for n in ast.walk(name) if isinstance(n, ast.If)
                   and "hasattr(window, '_toolbar')" in ast.unparse(n.test)]
        self.assertTrue(any('install_depot_process_results_class(window)' in
                            '\n'.join(ast.unparse(child) for child in n.body)
                            for n in guarded))

    def test_result_class_extension_retains_existing_class_and_is_idempotent(self):
        import ast
        from unittest.mock import patch as mock_patch
        import gui_qt
        root = Path(__file__).resolve().parents[1]
        path = root / 'gui_qt/depot_process_v027_a1.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'install_depot_process_results_class')
        calls = []
        class Existing:
            def __init__(self, *args, **kwargs):
                self.base_created = True
        module = ModuleType('gui_qt.result_center_v0110_a4')
        module.ResultCenterWindow = Existing
        fake_namespace = {'install_depot_process_tab': lambda instance, main: calls.append((instance, main))}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), fake_namespace)
        with mock_patch.object(gui_qt, 'result_center_v0110_a4', module, create=True), \
             patch.dict(sys.modules, {'gui_qt.result_center_v0110_a4': module}):
            installer = fake_namespace['install_depot_process_results_class']
            main = object()
            extension = installer(main)
            self.assertTrue(issubclass(extension, Existing))
            self.assertIs(extension, installer(object()))
            window = extension()
        self.assertTrue(window.base_created)
        self.assertEqual(calls, [(window, main)])

    def test_read_model_never_edits_original_work_files(self):
        report = self._report(({'archive_part': {'system_id': 'A1'}},))
        state = self._write('job-state.json', {
            'file_type': 'dwm-work-job-state', 'job_uid': self.uid,
            'state': {'status': 'completed'},
        })
        originals = {p: p.read_bytes() for p in (report, state, self.work/'job.json')}
        _ = self._rows()
        for path, old in originals.items():
            with self.subTest(file=str(path)):
                self.assertEqual(path.read_bytes(), old)
        self.assertFalse((self.work/'noark5_evidence').exists())

    def test_gui_wiring_and_version_are_present(self):
        root = Path(__file__).resolve().parents[1]
        entry = (root / 'gui_qt/__main__.py').read_text(encoding='utf-8')
        installer = (root / 'gui_qt/depot_process_v027_a1.py').read_text(encoding='utf-8')
        self.assertIn('install_depot_process_results_class(window)', entry)
        self.assertIn('install_depot_process_tab(self, main_window)', installer)
        self.assertIn('DwmMainWindow = _V025A3Window', entry)
        self.assertLess(entry.index('window = DwmMainWindow(api)'),
                        entry.index('install_depot_process_results_class(window)'))
        self.assertLess(entry.index('install_depot_process_results_class(window)'),
                        entry.index('install_canonical_results_menu(window)'))
        self.assertIn('raise SystemExit(main())', entry)
        from version import VERSION
        import re
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-a(\d+))?', VERSION)
        self.assertIsNotNone(match)
        release = tuple(int(match.group(n)) for n in (1, 2, 3))
        self.assertGreaterEqual(release, (0, 2, 7))
        if release == (0, 2, 7) and match.group(4) is not None:
            self.assertGreaterEqual(int(match.group(4)), 1)


if __name__ == '__main__':
    unittest.main()
