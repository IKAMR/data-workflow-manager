"""a20.6: recovery search must display a completed plan before any user action.

These tests run without a display by executing the real dialog method against
minimal Tk/CTk doubles; they exercise its event queue and state transitions.
"""
from __future__ import annotations

import ast
import queue
import re
import sys
import threading
import unittest
from pathlib import Path, PureWindowsPath
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'gui' / 'jobs_window_v017_a2.py'


class Widget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.options = dict(kwargs)
        self.children = []
        self.exists = True
        self.text = ''
        self.after_callbacks = []
        if isinstance(master, Widget):
            master.children.append(self)

    def pack(self, **_kwargs):
        return self

    def pack_forget(self):
        self.hidden = True

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def winfo_exists(self):
        return self.exists

    def destroy(self):
        self.exists = False

    def winfo_screenheight(self):
        return 900

    def title(self, text):
        self.window_title = text

    def geometry(self, value):
        self.size = value

    def minsize(self, width, height):
        self.minimum = (width, height)

    def transient(self, _parent):
        pass

    def protocol(self, _name, callback):
        self.on_close = callback

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def delete(self, _start, _end):
        self.text = ''

    def insert(self, _start, content):
        self.text = str(content)

    def after(self, _delay, callback):
        self.after_callbacks.append(callback)

    def pump(self):
        callbacks = list(self.after_callbacks)
        self.after_callbacks.clear()
        for callback in callbacks:
            callback()

    def deiconify(self):
        self.options['deiconified'] = True

    def lift(self):
        self.options['lifted'] = True

    def focus_force(self):
        self.options['focused'] = True

    def click(self):
        if self.options.get('state', 'normal') != 'disabled':
            self.options['command']()


class UIFactory:
    def __init__(self):
        self.widgets = []
        self.windows = []

    def maker(self, category):
        def create(*args, **kwargs):
            widget = Widget(*args, **kwargs)
            self.widgets.append((category, widget))
            if category == 'window':
                self.windows.append(widget)
            return widget
        return create

    def select(self, category, *, text=None):
        for kind, widget in self.widgets:
            if kind != category:
                continue
            if text is None or widget.options.get('text') == text:
                return widget
        raise AssertionError(f'Widget missing: {category}, {text}')


class InlineThread:
    def __init__(self, *, target, daemon=False, name=None):
        self.target = target

    def start(self):
        self.target()


class FakeJobsWindow:
    def __init__(self):
        self._batch_running = False
        self.master = SimpleNamespace(_load_job_list_file=lambda *_a, **_k: True)
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1


class RecoveryDialogTests(unittest.TestCase):
    def setUp(self):
        factory = UIFactory()
        self.ui = factory
        self.prompt_count = {'directory': 0, 'question': 0}

        def askdirectory(**_kwargs):
            self.prompt_count['directory'] += 1
            return 'G:/arkiv-noark5'

        self.save_target = str(Path('C:/DWM') / 'gjenfunnet-arkiv-noark5.n5jobs')
        self.saved = []
        def save_recovered(plan, filename):
            self.saved.append((plan, filename))
            return Path(filename)

        self.module = ModuleType('noark5_workflow.reporting.report_job_discovery_a207')
        self.module.save_available_report_jobs = save_recovered
        self.messages = []
        def question(*_a, **_k):
            self.prompt_count['question'] += 1
            return True
        self.scope = {
            '__name__': 'gui.mock_recovery_a206',
            '__package__': 'gui',
            'FakeJobsWindow': FakeJobsWindow,
            'ctk': SimpleNamespace(
                CTkToplevel=factory.maker('window'),
                CTkLabel=factory.maker('label'),
                CTkProgressBar=factory.maker('progress'),
                CTkTextbox=factory.maker('textbox'),
                CTkFrame=factory.maker('frame'),
                CTkButton=factory.maker('button')),
            'theme': SimpleNamespace(SMALL_SIZE=11, BUTTON_BG='', BUTTON_HOVER='',
                                     font=lambda size: ('Segoe UI', 11)),
            'filedialog': SimpleNamespace(askdirectory=askdirectory,
                                          asksaveasfilename=lambda **_kwargs: self.save_target),
            'messagebox': SimpleNamespace(askyesno=question,
                showinfo=lambda *a,**k: self.messages.append(('info',a)),
                showerror=lambda *a,**k: self.messages.append(('error',a))),
            'queue': queue,
            're': re,
            'Path': Path,
            'threading': SimpleNamespace(Event=threading.Event, Thread=InlineThread),
        }
        src = ast.parse(SOURCE.read_text(encoding='utf-8'))
        definitions = []
        for entry in src.body:
            if isinstance(entry, ast.FunctionDef) and entry.name == '_recovery_preview_text':
                definitions.append(entry)
            elif isinstance(entry, ast.ClassDef) and entry.name == 'V017A2JobsWindow':
                entry.bases = [ast.Name(id='FakeJobsWindow',ctx=ast.Load())]
                definitions.append(entry)
        code = ast.fix_missing_locations(ast.Module(body=definitions,type_ignores=[]))
        exec(compile(code, str(SOURCE), 'exec'), self.scope)
        self.JobWindow = self.scope['V017A2JobsWindow']
        self._module_patch = patch.dict(sys.modules, {
            'noark5_workflow.reporting.report_job_discovery_a207': self.module,
        })
        self._module_patch.start()
        self.addCleanup(self._module_patch.stop)

    def run_dialog(self):
        self.job_window = self.JobWindow.__new__(self.JobWindow)
        FakeJobsWindow.__init__(self.job_window)
        self.job_window._recover_report_jobs()
        return self.ui.windows[0]

    def example_plan(self):
        jobs = (SimpleNamespace(job_id='JOB-001', name='1535_005 ephorte',
                                original_runs=1, manifest_verified=True),)
        missing = tuple(Path(f'1539_00{i}_other') for i in range(8))
        return SimpleNamespace(jobs=jobs,
            extraction_folders=tuple(Path(f'{n}_extraction') for n in range(9)),
            report_roots=(Path('G:/arkiv-noark5/1535/1535_005/repository_operations/dwm/b03'),),
            missing_report_extractions=missing,
            existing_job_lists=(Path('G:/arkiv-noark5/K18_v0.1.4-a8_a-nnn.n5jobs'),),
            archived_dwm_zips=(Path('G:/arkiv-noark5/1535_005_dwm.zip'),),
            warnings=())

    def test_prior_progress_must_not_appear_as_final_result(self):
        plan = self.example_plan()
        def discover(_path, *, cancelled, on_progress):
            on_progress('Ingen sikre jobb-lister kunne opprettes')
            on_progress('Ferdig: 9 uttrekksmapper, 1 DWM-arbeidsområde')
            return plan
        self.module.discover_available_report_jobs=discover
        window=self.run_dialog()
        status=self.ui.select('label', text=f'Søker i {Path("G:/arkiv-noark5")}')
        self.assertIn('Søker', status.options['text'])
        self.assertEqual(self.prompt_count['question'],0)
        self.assertEqual(self.ui.select('button',text='Lagre ny jobbliste ...').options['state'],'disabled')
        window.pump()
        self.assertIn('Ferdig: 9 uttrekksmapper, 1 rapportjobb', status.options['text'])
        self.assertIn('JOB-001',self.ui.select('textbox').text)
        self.assertIn('Eksisterende jobblister',self.ui.select('textbox').text)
        self.assertIn('8 uttrekksmapper uten lagret',self.ui.select('textbox').text)
        self.assertEqual(self.prompt_count['question'],0)
        self.assertEqual(self.messages,[])
        self.assertEqual(self.ui.select('button',text='Lagre ny jobbliste ...').options['state'],'normal')
        self.assertFalse(window.after_callbacks)

    def test_windows_drive_path_normalization_is_supported(self):
        """Reproduce Windows Path string rendering on non-Windows test runners."""
        self.scope['Path'] = PureWindowsPath
        self.module.discover_available_report_jobs = lambda *_a, **_k: self.example_plan()
        window = self.run_dialog()
        status = self.ui.select('label', text=f'Søker i {PureWindowsPath("G:/arkiv-noark5")}')
        self.assertEqual(status.options['text'], 'Søker i G:\\arkiv-noark5')
        window.pump()
        self.assertIn('Ferdig: 9 uttrekksmapper', status.options['text'])
        self.assertEqual(self.ui.select('button', text='Lagre ny jobbliste ...').options['state'], 'normal')

    def test_save_only_on_click_and_open_only_on_click(self):
        self.module.discover_available_report_jobs=lambda *_a,**_k:self.example_plan()
        window=self.run_dialog()
        window.pump()
        self.assertEqual(self.saved,[])
        self.ui.select('button',text='Lagre ny jobbliste ...').click()
        self.assertEqual(len(self.saved),1)
        self.assertEqual(self.saved[0][1],self.save_target)
        self.assertEqual(self.ui.select('button',text='Åpne lagret jobbliste').options['state'],'normal')
        self.assertEqual(self.prompt_count['question'],0)
        self.ui.select('button',text='Åpne lagret jobbliste').click()
        self.assertEqual(self.prompt_count['question'],1)
        self.assertEqual(self.job_window.refresh_count,1)
        self.assertFalse(window.winfo_exists())

    def test_failed_scan_shows_error_without_early_confirmation(self):
        def discover(*_a,**_k):
            raise OSError('USB-disk frakoblet')
        self.module.discover_available_report_jobs=discover
        window=self.run_dialog()
        status=self.ui.select('label', text=f'Søker i {Path("G:/arkiv-noark5")}')
        window.pump()
        self.assertIn('Søket kunne ikke fullføres', status.options['text'])
        self.assertIn('USB-disk frakoblet',self.ui.select('textbox').text)
        self.assertEqual(self.ui.select('button',text='Lagre ny jobbliste ...').options['state'],'disabled')
        self.assertEqual(self.prompt_count['question'],0)
        self.assertEqual(self.messages,[])

    def test_only_one_recovery_dialog_can_be_active(self):
        self.module.discover_available_report_jobs=lambda *_a,**_k:self.example_plan()
        first=self.run_dialog()
        self.job_window._recover_report_jobs()
        self.assertEqual(self.prompt_count['directory'],1)
        self.assertEqual(len(self.ui.windows),1)
        self.assertTrue(first.options['focused'])

    def test_closed_dialog_does_not_process_late_result(self):
        self.module.discover_available_report_jobs=lambda *_a,**_k:self.example_plan()
        window=self.run_dialog()
        window.on_close()
        self.assertFalse(window.winfo_exists())
        self.assertIsNone(self.job_window._dwm_recovery_window)
        window.pump()
        self.assertEqual(self.ui.select('button',text='Lagre ny jobbliste ...').options['state'],'disabled')


if __name__ == '__main__':
    unittest.main()
