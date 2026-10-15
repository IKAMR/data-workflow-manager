"""a18-fix2: open full annual evidence in an independent read-only Tk window.

A headless GUI wiring test: exercises the actual nested button callback using
small fake widgets, without requiring a Windows desktop or CustomTkinter.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / 'gui' / 'period_assessment_dialog_a16.py'


class Widget:
    def __init__(self, *args, **kwargs):
        self.settings = kwargs
        self.inserted = ''
        self.command = kwargs.get('command')
        self.configured = {}
        self.packed = []

    def pack(self, **kwargs):
        self.packed.append(kwargs)

    def insert(self, position, value):
        self.inserted += value

    def configure(self, **kwargs):
        self.configured.update(kwargs)


class FakeWindow(Widget):
    def __init__(self, owner, *, state_unsupported=False):
        super().__init__(owner)
        self.owner = owner
        self.exists = True
        self.title_value = ''
        self.maximized = False
        self.geometry_value = ''
        self.protocols = {}
        self.clipboard = ''
        self.state_unsupported = state_unsupported
        self.raise_count = 0

    def title(self, value):
        self.title_value = value

    def winfo_screenwidth(self):
        return 1600

    def winfo_screenheight(self):
        return 900

    def minsize(self, *args):
        pass

    def geometry(self, value):
        self.geometry_value = value

    def state(self, value):
        if self.state_unsupported:
            raise RuntimeError('unsupported zoom state')
        self.maximized = (value == 'zoomed')

    def winfo_exists(self):
        return self.exists

    def deiconify(self):
        pass

    def lift(self):
        self.raise_count += 1

    def focus_force(self):
        pass

    def protocol(self, name, callback):
        self.protocols[name] = callback

    def destroy(self):
        self.exists = False

    def clipboard_clear(self):
        self.clipboard = ''

    def clipboard_append(self, value):
        self.clipboard += value


class Fixture:
    def __init__(self, *, state_unsupported=False):
        self.source = 'KDRS standard / import-024 / Hele uttrekket'
        self.annual_text = '1899: 9\n2005: 16000\n2099: 139\nKilde: import-024'
        self.windows = []
        self.widgets = []
        self.views = {}
        self.state_unsupported = state_unsupported
        self.owner = object()
        self.source_scope = SimpleNamespace(get=lambda: self.source)
        self.volume = SimpleNamespace(get=lambda *a: self.annual_text)

        def create_window(owner):
            view = FakeWindow(owner, state_unsupported=self.state_unsupported)
            self.windows.append(view)
            return view

        def widget(*args, **kwargs):
            view = Widget(*args, **kwargs)
            self.widgets.append(view)
            return view

        self.tk_module = SimpleNamespace(TclError=RuntimeError)
        self.ctk = SimpleNamespace(CTkToplevel=create_window, CTkFrame=widget,
                                   CTkLabel=widget, CTkTextbox=widget,
                                   CTkButton=widget)

    def callback(self):
        tree = ast.parse(GUI.read_text(encoding='utf-8'))
        outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == 'open_period_assessment_dialog')
        handler = next(n for n in outer.body if isinstance(n, ast.FunctionDef)
                       and n.name == 'open_large_view')
        module = ast.fix_missing_locations(ast.Module(body=[handler], type_ignores=[]))
        namespace = dict(jobs=[SimpleNamespace(job_id='JOB-002')],
                         idx=SimpleNamespace(get=lambda: 0),
                         source_scope=self.source_scope, large_views=self.views,
                         volume=self.volume, ctk=self.ctk,
                         tk=self.tk_module, window=self.owner)
        exec(compile(module, str(GUI), 'exec'), namespace)
        return namespace['open_large_view']


class DetachedYearViewTests(TestCase):
    def test_button_callback_is_connected_to_large_window(self):
        content = GUI.read_text(encoding='utf-8')
        ast.parse(content)
        self.assertIn("text='Åpne i eget vindu'", content)
        self.assertIn('open_large_button.configure(command=open_large_view)', content)

    def test_full_text_is_preserved_and_display_is_read_only(self):
        f = Fixture()
        f.callback()()
        self.assertEqual(len(f.windows), 1)
        popup = f.windows[0]
        self.assertIn('JOB-002', popup.title_value)
        self.assertIn('KDRS standard', popup.title_value)
        self.assertTrue(popup.maximized)
        area = next(w for w in f.widgets if w.settings.get('wrap') == 'none')
        self.assertEqual(area.inserted, f.annual_text)
        self.assertEqual(area.configured['state'], 'disabled')
        self.assertTrue(any(p.get('expand') for p in area.packed))

    def test_sources_can_be_compared_in_separate_snapshots(self):
        f = Fixture()
        action = f.callback()
        action()
        old = f.windows[0]
        f.source = 'KDRS u01 / import-024 / Hele uttrekket'
        f.annual_text = '1899: 4\n2099: 50'
        action()
        self.assertEqual(len(f.windows), 2)
        self.assertIn('KDRS standard', old.title_value)
        self.assertIn('KDRS u01', f.windows[1].title_value)
        self.assertEqual(old.owner, f.owner)
        f.source = 'KDRS standard / import-024 / Hele uttrekket'
        action()
        self.assertEqual(len(f.windows), 2)  # existing view raised, not replaced
        self.assertEqual(f.windows[0].raise_count, 2)

    def test_copy_close_reopen_and_unsupported_maximize(self):
        f = Fixture(state_unsupported=True)
        action = f.callback()
        action()
        w = f.windows[0]
        self.assertFalse(w.maximized)
        self.assertIn('x', w.geometry_value)
        copy = next(b for b in f.widgets if b.settings.get('text') == 'Kopier all tekst')
        copy.command()
        self.assertEqual(w.clipboard, f.annual_text)
        w.protocols['WM_DELETE_WINDOW']()
        self.assertFalse(w.exists)
        self.assertEqual(f.views, {})
        action()
        self.assertEqual(len(f.windows), 2)


if __name__ == '__main__':
    import unittest
    unittest.main()
