"""a3.4: independent Basic controls without breaking the two a2 presets."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from app.basic_start_v0111_a1 import (
    BASIC_CONTROLS, BASIC_ARKADE_WORKFLOW_ID, BASIC_WORKFLOW_ID,
    SIEGFRIED_OPERATION_ID, BasicControlPlan, basic_operation_ids,
    basic_options_for_operations, normalize_basic_controls,
    require_basic_arkade_cli, require_basic_siegfried,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ('metadata_inventory', 'validate_xml_schema', 'analyse_arkivstruktur',
        'run_noark5_xpath_tests_2026', 'compose_noark5_views',
        'build_noark5_depot_report')
ARKADE = BASE[:3] + ('arkade5_noark5_test', 'arkade5_pronom_analysis') + BASE[3:]


def loader(seq):
    if seq == BASIC_WORKFLOW_ID:
        return SimpleNamespace(profile_id='noark5', operation_ids=BASE)
    if seq == BASIC_ARKADE_WORKFLOW_ID:
        return SimpleNamespace(profile_id='noark5', operation_ids=ARKADE)
    return None


class FourControlTests(unittest.TestCase):
    def test_default_and_legacy_workflows_not_changed(self):
        self.assertEqual(basic_operation_ids(['dwm'], sequence_loader=loader), BASE)
        self.assertEqual(basic_operation_ids(['dwm','arkade_noark5','arkade_pronom'],
                                             sequence_loader=loader), ARKADE)
        self.assertEqual(basic_options_for_operations(ARKADE),
                         ('dwm','arkade_noark5','arkade_pronom'))

    def test_all_four_controls_are_independent(self):
        self.assertEqual(len(BASIC_CONTROLS), 4)
        self.assertEqual(basic_operation_ids(['siegfried'], sequence_loader=loader),
                         (SIEGFRIED_OPERATION_ID,))
        self.assertEqual(basic_operation_ids(['arkade_pronom'], sequence_loader=loader),
                         ('arkade5_pronom_analysis',))
        self.assertEqual(basic_operation_ids(['arkade_noark5'], sequence_loader=loader),
                         ('arkade5_noark5_test',))
        self.assertEqual(basic_operation_ids(['arkade_noark5','siegfried'], sequence_loader=loader),
                         ('arkade5_noark5_test', SIEGFRIED_OPERATION_ID))
        all_ids = basic_operation_ids(BASIC_CONTROLS, sequence_loader=loader)
        self.assertEqual(len(all_ids), len(set(all_ids)))
        for key in (SIEGFRIED_OPERATION_ID, 'arkade5_noark5_test','arkade5_pronom_analysis',
                    'run_noark5_xpath_tests_2026'):
            self.assertIn(key,all_ids)
        self.assertNotIn('dias_package',all_ids)

    def test_invalid_or_empty_controls_fail_closed(self):
        for value in ([], (), 'dwm', ['not_a_real_operation'], ['dwm','untrusted']):
            with self.subTest(value=value),self.assertRaises(ValueError):
                normalize_basic_controls(value)
        self.assertEqual(normalize_basic_controls(['siegfried','siegfried','dwm']),
                         ('dwm','siegfried'))

    def test_external_cli_only_required_when_selected(self):
        class Api:
            settings={}
            def check_arkade5_cli(self):
                raise AssertionError('Arkade 5 should not be probed')
        plan = BasicControlPlan(Path('/source'),Path('/work'),Path('/work'),
                                'standard',(SIEGFRIED_OPERATION_ID,))
        require_basic_arkade_cli(Api(),plan)
        no_cli = BasicControlPlan(Path('/source'),Path('/work'),Path('/work'),
                                  'standard',('arkade5_pronom_analysis',))
        with self.assertRaises(AssertionError):
            require_basic_arkade_cli(Api(),no_cli)

    def test_gui_uses_checkboxes_and_preserves_preflight_order(self):
        code = (ROOT/'gui_qt/basic_main_v0111_a1.py').read_text('utf-8')
        parsed = ast.parse(code)
        for text in ('DWM – Noark 5-test', 'Siegfried – PRONOM',
                     'Arkade 5 CLI – Noark 5-test', 'Arkade 5 CLI – PRONOM-analyse'):
            self.assertIn(text,code)
        cls=next(node for node in parsed.body if isinstance(node,ast.ClassDef)
                 and node.name=='DwmMainWindow')
        method=next(node for node in cls.body if isinstance(node,ast.FunctionDef)
                    and node.name=='_start_basic_control')
        calls={node.func.id:node.lineno for node in ast.walk(method)
               if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)}
        self.assertLess(calls['require_basic_arkade_cli'],calls['select_or_create_basic_job'])
        self.assertLess(calls['require_basic_siegfried'],calls['select_or_create_basic_job'])
        self.assertIn("qt/v0111_basic_options",code)
        self.assertIn('controls=self._selected_basic_controls()',code)

    def test_registry_is_exposed_and_results_are_separate(self):
        profile=(ROOT/'noark5_workflow/profile.py').read_text('utf-8')
        self.assertIn('SiegfriedPronomOperation',profile)
        gui=(ROOT/'gui_qt/basic_main_v0111_a1.py').read_text('utf-8')
        self.assertIn('result_center_siegfried_v0111_a3',gui)
        assert (ROOT/'noark5_workflow/operations/run_siegfried_pronom.py').exists()


if __name__=='__main__': unittest.main()
