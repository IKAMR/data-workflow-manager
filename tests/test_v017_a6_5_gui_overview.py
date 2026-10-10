from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT/'gui'/'noark5_multi_overview_a65.py').read_text(encoding='utf-8')
BRIDGE = (ROOT/'gui'/'depot_result_center_v017_a1.py').read_text(encoding='utf-8')
SCRIPT = (ROOT/'tools'/'noark5_batch_overview_a6.py').read_text(encoding='utf-8')

class TestA65(unittest.TestCase):
    def test_python_parses(self):
        for text in (GUI, BRIDGE, SCRIPT): ast.parse(text)

    def test_button_in_existing_result_center(self):
        self.assertIn('Samlet uttrekksoversikt', BRIDGE)
        self.assertIn('command=self._open_a65_multi_overview', BRIDGE)
        self.assertIn('report_path=self.report_path', BRIDGE)

    def test_safe_job_group_root(self):
        # module import can run on Windows with customtkinter; test AST instead
        self.assertIn("parent.name.lower() == 'repository_operations'", GUI)
        self.assertIn('return parent.parent.parent', GUI)
        self.assertIn('raise ValueError', GUI)

    def test_explicit_user_start(self):
        self.assertIn('command=self._start', GUI)
        self.assertIn("'--source', str(source), '--output', str(target)", GUI)
        self.assertIn("'--select'", GUI)

    def test_report_progress_and_no_gui_blocking(self):
        self.assertIn('threading.Thread', GUI)
        self.assertIn('subprocess.Popen', GUI)
        self.assertIn('self._events.put', GUI)
        self.assertIn('self.after(120, self._poll)', GUI)
        self.assertIn('if self._running:', GUI)

    def test_generator_unchanged_safe_discovery(self):
        self.assertIn("'content', 'sip', 'aip', 'dokument'", SCRIPT)
        self.assertNotIn("source.rglob", SCRIPT)
        self.assertIn('choose_latest_per_job', SCRIPT)
        self.assertIn('depot-effective-evidence.json', SCRIPT)

    def test_no_automatic_approval(self):
        self.assertIn('Ingen automatisk depotgodkjenning', GUI)
        self.assertIn('DELSUM', SCRIPT)

if __name__ == '__main__': unittest.main()
