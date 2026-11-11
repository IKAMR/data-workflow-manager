"""Headless protection for Basic control presets and selected assessment bases."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import csv
import sys
import tempfile
import unittest

from app.basic_start_v0111_a1 import (
    BASIC_WORKFLOW_ID, BASIC_ARKADE_WORKFLOW_ID, prepare_basic_plan,
    select_or_create_basic_job, BasicControlPlan,
)
from app.format_assessment_v0111_a2 import (
    DEFAULT_FORMAT_SOURCE, FORMAT_SOURCE_ARKADE_RAF,
    FORMAT_SOURCE_NASJONALARKIVET, chosen_format_source,
    historical_arkade_status, require_format_source,
)

ROOT = Path(__file__).resolve().parents[1]
STANDARD = ('metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
            'run_noark5_xpath_tests_2026', 'compose_noark5_views',
            'build_noark5_depot_report')
ARKADE = STANDARD[:3] + ('arkade5_noark5_test', 'arkade5_pronom_analysis') + STANDARD[3:]


class AssessmentSourceTests(unittest.TestCase):
    def test_two_sources_only_and_default_is_dated_list(self):
        self.assertEqual(chosen_format_source({}), DEFAULT_FORMAT_SOURCE)
        self.assertEqual(chosen_format_source({}), FORMAT_SOURCE_NASJONALARKIVET)
        self.assertEqual(chosen_format_source({'format_assessment_source': FORMAT_SOURCE_ARKADE_RAF}),
                         FORMAT_SOURCE_ARKADE_RAF)
        for value in ('', '../outside.json', 'unknown', 'noark5_dwm'):
            with self.assertRaises(ValueError):
                require_format_source(value)

    def test_historical_raf_is_a_source_value_not_new_legal_approval(self):
        cases = {
            'Gyldig': ('valid', 'Gyldig arkivformat'),
            'Gyldig*': ('conditional', 'Gyldig med forbehold'),
            'Gyldig med forbehold': ('conditional', 'Gyldig med forbehold'),
            'Ikke gyldig': ('invalid', 'Ikke gyldig arkivformat'),
            'ugyldig': ('invalid', 'Ikke gyldig arkivformat'),
            'Ukjent': ('unknown', 'Ukjent'),
            None: ('unknown', 'Ukjent'),
            'undocumented value': ('unknown', 'Ukjent'),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                actual = historical_arkade_status(raw)
                self.assertEqual((actual.code, actual.label), expected)

    def test_original_raf_not_rewritten(self):
        observed = {'RAF-220301': 'Gyldig*', 'Format-ID': 'fmt/101'}
        historical_arkade_status(observed['RAF-220301'])
        self.assertEqual(observed['RAF-220301'], 'Gyldig*')
        self.assertEqual(observed['Format-ID'], 'fmt/101')


class BasicWorkflowTests(unittest.TestCase):
    def _modules(self, calls=None):
        def workflow(identifier):
            if calls is not None:
                calls.append(identifier)
            if identifier == BASIC_WORKFLOW_ID:
                return SimpleNamespace(profile_id='noark5', operation_ids=STANDARD)
            if identifier == BASIC_ARKADE_WORKFLOW_ID:
                return SimpleNamespace(profile_id='noark5', operation_ids=ARKADE)
            return None
        return {
            'app.job_preflight_v018_a6': SimpleNamespace(check_extraction_folder=lambda *_a, **_kw: ()),
            'app.storage_profiles_v0110_a2': SimpleNamespace(resolve_storage_profile=lambda _settings: 'standard_enkel'),
            'app.workflow_sequences': SimpleNamespace(workflow_sequence_by_id=workflow),
        }

    def test_extended_profile_produces_real_arkade_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, work = Path(tmp) / 'source', Path(tmp) / 'work'
            source.mkdir(); work.mkdir()
            calls = []
            with patch.dict(sys.modules, self._modules(calls)):
                result = prepare_basic_plan(source, work, {}, workflow_id=BASIC_ARKADE_WORKFLOW_ID)
            self.assertEqual(result.workflow_id, BASIC_ARKADE_WORKFLOW_ID)
            self.assertEqual(result.operation_ids, ARKADE)
            self.assertEqual(calls, [BASIC_ARKADE_WORKFLOW_ID])
            self.assertEqual(result.work_operations, work)
            self.assertFalse(list(work.iterdir()))

    def test_standard_has_no_arkade_or_aip(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, work = Path(tmp) / 'source', Path(tmp) / 'work'
            source.mkdir(); work.mkdir()
            with patch.dict(sys.modules, self._modules()):
                result = prepare_basic_plan(source, work, {})
            self.assertEqual(result.operation_ids, STANDARD)
            self.assertNotIn('dias_package', result.operation_ids)

    def test_unknown_sequence_is_never_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, work = Path(tmp) / 'source', Path(tmp) / 'work'
            source.mkdir(); work.mkdir()
            with patch.dict(sys.modules, self._modules()):
                with self.assertRaisesRegex(ValueError, 'Ukjent Basic'):
                    prepare_basic_plan(source, work, {}, workflow_id='dias_package')

    def test_cli_must_be_available_before_creating_extended_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            plan = BasicControlPlan(work / 'source', work, work, 'standard_enkel',
                                    ARKADE, BASIC_ARKADE_WORKFLOW_ID)
            class Api:
                calls = 0
                def check_arkade5_cli(self):
                    return SimpleNamespace(severity='error', message='Filen mangler')
                def create_job(self, **kwargs):
                    self.calls += 1
                    raise AssertionError('must never create a job')
            api = Api()
            with self.assertRaisesRegex(ValueError, 'Arkade 5 CLI er ikke klar'):
                select_or_create_basic_job(api, plan)
            self.assertEqual(api.calls, 0)

    def test_extended_job_output_remains_selected_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            plan = BasicControlPlan(work / 'source', work, work, 'standard_enkel',
                                    ARKADE, BASIC_ARKADE_WORKFLOW_ID)
            self.assertEqual(plan.work_operations, work)
            self.assertNotIn('work/dwm', str(plan.work_operations).replace('\\', '/'))


class PackageContracts(unittest.TestCase):
    def test_setup_and_pronom_view_use_the_same_setting(self):
        setup = (ROOT / 'gui_qt/setup_format_v0111_a2.py').read_text('utf-8')
        result = (ROOT / 'gui_qt/result_center_v0111_a2.py').read_text('utf-8')
        api = (ROOT / 'app/workbench_api_v0111_a2.py').read_text('utf-8')
        self.assertIn("updates['format_assessment_source']", setup)
        self.assertIn('format_assessment_source', result)
        self.assertIn('format_assessment_source', api)
        self.assertIn("'noark5_standard_arkade'", (ROOT / 'app/basic_start_v0111_a1.py').read_text('utf-8'))

    def test_startup_and_main_window_reuse_existing_engines(self):
        entry = (ROOT / 'gui_qt/__main__.py').read_text('utf-8')
        gui = (ROOT / 'gui_qt/basic_main_v0111_a1.py').read_text('utf-8')
        self.assertIn('from app.workbench_api_v0111_a2 import DwmWorkbenchAPI', entry)
        self.assertIn('self._run_selected()', gui)
        self.assertIn('self._a12_open_selected_report', gui)
        self.assertIn('select_or_create_basic_job(self.api, plan)', gui)
        self.assertNotIn('subprocess.run(', gui)

    def test_readme_is_product_documentation_not_alpha_test_log(self):
        content = (ROOT / 'README.md').read_text('utf-8')
        self.assertNotIn('## Enkel start (fra v0.1.11-a1)', content)
        self.assertNotIn('v0.1.10 er ment for videre praktisk brukertesting', content)
        self.assertIn('## Brukergrensesnitt', content)
        self.assertIn('## Operasjonsarkitektur', content)


class PortableSettingsContractTests(unittest.TestCase):
    def test_format_source_is_a_known_exportable_setting(self):
        from settings import DEFAULT_CONFIG
        self.assertEqual(DEFAULT_CONFIG.get('format_assessment_source'),
                         FORMAT_SOURCE_NASJONALARKIVET)


if __name__ == '__main__':
    unittest.main()
