"""v0.2.0-a3: Qt-neutral regressions and a real temporary-dir ingest smoke test.

Tests do not require PySide6; the real Windows UI is verified separately.
"""
from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path, PureWindowsPath
from types import ModuleType, SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from app.ingest_controller_v020_a3 import (
    DEFAULT_RECEIVING_SETUP, IngestRequest, available_profiles, prepare_ingest,
    preview_ingest, create_ingest,
)

ROOT = Path(__file__).resolve().parents[1]
QT = ROOT / 'gui_qt' / 'ingest_v020_a3.py'
AV = ROOT / 'gui_qt' / 'antivirus_v020_a3.py'
HOME = ROOT / 'gui_qt' / 'production_home_v020_a2.py'
AREAS = ROOT / 'app' / 'ui_work_areas_v020_a2.py'


def extract_method(source: Path, class_name: str, method_name: str, **global_scope):
    root = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(node for node in root.body if isinstance(node, ast.ClassDef)
               and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == method_name)
    scope = dict(global_scope)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(source), 'exec'), scope)
    return scope[method_name]


class PureIngestA3Tests(unittest.TestCase):
    def setUp(self):
        self.request = IngestRequest(
            'receipt', 'profile.json', 'ikamr', 'K:/', 'arkiv-karantene-01',
            '1505', 'E-1505-2026-0001', '1505_019 prøve',
        )
        self.calls = []
        self.fake_profile = SimpleNamespace(profile_id='ikamr', name='Test',
                                            operations_folder='repository_operations')
        self.fake_plan = SimpleNamespace(
            mode='receipt', disk=Path('/disk'),
            group=Path('/disk/arkiv-karantene-01'),
            root=Path('/disk/arkiv-karantene-01/E-1505-2026-0001'),
            receipt_root=Path('/disk/arkiv-karantene-01/E-1505-2026-0001'),
            receipt_number='E-1505-2026-0001', owner_code='1505',
            label='1505_019 prøve', extraction_id='', ingest_date='',
            paths=(Path('/disk/arkiv-karantene-01/E-1505-2026-0001'),),
            profile=self.fake_profile,
            audit_path=Path('/disk/arkiv-karantene-01/E-1505-2026-0001/ingest.events.jsonl'),
        )
        self.backend = ModuleType('app.grouped_ingest')
        self.backend.grouped_profiles = lambda file: (self.calls.append(('profiles', file)) or
                                                     (self.fake_profile,))
        self.backend.plan_receipt = lambda *args, **kwargs: (
            self.calls.append(('receipt', args, kwargs)) or self.fake_plan)
        self.backend.plan_extraction = lambda *args, **kwargs: (
            self.calls.append(('extraction', args, kwargs)) or
            replace_plan(self.fake_plan, mode='extraction',
                         root=Path('/disk/arkiv-karantene-01/2026-11-14_1505_019_E-1505-2026-0001'),
                         extraction_id='1505_019', ingest_date='2026-11-14'))

    def test_receipt_delegates_without_side_effects(self):
        with patch.dict('sys.modules', {'app.grouped_ingest': self.backend}):
            self.assertEqual(available_profiles('profile.json'), (self.fake_profile,))
            plan = prepare_ingest(self.request)
        self.assertIs(plan, self.fake_plan)
        name, args, kwargs = self.calls[-1]
        self.assertEqual(name, 'receipt')
        self.assertEqual(args[0:2], ('K:/', 'arkiv-karantene-01'))
        self.assertIs(args[2], self.fake_profile)
        self.assertEqual(args[3:], ('1505', 'E-1505-2026-0001', '1505_019 prøve'))
        self.assertEqual(kwargs, {'info_xml': None})
        self.assertIn('flat E-mappe', preview_ingest(plan))
        self.assertIn('Ingen filer', preview_ingest(plan))

    def test_extraction_uses_the_same_backend_with_separate_arguments(self):
        request = replace(self.request, mode='extraction',
                          extraction_id='1505_019', unpack_date='2026-11-14')
        with patch.dict('sys.modules', {'app.grouped_ingest': self.backend}):
            plan = prepare_ingest(request)
        self.assertEqual(self.calls[-1][0], 'extraction')
        self.assertEqual(self.calls[-1][1][-2:], ('1505_019', '2026-11-14'))
        self.assertIn('separat fra mottaksmappen', preview_ingest(plan))
        # pathlib uses backslashes on Windows, forward slashes on Unix.
        expected_log = plan.root / plan.profile.operations_folder / 'depot-log.txt'
        self.assertIn('Uttrekkslogg: ' + str(expected_log), preview_ingest(plan))

    def test_extraction_preview_keeps_windows_log_paths(self):
        # Simulate the user's Windows paths even when this test runs on Linux.
        group = PureWindowsPath(r'K:\arkiv-karantene-01')
        receipt = group / 'E-1505-2026-0001'
        extraction = group / '2026-11-14_1505_019_E-1505-2026-0001'
        plan = replace_plan(
            self.fake_plan, mode='extraction', group=group, root=extraction,
            receipt_root=receipt, paths=(extraction,),
            audit_path=receipt / 'ingest.events.jsonl',
            extraction_id='1505_019', ingest_date='2026-11-14',
        )
        preview = preview_ingest(plan)
        self.assertIn(
            'Uttrekkslogg: ' + str(extraction / 'repository_operations' / 'depot-log.txt'),
            preview,
        )
        self.assertIn(
            'Portabel hendelseslogg: ' + str(extraction / 'repository_operations' / 'ingest.events.jsonl'),
            preview,
        )

    def test_unknown_profile_and_unknown_mode_cannot_create(self):
        with patch.dict('sys.modules', {'app.grouped_ingest': self.backend}):
            with self.assertRaises(ValueError):
                prepare_ingest(replace(self.request, profile_id='wrong'))
            with self.assertRaises(ValueError):
                prepare_ingest(replace(self.request, mode='invalid'))
        self.assertFalse(any(c[0] in ('receipt', 'extraction') for c in self.calls))

    def test_info_xml_is_validated_by_existing_reader(self):
        reader = ModuleType('app.receiving_folders')
        reader.read_info_xml = lambda path: self.calls.append(('xml', path)) or {'label': 'test'}
        with patch.dict('sys.modules', {'app.grouped_ingest': self.backend,
                                        'app.receiving_folders': reader}):
            prepare_ingest(replace(self.request, info_xml='incoming/info.xml'))
        self.assertIn(('xml', 'incoming/info.xml'), self.calls)

    def test_create_only_delegates_to_existing_audited_engine(self):
        identity = ModuleType('app.identity_provider')
        identity.LocalUserProfileIdentityProvider = lambda: SimpleNamespace(
            current_identity=lambda: 'current-actor'
        )
        self.backend.create_grouped_ingest = lambda plan, *, actor: (
            self.calls.append(('create', plan, actor)) or (plan.root,)
        )
        with patch.dict('sys.modules', {'app.grouped_ingest': self.backend,
                                        'app.identity_provider': identity}):
            result = create_ingest(self.fake_plan)
        self.assertEqual(result, (self.fake_plan.root,))
        self.assertIn(('create', self.fake_plan, 'current-actor'), self.calls)


def replace_plan(plan, **changes):
    return SimpleNamespace(**{**vars(plan), **changes})


class ExplicitConsentA3Tests(unittest.TestCase):
    def test_neither_cancel_nor_busy_job_can_create_receipt(self):
        messages = []

        class QMessageBox:
            StandardButton = SimpleNamespace(Yes=1, No=0)
            @staticmethod
            def question(*args):
                return 0  # user declined
            @staticmethod
            def warning(*args):
                messages.append('warning')

        created = []
        method = extract_method(QT, 'IngestPage', '_create',
                 QMessageBox=QMessageBox,
                 create_ingest=lambda plan: created.append(plan),
                 save_config=lambda _: None)
        plan = SimpleNamespace(paths=(Path('/tmp/receipt'),), root=Path('/tmp/receipt'),
                               receipt_number='E-1505-2026-0001', label='Test')
        ui = SimpleNamespace(window=SimpleNamespace(_worker=None, api=SimpleNamespace(running=False)),
                             _preview=lambda: plan, _preview_plan=plan)
        method(ui)
        self.assertEqual(created, [])
        ui.window.api.running = True
        method(ui)
        self.assertEqual(created, [])
        self.assertEqual(messages, ['warning'])

    def test_confirmation_creates_exactly_once_and_disables_repeat(self):
        created, saved, informed = [], [], []

        class QMessageBox:
            StandardButton = SimpleNamespace(Yes=1, No=0)
            @staticmethod
            def question(*args):
                return 1
            @staticmethod
            def information(*args):
                informed.append(args)
            @staticmethod
            def warning(*args):
                self.fail('not expected')

        class Target:
            def __init__(self):
                self.last = None
            def setEnabled(self, state):
                self.last = state
            def setText(self, value):
                self.last = value
            def setPlainText(self, value):
                self.last = value
            def text(self):
                return 'profile.json'

        directory = Path('/tmp/e-receipt')
        plan = SimpleNamespace(paths=(directory,), root=directory,
               receipt_number='E-1505-2026-0001', label='Demo', mode='receipt',
               disk=Path('/tmp'), group=Path('/tmp/group'),
               audit_path=directory / 'ingest.events.jsonl')
        create_button, preview, status, setup_file = Target(), Target(), Target(), Target()
        window = SimpleNamespace(_worker=None, api=SimpleNamespace(running=False))
        stub = SimpleNamespace(window=window, _preview=lambda: plan,
            _preview_plan=plan, create_button=create_button, preview=preview,
            status=status, setup_file=setup_file, _last_extraction=None)
        method = extract_method(QT, 'IngestPage', '_create',
            QMessageBox=QMessageBox, create_ingest=lambda plan: (
                created.append(plan) or (plan.root,)),
            save_config=lambda changes: saved.append(changes),
            preview_ingest=lambda plan: 'Preview: ' + str(plan.root))
        method(stub)
        self.assertEqual(created, [plan])
        self.assertEqual(len(informed), 1)
        self.assertEqual(create_button.last, False)
        self.assertIn('OPPRETTET OG LOGGFØRT', preview.last)
        self.assertEqual(saved[0]['last_ingest_group'], 'group')

    def test_save_preset_contains_only_non_sensitive_defaults(self):
        class Field:
            def __init__(self, value):
                self.value = value
            def text(self):
                return self.value
            def currentData(self):
                return self.value
        ui = SimpleNamespace(
            setup_file=Field('config.json'), profile=Field('ikamr'),
            disk=Field('K:/'), group=Field('arkiv-karantene-08'),
            owner=Field('1505'), mode=Field('receipt'),
        )
        method = extract_method(QT, 'IngestPage', '_preset_values')
        result = method(ui)
        self.assertEqual(set(result), {'setup_file', 'folder_profile_id', 'disk',
                                       'group', 'owner_code', 'default_mode'})
        self.assertEqual(result['default_mode'], 'Mottak')
        self.assertNotIn('receipt_number', result)
        self.assertNotIn('info_xml', result)

    def test_ui_refresh_recomputes_plan_after_consent_button(self):
        source = QT.read_text(encoding='utf-8')
        self.assertIn('plan = self._preview()', source)
        self.assertIn('QMessageBox.question(', source)
        self.assertIn('QMessageBox.StandardButton.No', source)
        self.assertIn('create_ingest(plan)', source)
        self.assertLess(source.index('plan = self._preview()', source.index('def _create')),
                        source.index('create_ingest(plan)', source.index('def _create')))
        self.assertNotIn('from gui.grouped_ingest_dialog', source)
        self.assertNotIn('subprocess', source)


class AntivirusContractA3Tests(unittest.TestCase):
    def test_antivirus_page_is_not_a_fake_scan_or_approval(self):
        source = AV.read_text(encoding='utf-8')
        self.assertIn('Status: IKKE SKANNET', source)
        self.assertIn('setReadOnly(True)', source)
        self.assertIn('v020_integrated_home()', source)
        for danger in ('subprocess.', 'QProcess', 'scan_is_clean', 'save_scan_result',
                       'create_grouped_ingest(', 'approved=True'):
            self.assertNotIn(danger, source)

    def test_home_integrates_three_pages_and_keeps_existing_work(self):
        source = HOME.read_text(encoding='utf-8')
        for fragment in (
            'ingest = IngestPage(window)', 'antivirus = AntivirusPage(window)',
            'stack.addWidget(ingest)', 'stack.addWidget(antivirus)',
            'window.v020_show_ingest_page = show_ingest',
            'window.v020_show_antivirus_page = show_antivirus',
            "window._a2_set_step('work')", 'saved_advanced is None',
        ):
            self.assertIn(fragment, source)
        self.assertIn('window.v020_go_to_work = go_to_work', source)


@unittest.skipUnless((ROOT / 'app' / 'grouped_ingest.py').is_file(),
                     'Full DWM backend required for real temporary-dir smoke test')
class RealIngestBackendSmokeA3Tests(unittest.TestCase):
    """Uses real DWM backend on TEMP directories, never a real quarantine disk."""

    def test_flat_receipt_and_separate_extraction_log_are_preserved(self):
        with TemporaryDirectory(prefix='dwm-a3-ingest-') as temp:
            base = Path(temp)
            disk = base / 'disk'
            group = disk / 'arkiv-karantene-01'
            group.mkdir(parents=True)
            setup = base / 'profiles.json'
            setup.write_text(json.dumps({
                'file_type': 'dwm-receiving-folder-profiles',
                'format_version': 1,
                'profiles': [{
                    'id': 'test', 'name': 'Test – gruppe',
                    'grouped_ingest': {
                        'group_prefix': 'arkiv-karantene-',
                        'extraction_pattern': '{date}_{extraction_id}_{receipt_number}',
                        'receipt_log': 'ingest.events.jsonl',
                        'operations_folder': 'repository_operations',
                        'extraction_folders': [
                            'content/sip', 'content/tar', 'descriptive_metadata',
                            'repository_operations/abstract',
                            'repository_operations/quarantine',
                            'repository_operations/utilities',
                        ],
                    },
                }],
            }), encoding='utf-8')
            receipt = IngestRequest('receipt', str(setup), 'test', str(disk),
                                    group.name, '1505', 'E-1505-2026-0001', 'Demo')
            planned = prepare_ingest(receipt)
            self.assertFalse(planned.root.exists())
            self.assertEqual(len(planned.paths), 1)
            self.assertIn('flat E-mappe', preview_ingest(planned))
            create_ingest(planned)
            self.assertTrue(planned.root.is_dir())
            self.assertTrue((planned.root / 'ingest.events.jsonl').is_file())
            self.assertTrue((planned.root / 'depot-log.txt').is_file())
            self.assertEqual({p.name for p in planned.root.iterdir()},
                             {'ingest.events.jsonl', 'depot-log.txt'})
            extraction = replace(receipt, mode='extraction', extraction_id='1505_019',
                                 unpack_date='2026-11-14')
            planned_extract = prepare_ingest(extraction)
            self.assertEqual(planned_extract.root.parent, group)
            self.assertFalse(planned_extract.root.exists())
            create_ingest(planned_extract)
            self.assertTrue((planned_extract.root / 'content' / 'sip').is_dir())
            self.assertTrue((planned_extract.root / 'repository_operations' /
                             'ingest.events.jsonl').is_file())
            records = [json.loads(line) for line in
                       (planned.receipt_root / 'ingest.events.jsonl').read_text(
                           encoding='utf-8').splitlines() if line.strip()]
            self.assertEqual(len(records), 2)


if __name__ == '__main__':
    unittest.main()
