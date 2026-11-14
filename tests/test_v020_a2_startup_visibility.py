"""v0.2.0-a2: startup page and 0/1/2 work-area maturity regression tests."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.operation_metadata import MATURITY_LEVELS, VISIBILITY_LABELS
from app.ui_start_preferences_v020_a2 import (
    UI_DEFAULTS, WORK_AREA_VISIBILITY_LABELS, validate_ui_preferences,
)
from app.ui_work_areas_v020_a2 import (
    AREA_BY_KEY, WORK_AREAS, cards_for, normalize_area_visibility,
)

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / 'gui_qt' / 'start_shell_v020_a1.py'
HOME = ROOT / 'gui_qt' / 'production_home_v020_a2.py'

SECTIONS = tuple((area.key, area.key, '') for area in WORK_AREAS)


def pure_startup_rules():
    source = ast.parse(SHELL.read_text(encoding='utf-8'))
    variables = {'PROFILE_KEY', 'PAGE_KEY', 'PROFILES', 'START_PAGES'}
    functions = {'normalize_profile', 'normalize_startpage', 'startup_page_target'}
    chosen = [node for node in source.body if (
        isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
            and target.id in variables for target in node.targets)
    ) or (isinstance(node, ast.FunctionDef) and node.name in functions)]
    context = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=chosen, type_ignores=[])),
                 str(SHELL), 'exec'), context)
    return context['startup_page_target']


class WorkAreaMaturityA2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.startup_page_target = staticmethod(pure_startup_rules())

    def test_matches_existing_siard_dwm_scale(self):
        self.assertEqual(MATURITY_LEVELS, {'alpha': 0, 'beta': 1, 'stable': 2})
        self.assertEqual(set(VISIBILITY_LABELS), {0, 1, 2})
        self.assertEqual(set(WORK_AREA_VISIBILITY_LABELS), set(VISIBILITY_LABELS))

    def test_eight_ordered_areas_are_visible_at_zero(self):
        self.assertEqual(UI_DEFAULTS['ui_area_visibility'], 0)
        self.assertEqual(len(cards_for((item.key for item in WORK_AREAS), SECTIONS, 0)), 8)

    def test_zero_one_two_filters_including_ingest(self):
        keys = [area.key for area in WORK_AREAS]
        self.assertEqual(AREA_BY_KEY['ingest'].maturity_level, 0)
        self.assertEqual([key for key, _, _ in cards_for(keys, SECTIONS, 1)],
                         ['workspace', 'control', 'report', 'preserve'])
        self.assertEqual([key for key, _, _ in cards_for(keys, SECTIONS, 2)],
                         ['workspace', 'control'])
        self.assertEqual([key for key, _, _ in cards_for(['control'], SECTIONS, 2)],
                         ['control'])

    def test_corrupt_visibility_setting_fails_closed(self):
        self.assertEqual(normalize_area_visibility(None), 0)
        for bad in (True, False, -1, 3, '0', [], object()):
            self.assertEqual(normalize_area_visibility(bad), 2)
        for bad in (True, 3, -1, '1'):
            with self.assertRaises(ValueError):
                validate_ui_preferences({'ui_area_visibility': bad})

    def test_fixed_start_page_overrides_profile_and_last(self):
        target = self.startup_page_target
        self.assertEqual(target({'ui_work_profile': 'control'}, 'home'), 'control')
        self.assertEqual(target({'ui_work_profile': 'depot'}, ''), 'home')
        self.assertEqual(target({'ui_startup_page': 'home', 'ui_work_profile': 'control'}, 'control'), 'home')
        self.assertEqual(target({'ui_startup_page': 'control', 'ui_work_profile': 'depot'}, 'home'), 'control')
        self.assertEqual(target({'ui_startup_page': 'last'}, 'home'), 'home')
        self.assertEqual(target({'ui_startup_page': 'last'}, 'control'), 'control')
        self.assertEqual(target({'ui_startup_page': 'last', 'ui_work_profile': 'depot'}, 'unknown'), 'home')

    def test_independent_start_page_and_control_mode(self):
        target = self.startup_page_target
        self.assertEqual(target({'ui_startup_page': 'home', 'ui_startup_mode': 'advanced'}, 'control'), 'home')
        self.assertEqual(validate_ui_preferences({'ui_startup_page': 'last', 'ui_area_visibility': 2}),
                         {'ui_startup_page': 'last', 'ui_area_visibility': 2})
        for invalid in ('', 'new', 1, None):
            with self.assertRaises(ValueError):
                validate_ui_preferences({'ui_startup_page': invalid})

    def test_qt_startup_preserves_last_page_on_close(self):
        home = HOME.read_text(encoding='utf-8')
        shell = SHELL.read_text(encoding='utf-8')
        self.assertIn("window.config.setValue('qt/v020_last_page', 'home')", home)
        self.assertIn("window.config.setValue('qt/v020_last_page', 'control')", home)
        self.assertIn('show_control(record=False)', home)
        self.assertIn('QTimer.singleShot(0, lambda: show_home(record=False))', home)
        self.assertIn('startup_page_target(', home)
        self.assertIn("'qt/v020_last_page'", home)
        self.assertIn("'Oppstartsside'", shell)
        self.assertIn("'Synlige arbeidsområder etter modenhet'", shell)
        self.assertIn('QScrollArea(self)', shell)
        self.assertIn('normalize_area_visibility(settings.get(AREA_VISIBILITY_KEY))', shell)

    def test_work_area_filter_does_not_touch_execution_contract(self):
        home = HOME.read_text(encoding='utf-8')
        self.assertIn('cards_for(visible_sections(settings), SECTIONS, threshold)', home)
        self.assertIn("capability.state_label + ' · ' + capability.maturity_label", home)
        self.assertNotIn('api.run_job(', home)
        self.assertNotIn('api.update_storage(', home)


if __name__ == '__main__':
    unittest.main()
