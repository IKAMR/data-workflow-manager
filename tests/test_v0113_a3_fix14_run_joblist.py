"""Contract checks for optional job list controls in the Basic run step."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'gui_qt' / 'basic_main_v0113_a2.py'

class RunJoblistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        cls.window = next(n for n in cls.tree.body if isinstance(n, ast.ClassDef)
                          and n.name == 'DwmMainWindow')

    def method(self, name):
        return next(n for n in self.window.body if isinstance(n, ast.FunctionDef)
                    and n.name == name)

    def test_run_controls_exist_on_shared_run_group(self):
        code = ast.get_source_segment(self.source, self.method('_a3_install_run_joblist'))
        self.assertIn("self._a2_step_groups['run']", code)
        self.assertIn("'Jobbliste (valgfritt):'", code)
        self.assertIn('layout.insertLayout(0, row)', code)

    def test_buttons_use_existing_methods(self):
        code = ast.get_source_segment(self.source, self.method('_a3_install_run_joblist'))
        self.assertIn('clicked.connect(self._a2_choose_joblist)', code)
        self.assertIn('clicked.connect(self._a2_save_joblist_as)', code)
        self.assertNotIn('new_job_list(', code)

    def test_live_refresh_and_optional_value(self):
        code = ast.get_source_segment(self.source, self.method('_a2_refresh_overview'))
        self.assertIn("joblist or 'Ikke lagret'", code)
        self.assertIn('self._a3_run_joblist_path.setText(display)', code)
        self.assertIn('self._a3_run_open_joblist.setEnabled(idle)', code)
        self.assertIn('self._a3_run_save_joblist.setEnabled(idle)', code)

    def test_setup_initializes_run_selection(self):
        code = ast.get_source_segment(self.source, self.method('__init__'))
        self.assertIn('self._a3_install_run_joblist()', code)

if __name__ == '__main__':
    unittest.main()
