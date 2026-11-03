"""A8 correction: saved progress, selected-job isolation and dock toggle."""
from __future__ import annotations

import ast
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from app.run_progress_v018_a8 import saved_progress

ROOT = Path(__file__).resolve().parents[1]


def details(job_id='JOB-002', status='Ferdig', current=2, count=2, progress=1.0):
    job=SimpleNamespace(job_id=job_id, name='uttrekk', status=status,
                        current_operation=current, operation_count=count, progress=progress)
    ops=tuple(SimpleNamespace(position=i+1,name=f'Test {i+1}',completed=i<current)
              for i in range(count))
    return SimpleNamespace(job=job,operations=ops,message='Workflow fullført' if status=='Ferdig' else '')


class ProgressTest(unittest.TestCase):
    def test_completed_job_is_visible_after_restart_without_detailed_log(self):
        snap=saved_progress(details())
        self.assertIn('Ferdig · 2/2',snap.title)
        self.assertEqual(snap.percent,100)
        self.assertEqual(len(snap.lines),2)
        self.assertIn('ikke en detaljert historisk kjørelogg',snap.log_text)
        self.assertIn('Test 2',snap.log_text)

    def test_ready_job_is_not_described_as_a_finished_run(self):
        snap=saved_progress(details('JOB-001','Klar',0,9,0.0))
        self.assertEqual(snap.percent,0)
        self.assertIn('Ingen fullført kjøring',snap.log_text)
        self.assertEqual(len(snap.lines),9)
        self.assertTrue(all('Ikke fullført' in row for row in snap.lines))

    def test_partial_job_does_not_mark_incomplete_operations_ok(self):
        snap=saved_progress(details('JOB-003','Feil',1,3,0.33))
        self.assertEqual(snap.percent,33)
        self.assertIn('OK (lagret)',snap.lines[0])
        self.assertNotIn('OK (lagret)',snap.lines[1])
        self.assertNotIn('OK (lagret)',snap.lines[2])


class FakeCombo:
    def __init__(self):self.rows=[];self.index=-1
    def blockSignals(self,v):return False
    def clear(self):self.rows=[];self.index=-1
    def addItem(self,label,data):self.rows.append((label,data));self.index=0 if self.index<0 else self.index
    def currentData(self):return self.rows[self.index][1] if self.index>=0 else None
    def findData(self,data):return next((i for i,(_,v) in enumerate(self.rows) if v==data),-1)
    def setCurrentIndex(self,i):self.index=i


class FakeScroll:
    def __init__(self):self.val=0
    def value(self):return self.val
    def setValue(self,value):self.val=value
    def maximum(self):return 999


class FakeText:
    def __init__(self):self.value='';self.scroll=FakeScroll()
    def setPlainText(self,text):self.value=text
    def clear(self):self.value=''
    def verticalScrollBar(self):return self.scroll


class FakeLabel:
    def __init__(self):self.value=''
    def setText(self,v):self.value=v


class FakeProgress:
    def __init__(self):self.value=0
    def setValue(self,v):self.value=v


class FakeDock:
    def __init__(self):self.floating=False;self.shown=0
    def isFloating(self):return self.floating
    def setFloating(self,v):self.floating=v
    def show(self):self.shown+=1
    def raise_(self):pass
    def activateWindow(self):pass


class FakeAPI:
    def __init__(self):
        self.jobs={'JOB-001':details('JOB-001','Klar',0,9,0),
                   'JOB-002':details('JOB-002','Ferdig',9,9,1)}
        self.current_list='A.n5jobs'
        self.paths={'JOB-001':'X:/A/dwm','JOB-002':'X:/B/dwm'}
        self.logs={'JOB-002':[]}
    def workspace(self):
        return SimpleNamespace(job_list_path=self.current_list,
                               jobs=[SimpleNamespace(job_id=k,effective_work_operations=v)
                                     for k,v in self.paths.items()])
    def job_details(self,job_id):return self.jobs[job_id]
    def saved_job_log(self,job_id):return ''
    def run_log_history(self,job_id):return self.logs.get(job_id,())
    def read_run_log(self,job_id,run_id):return f'Logg for {job_id} {run_id}'


def headless_ui_methods():
    """Exercise actual GUI function bodies without importing PySide6."""
    source=(ROOT/'gui_qt'/'main_window.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    gui=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DwmMainWindow')
    names={'_a8_show_job_log','_a8_float_job_log','_a8_update_log_window_buttons',
           '_a8_refresh_job_log','_a8_show_selected_run','_a8_restore_run_context'}
    methods=[node for node in gui.body if isinstance(node,ast.FunctionDef) and node.name in names]
    namespace={'saved_progress':saved_progress}
    code=compile(ast.fix_missing_locations(ast.Module(body=methods,type_ignores=[])),'gui_qt/main_window.py','exec')
    exec(code,namespace)
    return type('UiMethods',(),{name:namespace[name] for name in names})


class FakeWindow(headless_ui_methods()):
    def __init__(self):
        self.api=FakeAPI()
        self._active_id='JOB-001'
        self._job_log_selected_job=None
        self._job_log_last_options=()
        self._a8_run_context=None
        self._a8_live_job=None
        self.job_run_combo=FakeCombo()
        self.job_log_text=FakeText()
        self.log_follow=SimpleNamespace(isChecked=lambda:True)
        self.run_summary=FakeLabel()
        self.run_events=FakeText()
        self.run_progress_bar=FakeProgress()
        self.dock_log=FakeDock()
        self.log_window_button=FakeLabel()
        self.float_job_log_action=FakeLabel()
        self._detached_log_window=None

    def _a9_sync_detached_log_choices(self):
        pass

    def _a9_sync_detached_run(self):
        pass


class UiBehaviorTest(unittest.TestCase):
    def test_job_switch_replaces_run_status_and_log_instead_of_leaking(self):
        ui=FakeWindow()
        ui._a8_restore_run_context()
        ui._a8_refresh_job_log()
        self.assertIn('JOB-001',ui.run_summary.value)
        self.assertEqual(ui.run_progress_bar.value,0)
        self.assertIn('Ingen faktisk kjørelogg',ui.job_log_text.value)
        ui._active_id='JOB-002'
        ui._a8_restore_run_context()
        ui._a8_refresh_job_log()
        self.assertIn('JOB-002',ui.run_summary.value)
        self.assertEqual(ui.run_progress_bar.value,100)
        self.assertIn('Ingen faktisk kjørelogg',ui.job_log_text.value)
        self.assertNotIn('JOB-001',ui.job_log_text.value)

    def test_old_joblist_entries_are_selectable_when_no_a8_file_exists(self):
        ui=FakeWindow()
        ui._active_id='JOB-002'
        ui.api.saved_job_log=lambda job_id: 'START: Gammelt testløp\nOK: Ferdig' if job_id=='JOB-002' else ''
        ui._a8_refresh_job_log()
        self.assertEqual(ui.job_run_combo.currentData(),'__legacy__')
        self.assertIn('Gammelt testløp',ui.job_log_text.value)
        self.assertEqual(ui.job_run_combo.findData('__snapshot__'), -1)
        self.assertEqual(ui.job_run_combo.currentData(), '__legacy__')
        self.assertIn('Gammelt testløp',ui.job_log_text.value)

    def test_changing_joblist_with_same_job_id_clears_history_context(self):
        ui=FakeWindow()
        ui._a8_refresh_job_log()
        oldkey=ui._job_log_selected_job
        ui.api.current_list='B.n5jobs'
        ui.api.paths['JOB-001']='X:/Different/dwm'
        ui._a8_refresh_job_log()
        self.assertNotEqual(oldkey,ui._job_log_selected_job)
        self.assertEqual(ui._job_log_selected_job[0],'B.n5jobs')
        self.assertIn('Different',ui._job_log_selected_job[2])

    def test_actual_run_is_preferred_over_summary_and_previous_can_be_selected(self):
        ui=FakeWindow()
        ui._active_id='JOB-002'
        run=SimpleNamespace(run_id='20261103T180000Z-aabbccdd',status='finished',started_at='2026-11-03T18:00:00')
        ui.api.logs['JOB-002']=[run]
        ui._a8_refresh_job_log()
        self.assertEqual(ui.job_run_combo.currentData(),run.run_id)
        self.assertIn(run.run_id,ui.job_log_text.value)
        self.assertEqual(ui.job_run_combo.findData('__snapshot__'), -1)
        self.assertEqual(ui.job_run_combo.currentData(), run.run_id)
        self.assertIn(run.run_id, ui.job_log_text.value)

    def test_log_button_uses_normal_independent_window_instead_of_floating_dock(self):
        # A native floating QDockWidget stays above the main window on Windows.
        # Since a9 the user-facing 'Eget vindu' action opens an independent
        # Qt.Window, so overlapping windows follow ordinary OS stacking rules.
        source=(ROOT/'gui_qt'/'main_window.py').read_text(encoding='utf-8')
        viewer=(ROOT/'gui_qt'/'detached_log_window_v018_a9.py').read_text(encoding='utf-8')
        self.assertIn('viewer = DetachedJobLogWindow()', source)
        self.assertIn('self._a9_redock_job_log()', source)
        self.assertIn('self.dock_log.hide()', source)
        self.assertNotIn('self.dock_log.setFloating(floating)', source)
        self.assertIn('super().__init__(None, Qt.WindowType.Window)', viewer)


if __name__=='__main__':unittest.main()
