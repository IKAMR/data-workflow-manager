import tempfile
import unittest
from pathlib import Path

from app.workspace import ensure_workspace, job_list_dir, run_log_dir, setup_dir

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceDefaultsA2151Tests(unittest.TestCase):
    def test_workspace_is_created_from_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "n5wfman"
            settings = {"temp_dir": str(root), "run_log_dir": "", "setup_dir": "", "job_list_dir": ""}
            ensure_workspace(settings)
            self.assertTrue((root / "logs" / "runs").is_dir())
            self.assertTrue((root / "setup").is_dir())
            self.assertTrue((root / "joblists").is_dir())
            self.assertTrue((root / "work").is_dir())
            self.assertTrue((root / "cache").is_dir())

    def test_empty_custom_value_means_default(self):
        settings = {"temp_dir": "C:/uttrekk-n5wfman", "run_log_dir": "", "setup_dir": "", "job_list_dir": ""}
        self.assertEqual(run_log_dir(settings), Path("C:/uttrekk-n5wfman") / "logs" / "runs")
        self.assertEqual(setup_dir(settings), Path("C:/uttrekk-n5wfman") / "setup")
        self.assertEqual(job_list_dir(settings), Path("C:/uttrekk-n5wfman") / "joblists")

    def test_settings_dialog_has_browse_and_default_buttons(self):
        text = (ROOT / "gui" / "settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn('text="Velg…"', text)
        self.assertIn('text="Bruk standard"', text)
        self.assertIn("def _browse_standard_dir", text)
        self.assertIn("def _use_default_dir", text)

    def test_latest_runtime_uses_joblist_workspace_fallback(self):
        latest = (ROOT / "gui" / "persistent_app_a2155.py").read_text(encoding="utf-8")
        parent = (ROOT / "gui" / "persistent_app_a2151.py").read_text(encoding="utf-8")
        self.assertIn("A2154WorkflowApp", latest)
        self.assertIn("job_list_dir(self.settings)", parent)
        self.assertIn("ensure_workspace(self.settings)", parent)

    def test_current_runtime_preserves_workspace_chain(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        a21 = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")
        a20 = (ROOT / "gui" / "persistent_app_a20.py").read_text(encoding="utf-8")
        a19 = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        a18 = (ROOT / "gui" / "persistent_app_a18.py").read_text(encoding="utf-8")
        a17 = (ROOT / "gui" / "persistent_app_a17.py").read_text(encoding="utf-8")
        a13 = (ROOT / "gui" / "persistent_app_a13.py").read_text(encoding="utf-8")
        a6 = (ROOT / "gui" / "persistent_app_a6.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a21", main)
        self.assertIn("A20WorkflowApp", a21)
        self.assertIn("A19WorkflowApp", a20)
        self.assertIn("A18WorkflowApp", a19)
        self.assertIn("A17WorkflowApp", a18)
        self.assertIn("A13WorkflowApp", a17)
        self.assertIn("persistent_app_a6", a13)
        self.assertIn("A5WorkflowApp", a6)


if __name__ == "__main__":
    unittest.main()
