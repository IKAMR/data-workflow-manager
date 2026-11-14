"""v0.2.0-a2: production home routes, capability honesty and version boundary."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import tomllib
import unittest

from app.ui_work_areas_v020_a2 import AREA_BY_KEY, WORK_AREAS, cards_for, destination
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'gui_qt' / 'production_home_v020_a2.py'
SHELL = ROOT / 'gui_qt' / 'start_shell_v020_a1.py'
ENTRY = ROOT / 'gui_qt' / '__main__.py'

SECTION_DEFS = (
    ('ingest', 'Ingest', ''), ('antivirus', 'Antiviruskontroll', ''),
    ('workspace', 'Til arbeidsomr\u00e5de', ''), ('control', 'Kontroll', ''),
    ('report', 'Rapportering', ''), ('preserve', 'Bevaring', ''),
    ('crm', 'Mot intern CRM', ''), ('access', 'Innsyn', ''),
)


def load_gui_method(name, **globals_):
    """Exercise pure routing of the real Qt class without importing PySide6."""
    tree = ast.parse(HOME.read_text(encoding='utf8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'ProductionStartPage')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == name)
    env = {'destination': destination, **globals_}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],
                                               type_ignores=[])), str(HOME), 'exec'), env)
    return env[name]


class ProductionA2Tests(unittest.TestCase):
    def test_all_eight_areas_have_unique_keys_and_agreed_order(self):
        keys = [area.key for area in WORK_AREAS]
        self.assertEqual(keys, [entry[0] for entry in SECTION_DEFS])
        self.assertEqual(len(set(keys)), 8)

    def test_profile_visibility_does_not_reorder_production_steps(self):
        self.assertEqual([v[0] for v in cards_for({'report', 'control', 'ingest'}, SECTION_DEFS)],
                         ['ingest', 'control', 'report'])
        self.assertEqual([v[0] for v in cards_for({'control'}, SECTION_DEFS)], ['control'])
        self.assertEqual(cards_for((), SECTION_DEFS), ())

    def test_unimplemented_sections_are_non_actions(self):
        for key in ('crm', 'access'):
            self.assertEqual(AREA_BY_KEY[key].state, 'planned')
            self.assertIsNone(destination(key))
        with self.assertRaises(KeyError):
            destination('not-an-area')

    def test_ingest_qt_and_antivirus_are_truthfully_routed_in_a3(self):
        self.assertEqual(AREA_BY_KEY['ingest'].state, 'available')
        self.assertEqual(destination('ingest'), 'qt_ingest')
        self.assertEqual(AREA_BY_KEY['antivirus'].state, 'partial')
        self.assertEqual(destination('antivirus'), 'antivirus_info')
        self.assertEqual(AREA_BY_KEY['preserve'].state, 'partial')
        self.assertEqual(destination('preserve'), 'preservation')

    def test_existing_qt_destinations_are_explicit(self):
        self.assertEqual(destination('workspace'), 'basic_work')
        self.assertEqual(destination('control'), 'control')
        self.assertEqual(destination('report'), 'report')

    def test_open_section_does_not_run_any_processing_or_auto_approval(self):
        events = []
        stub = SimpleNamespace(
            accept=lambda: events.append('accept'),
            _close_and_run=lambda fn: events.append('schedule'),
            _open_existing_work_step=lambda: events.append('work'),
            _report_actions=lambda: events.append('report-options'),
            _preservation_actions=lambda: events.append('preservation-options'),
            _legacy_launch=lambda purpose: events.append('legacy-prompt'),
            window=SimpleNamespace(
                v020_show_ingest_page=lambda: events.append('ingest-qt'),
                v020_show_antivirus_page=lambda: events.append('antivirus-info'),
            ),
        )
        route = load_gui_method('_open_section')
        route(stub, 'crm')
        route(stub, 'access')
        self.assertEqual(events, [])
        route(stub, 'control')
        self.assertEqual(events, ['accept'])
        route(stub, 'workspace')
        route(stub, 'report')
        route(stub, 'preserve')
        route(stub, 'ingest')
        route(stub, 'antivirus')
        self.assertEqual(events, ['accept', 'schedule', 'report-options',
                                  'preservation-options', 'ingest-qt', 'antivirus-info'])

    def test_work_uses_existing_basic_step_without_creating_directories(self):
        events = []
        window = SimpleNamespace(
            _enter_basic=lambda: events.append('basic'),
            _a2_set_step=lambda step: events.append(('step', step)),
            v020_sync_navigation=lambda: events.append('sync'),
        )
        stub = SimpleNamespace(window=window)
        load_gui_method('_open_existing_work_step')(stub)
        self.assertEqual(events, ['basic', ('step', 'work'), 'sync'])

    def test_close_before_opening_a_second_dialog(self):
        events = []
        def run_immediately(delay, callback):
            events.append(('scheduled', delay))
            callback()
        timer = SimpleNamespace(singleShot=run_immediately)
        stub = SimpleNamespace(accept=lambda: events.append('accept'))
        load_gui_method('_close_and_run', QTimer=timer)(stub,
                lambda: events.append('callback'))
        self.assertEqual(events, ['accept', ('scheduled', 0), 'callback'])

    def test_existing_legacy_launcher_has_explicit_confirmation(self):
        code = HOME.read_text(encoding='utf8')
        self.assertIn('QMessageBox.question(', code)
        self.assertIn('self.window.api.running', code)
        self.assertIn('self._close_and_run(self.window._open_legacy)', code)
        self.assertIn('action.setEnabled(capability.route is not None)', code)
        self.assertNotIn('execute_job(', code)
        self.assertNotIn('start_dias_package(', code)

    def test_a2_entrypoint_preserves_a1_shell_and_control_engine(self):
        src = ENTRY.read_text(encoding='utf8')
        self.assertIn('DwmWorkbenchAPI()', src)
        self.assertIn('DwmMainWindow(api)', src)
        self.assertIn('install_start_navigation(window)', src)
        self.assertIn('install_setup_tab()', src)
        self.assertIn('install_canonical_results_menu(window)', src)
        self.assertIn('window.v020_start_page_factory = ProductionStartPage', src)
        nav = SHELL.read_text(encoding='utf8')
        self.assertIn("getattr(window, 'v020_start_page_factory', StartPage)", nav)
        self.assertIn('window.basic_advanced_button', nav)

    def test_release_and_distribution_agree(self):
        self.assertEqual(VERSION, '0.2.0-a3')
        with (ROOT / 'pyproject.toml').open('rb') as stream:
            project = tomllib.load(stream)['project']
        self.assertEqual(project['version'], '0.2.0a3')
        self.assertEqual(project['version'], VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
