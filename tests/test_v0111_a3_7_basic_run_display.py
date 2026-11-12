"""a3.7: stable pinned Basic status and reuse of Advanced run details."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.basic_run_feedback_v0111_a3 import elapsed_clock, planned_operation_rows

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'gui_qt' / 'basic_main_v0111_a1.py'


def method_source(name: str) -> str:
    source = UI.read_text('utf-8')
    cls = next(n for n in ast.parse(source).body
               if isinstance(n, ast.ClassDef) and n.name == 'DwmMainWindow')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == name)
    return ast.get_source_segment(source, method)


class BasicRunDisplayTests(unittest.TestCase):
    def test_signal_clock_changes_only_measured_elapsed_seconds(self):
        self.assertEqual(elapsed_clock(None, 50.0), '--:--:--')
        self.assertEqual(elapsed_clock(10, 10.5), '00:00:00')
        self.assertEqual(elapsed_clock(10, 16.8), '00:00:06')
        self.assertEqual(elapsed_clock(10, 71.3), '00:01:01')
        self.assertEqual(elapsed_clock(10, 3671.3), '01:01:01')
        self.assertEqual(len(elapsed_clock(10, 3671.3)), len(elapsed_clock(10, 16.8)))

    def test_planned_steps_are_from_one_authoritative_cursor(self):
        ops = [SimpleNamespace(operation_id=f'op{i}', name=f'Deljobb {i}', completed=i <= 1)
               for i in range(1, 5)]
        rows = planned_operation_rows(ops, 'Kjører', 1)
        self.assertEqual(len(rows), 4)
        self.assertEqual([r[2] for r in rows],
                         ['Fullført', 'Kjører', 'Ikke startet', 'Ikke startet'])
        self.assertEqual([r[3] for r in rows], ['op1', 'op2', 'op3', 'op4'])
        self.assertEqual([r[2] for r in planned_operation_rows(ops, 'Feil', 1)],
                         ['Fullført', 'Stoppet', 'Ikke startet', 'Ikke startet'])
        self.assertEqual([r[2] for r in planned_operation_rows(ops, 'Venter ved kontrollpunkt', 1)],
                         ['Fullført', 'Venter', 'Ikke startet', 'Ikke startet'])
        self.assertEqual([r[2] for r in planned_operation_rows(ops, 'Ferdig', 4)],
                         ['Fullført'] * 4)

    def test_pinned_status_stays_above_scrollable_form(self):
        code = method_source('_build_basic_page')
        self.assertIn('page_layout.addWidget(area, 1)', code)
        self.assertIn('self._build_basic_pinned_status(page, page_layout)', code)
        self.assertLess(code.index('self._build_basic_pinned_status(page, page_layout)'),
                        code.index('page_layout.addWidget(area, 1)'))
        self.assertIn("self.pages.addTab(page, 'Enkel start')", code)
        pinned = method_source('_build_basic_pinned_status')
        self.assertIn("setObjectName('basicPinnedRunStatus')", pinned)
        self.assertIn('self.basic_pinned_stop_button', pinned)
        self.assertIn('self.basic_pinned_details_button', pinned)
        self.assertIn('parent_layout.addWidget(panel)', pinned)
        self.assertIn('panel.hide()', pinned)

    def test_same_advanced_run_viewer_log_and_results_are_reused(self):
        code = method_source('_open_basic_run_details')
        self.assertIn('self._a9_float_run()', code)
        self.assertIn("getattr(self, '_detached_run_window', None)", code)
        self.assertIn('self._a9_sync_detached_run()', code)
        self.assertIn('self._basic_add_run_plan(viewer)', code)
        # No new job runner, no new API, no duplicated result log.
        self.assertNotIn('Thread(', code)
        self.assertNotIn('QPlainTextEdit(', code)
        plan = method_source('_basic_add_run_plan')
        self.assertIn('QTreeWidget(viewer)', plan)
        self.assertIn("['Nr.', 'Deljobb', 'Status']", plan)
        self.assertIn('viewer.layout().insertWidget(2, label)', plan)
        sync = method_source('_basic_sync_run_plan')
        self.assertIn('self.api.job_details(self._basic_job_id)', sync)
        self.assertIn('planned_operation_rows(', sync)
        self.assertIn('item.setText(2, status)', sync)
        self.assertIn('key != viewer._basic_plan_key', sync)

    def test_no_false_heartbeat_animation_and_stable_elapsed_label(self):
        code = method_source('_sync_basic_status')
        self.assertNotIn('self._basic_heartbeat_tick +=', code)
        self.assertNotIn("dots = '.'", code)
        self.assertIn('elapsed_clock(self._basic_last_run_signal, time.monotonic())', code)
        self.assertIn('self.basic_pinned_panel.setVisible(bool(busy and self._basic_active))', code)
        self.assertIn('self.basic_status.setVisible(not busy)', code)
        pinned = method_source('_build_basic_pinned_status')
        self.assertIn("self.basic_pinned_elapsed.setMinimumWidth(86)", pinned)
        self.assertIn('self.basic_pinned_message.setWordWrap(False)', pinned)

    def test_close_of_detailed_window_keeps_basic_docks_hidden(self):
        code = method_source('_a9_redock_run')
        self.assertIn('super()._a9_redock_run()', code)
        self.assertIn("getattr(self, 'dock_' + name).hide()", code)

    def test_full_stored_log_is_opened_by_the_same_advanced_log_action(self):
        code = method_source('_a11_open_history_log')
        self.assertIn('super()._a11_open_history_log(key)', code)
        self.assertIn('self._a8_float_job_log()', code)
        self.assertIn('self._a8_refresh_job_log(force=True)', code)
        self.assertNotIn('write_text', code)
        redock = method_source('_a9_redock_job_log')
        self.assertIn('super()._a9_redock_job_log()', redock)
        self.assertIn("getattr(self, 'dock_' + name).hide()", redock)


if __name__ == '__main__':
    unittest.main()
