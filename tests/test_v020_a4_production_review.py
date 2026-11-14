"""a4: Qt-free evidence checks; current report != approval != preservation."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import tomllib
import unittest
from unittest.mock import Mock

from app.production_review_v020_a4 import (
    _candidate_status, inspect_production_evidence,
)
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui_qt' / 'reporting_preservation_v020_a4.py'
HOME = ROOT / 'gui_qt' / 'production_home_v020_a2.py'
LABELS = {
    'accepted': 'Akseptert',
    'accepted_with_deviation': 'Akseptert med avvik',
    'requires_clarification': 'Krever avklaring',
    'new_extraction_required': 'Nytt uttrekk kreves',
}


class ProductionEvidenceA4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / 'repository_operations'
        self.work.mkdir()
        self.job = SimpleNamespace(job_id='JOB-001', name='Uttrekk med arkivdeler',
                                   effective_work_operations=self.work)
        self.file = self.work / 'noark5_reports' / 'depot_validation' / 'RUN-01' / 'depot_validation_report.json'
        self.file.parent.mkdir(parents=True)
        self.file.write_text('{"report_type":"noark5_depot_validation"}', encoding='utf8')
        self.artifacts = (object(), object())
        self.report_data = {
            'report_type': 'noark5_depot_validation',
            'technical_validation': {'status': 'completed'},
            'archive_parts': [{'archive_part': {'system_id': 'abc'}},
                              {'archive_part': {'system_id': 'def'}}],
        }
        self.discovery = Mock(return_value=SimpleNamespace(
            depot_report=self.report_data, depot_report_path=self.file,
            artifacts=self.artifacts, warnings=(),
        ))
        self.assessment = Mock(return_value=None)
        self.parts = Mock(return_value=None)

    def inspect(self):
        return inspect_production_evidence(
            self.job, discovery=self.discovery, load_assessment=self.assessment,
            load_parts=self.parts, assessment_labels=LABELS,
        )

    def test_technical_completed_is_not_automatic_approval(self):
        result = self.inspect()
        self.assertEqual(result.technical_status, 'completed')
        self.assertEqual(result.professional_status, 'Ikke faglig vurdert')
        self.assertEqual(result.result_files, 2)
        self.assertEqual(result.archive_parts, 2)
        self.assertEqual(result.reviewed_parts, 0)
        self.assertEqual(result.professional_history, 0)
        self.assertEqual(result.candidate_status, 'Ingen evidenskandidat funnet')
        self.assessment.assert_called_once_with(self.file.resolve())
        self.assertEqual(result.depot_report, self.file.resolve())

    def test_saved_assessment_and_parts_are_read_not_created(self):
        self.assessment.return_value = {
            'current': {'status': 'accepted_with_deviation'},
            'history': [{'status': 'accepted'}, {'status': 'accepted_with_deviation'}],
        }
        self.parts.return_value = {'parts': {
            'abc': {'current': {'status': 'accepted'}},
            'def': {'current': {'status': 'requires_clarification'}},
        }}
        before = {p.relative_to(self.work): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        result = self.inspect()
        after = {p.relative_to(self.work): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(result.professional_status, 'Akseptert med avvik')
        self.assertEqual(result.professional_history, 2)
        self.assertEqual(result.reviewed_parts, 2)
        self.assertNotIn('godkjent AIP', result.candidate_status)

    def test_outdated_decision_must_be_marked_uncertain(self):
        self.assessment.side_effect = ValueError('SHA-256 mismatch')
        self.parts.side_effect = ValueError('Part history applies to different report')
        result = self.inspect()
        self.assertEqual(result.professional_status, 'Historikk krever kontroll')
        self.assertEqual(result.reviewed_parts, 0)
        self.assertTrue(any('SHA-256' in text for text in result.warnings))
        self.assertTrue(any('Arkivdelvurderinger' in text for text in result.warnings))

    def test_no_report_stays_unapproved_even_with_other_result_files(self):
        self.discovery.return_value = SimpleNamespace(
            depot_report=None, depot_report_path=None,
            artifacts=self.artifacts, warnings=['Ingen gyldig rapport'],
        )
        result = self.inspect()
        self.assertIsNone(result.depot_report)
        self.assertEqual(result.result_files, 2)
        self.assertEqual(result.professional_status, 'Ikke faglig vurdert')
        self.assessment.assert_not_called()
        self.parts.assert_not_called()

    def test_report_escape_does_not_load_decisions(self):
        outside = Path(self.tmp.name) / 'depot_validation_report.json'
        outside.write_text('{}', encoding='utf8')
        self.discovery.return_value.depot_report_path = outside
        result = self.inspect()
        self.assertIsNone(result.depot_report)
        self.assertTrue(any('Rapportreferansen er ugyldig' in s for s in result.warnings))
        self.assessment.assert_not_called()

    def test_evidence_candidate_manifest_is_not_integrity_verification(self):
        folder = self.work / 'preservation_staging' / 'dwm-aip-candidate-v1'
        folder.mkdir(parents=True)
        (folder / 'manifest-sha256.json').write_text('{"status":"candidate_not_approved_not_aip"}', encoding='utf8')
        result = self.inspect()
        self.assertIn('IKKE kontrollert', result.candidate_status)
        self.assertNotIn('verifisert', result.candidate_status)
        self.assertTrue((folder / 'manifest-sha256.json').is_file())

    def test_candidate_missing_manifest_is_not_presentation_as_aip(self):
        folder = self.work / 'preservation_staging' / 'dwm-aip-candidate-v1'
        folder.mkdir(parents=True)
        self.assertEqual(_candidate_status(self.work), 'Evidenskandidat funnet, manifest mangler')

    def test_missing_job_or_disconnected_work_does_not_invoke_engines(self):
        self.assertFalse(inspect_production_evidence(None).has_job)
        self.job.effective_work_operations = Path(self.tmp.name) / 'unplugged'
        result = self.inspect()
        self.assertEqual(result.professional_status, 'Ikke faglig vurdert')
        self.discovery.assert_not_called()

    def test_symlink_candidate_is_never_treated_as_safe(self):
        stage = self.work / 'preservation_staging'
        stage.mkdir()
        try:
            (stage / 'dwm-aip-candidate-v1').symlink_to(Path(self.tmp.name), target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest('Symlinks not available for this Windows test account')
        self.assertIn('symbolsk lenke', _candidate_status(self.work))


class QtContractA4Tests(unittest.TestCase):
    def test_new_pages_delegate_to_established_technical_and_depot_ui(self):
        gui = GUI.read_text(encoding='utf8')
        self.assertIn('class ReportingPage(_ProductionEvidencePage):', gui)
        self.assertIn('class PreservationPage(_ProductionEvidencePage):', gui)
        self.assertIn('self.window._a12_open_result_center(depot=True)', gui)
        self.assertIn('self.window._a12_open_selected_report()', gui)
        self.assertIn("getattr(self.window, '_a15_canonical_action', None)", gui)
        self.assertIn('self.window._open_legacy()', gui)
        self.assertIn('inspect_production_evidence(job)', gui)
        self.assertIn('QMessageBox.question(', gui)
        self.assertNotIn('record_depot_review(', gui)
        self.assertNotIn('prepare_candidate(', gui)
        self.assertNotIn('create_grouped_ingest(', gui)

    def test_runtime_page_actions_not_bound_before_home_installation(self):
        gui = GUI.read_text(encoding='utf8')
        self.assertIn('lambda: window.v020_integrated_home()', gui)
        self.assertIn('lambda: window.v020_show_control_page()', gui)
        self.assertNotIn('clicked.connect(window.v020_integrated_home)', gui)

    def test_navigation_tracks_new_pages_but_keeps_old_modes_and_jobs(self):
        gui = HOME.read_text(encoding='utf8')
        self.assertIn('from gui_qt.reporting_preservation_v020_a4 import ReportingPage, PreservationPage', gui)
        self.assertIn('window.v020_show_reporting_page = show_reporting', gui)
        self.assertIn('window.v020_show_preservation_page = show_preservation', gui)
        self.assertIn('stack.setCurrentWidget(reporting)', gui)
        self.assertIn('stack.setCurrentWidget(preservation)', gui)
        self.assertIn('saved_advanced', gui)
        self.assertIn('window.api', gui)
        self.assertNotIn('run_job(', gui)
        self.assertNotIn('start_dias_package(', gui)

    def test_a4_is_consistent_between_version_and_distribution(self):
        self.assertEqual(VERSION, '0.2.0-a4')
        with (ROOT / 'pyproject.toml').open('rb') as handle:
            dist = tomllib.load(handle)['project']['version']
        self.assertEqual(dist, VERSION.replace('-a', 'a'))


class DelegationA4Tests(unittest.TestCase):
    """Exercise the real Qt action method without importing PySide6."""

    def setUp(self):
        tree = ast.parse(GUI.read_text(encoding='utf8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == '_ProductionEvidencePage')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == '_run_action')
        self.events = []
        events = self.events

        class MessageBox:
            class StandardButton:
                Yes = 1
                No = 2
            @staticmethod
            def information(*args):
                events.append('info')
            @staticmethod
            def warning(*args):
                events.append('warning')
            @staticmethod
            def question(*args):
                events.append('confirmation')
                return 1

        scope = {'QMessageBox': MessageBox}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(GUI), 'exec'), scope)
        self.action = scope['_run_action']
        self.window = SimpleNamespace(
            _worker=None, api=SimpleNamespace(running=False),
            _a12_open_result_center=lambda **kwargs: events.append(('results', kwargs)),
            _a12_open_selected_report=lambda: events.append('report'),
            _a15_canonical_action=SimpleNamespace(trigger=lambda: events.append('canonical')),
            _open_legacy=lambda: events.append('legacy'),
            v020_show_reporting_page=lambda: events.append('reporting_page'),
            v020_show_preservation_page=lambda: events.append('preservation_page'),
        )
        self.page = SimpleNamespace(window=self.window,
                                    _snapshot=SimpleNamespace(has_job=True),
                                    refresh=lambda: events.append('refresh'))

    def test_depot_review_and_canonical_use_existing_actions(self):
        self.action(self.page, 'review')
        self.action(self.page, 'generate')
        self.action(self.page, 'dias_link')
        self.assertEqual(self.events,
                         [('results', {'depot': True}), 'refresh', 'report', 'refresh',
                          'canonical', 'refresh'])

    def test_legacy_packing_requires_explicit_confirmation(self):
        self.action(self.page, 'legacy')
        self.assertEqual(self.events, ['confirmation', 'legacy', 'refresh'])

    def test_running_jobs_block_decision_and_preservation_actions(self):
        self.window.api.running = True
        self.action(self.page, 'review')
        self.action(self.page, 'legacy')
        self.assertEqual(self.events, ['warning', 'warning'])
        self.window.api.running = False
        self.window._worker = object()
        self.action(self.page, 'dias_link')
        self.assertEqual(self.events[-1], 'warning')

    def test_no_selected_job_cannot_launch_decisions(self):
        self.page._snapshot = SimpleNamespace(has_job=False)
        self.action(self.page, 'review')
        self.assertEqual(self.events, ['info'])

    def test_navigation_does_not_require_a_job_or_make_files(self):
        self.page._snapshot = None
        self.action(self.page, 'reporting')
        self.action(self.page, 'preservation')
        self.assertEqual(self.events, ['reporting_page', 'preservation_page'])


if __name__ == '__main__':
    unittest.main()
