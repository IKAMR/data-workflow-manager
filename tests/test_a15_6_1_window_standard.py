from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A1561Tests(unittest.TestCase):
    def setUp(self):
        self.runtime = (
            ROOT / "gui" / "persistent_app_a24.py"
        ).read_text(encoding="utf-8")
        self.settings = (
            ROOT / "settings.py"
        ).read_text(encoding="utf-8")
        self.main = (
            ROOT / "main.py"
        ).read_text(encoding="utf-8")

    def test_runtime_is_preserved_in_current_chain(self):
        self.assertIn(
            "from gui.persistent_app_a24 import WorkflowApp as _A24WorkflowApp",
            self.main,
        )
        self.assertIn(
            "from gui.persistent_app_a27 import run_gui",
            self.main,
        )

    def test_maximized_state_is_saved(self):
        self.assertIn('self.state()).lower() == "zoomed"', self.runtime)
        self.assertIn(
            'save_config({"main_window_maximized": maximized})',
            self.runtime,
        )

    def test_maximized_state_is_restored(self):
        self.assertIn('self.state("zoomed")', self.runtime)
        self.assertIn(
            "self.after_idle(self._restore_maximized_state)",
            self.runtime,
        )
        self.assertIn(
            "self.after(150, self._restore_maximized_state)",
            self.runtime,
        )

    def test_settings_defaults_exist(self):
        self.assertIn(
            '"restore_main_window_maximized": True',
            self.settings,
        )
        self.assertIn(
            '"main_window_maximized": False',
            self.settings,
        )

    def test_active_standard_button_exists(self):
        self.assertIn('text="Standard"', self.runtime)
        self.assertIn(
            "command=self._apply_standard_to_current_job",
            self.runtime,
        )

    def test_active_standard_uses_configured_policies(self):
        self.assertIn(
            'storage_layout_profile", "ikamr_standard"',
            self.runtime,
        )
        self.assertIn(
            '"noark5_discovery_workflow", "noark5_standard"',
            self.runtime,
        )
        self.assertIn("materialize_storage_roles(", self.runtime)
        self.assertIn("workflow_sequence_by_id(", self.runtime)


if __name__ == "__main__":
    unittest.main()
