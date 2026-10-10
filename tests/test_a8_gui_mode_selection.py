"""Regression rules: no automatic folder scan on mode switch."""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / 'gui' / 'noark5_multi_overview_a65.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
CLS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'MultiExtractionOverview')
FUNCS = {n.name: n for n in CLS.body if isinstance(n, ast.FunctionDef)}

class GuiModeRegression(unittest.TestCase):
    def test_source_hidden_for_joblist(self):
        self.assertIn('self._source_container.pack_forget()', ast.get_source_segment(SOURCE, FUNCS['_set_mode']))
    def test_folder_search_only_on_button(self):
        self.assertIn('command=self._search_folders', SOURCE)
        self.assertNotIn('self._refresh_jobs', SOURCE)
        mode_body = ast.get_source_segment(SOURCE, FUNCS['_set_mode'])
        self.assertNotIn('available_jobs(', mode_body)
        self.assertNotIn('locate_reports(', mode_body)
    def test_source_change_clears_previous_list(self):
        s=ast.get_source_segment(SOURCE, FUNCS['_source_changed'])
        self.assertIn('self._clear_jobs(', s)
        self.assertIn('self._source.trace_add', SOURCE)
    def test_joblist_load_does_not_search(self):
        s=ast.get_source_segment(SOURCE, FUNCS['_load_joblist'])
        self.assertNotIn('available_jobs(',s)
        self.assertNotIn('locate_reports(',s)
    def test_discovery_console_is_silent(self):
        s=ast.get_source_segment(SOURCE, next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='available_jobs'))
        self.assertIn('redirect_stdout',s)

if __name__=='__main__': unittest.main()
