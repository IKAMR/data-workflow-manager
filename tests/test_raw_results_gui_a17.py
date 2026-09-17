from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RawResultsGuiA17Tests(unittest.TestCase):
    def test_current_runtime_preserves_a17_runtime(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        a19 = (ROOT / "gui" / "persistent_app_a19.py").read_text(encoding="utf-8")
        a18 = (ROOT / "gui" / "persistent_app_a18.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a19", main)
        self.assertIn("A18WorkflowApp", a19)
        self.assertIn("A17WorkflowApp", a18)

    def test_path_is_job_work_operations_wf_results(self):
        text = (ROOT / "gui" / "result_history_dialog.py").read_text(encoding="utf-8")
        self.assertIn("work_operations", text)
        self.assertIn('"wf"', text)
        self.assertIn('"results"', text)

    def test_results_are_filtered_by_job_id(self):
        text = (ROOT / "gui" / "result_history_dialog.py").read_text(encoding="utf-8")
        self.assertIn("job_id", text)

    def test_legacy_blank_job_id_requires_source_match(self):
        text = (ROOT / "gui" / "result_history_dialog.py").read_text(encoding="utf-8")
        self.assertIn("source", text)

    def test_no_source_fallback_without_work_operations(self):
        text = (ROOT / "gui" / "result_history_dialog.py").read_text(encoding="utf-8")
        self.assertIn("work_operations", text)

    def test_runtime_exposes_results_button_without_replacing_a13(self):
        from gui.ui_contract_a17 import HEADER_ACTIONS, RESULTS_ACTION_LOCATION
        text = (ROOT / "gui" / "persistent_app_a17.py").read_text(encoding="utf-8")
        self.assertIn("class WorkflowApp(A13WorkflowApp)", text)
        self.assertNotIn("def _build_header", text)
        self.assertIn('self.log_panel.set_aux_action("Resultater"', text)
        self.assertEqual(HEADER_ACTIONS, ("Mapper", "Jobber", "Setup", "A-", "A+", "?"))
        self.assertEqual(RESULTS_ACTION_LOCATION, "run-log")
        self.assertIn("HEADER_ACTIONS", text)
        self.assertIn("self._a17_header_actions = actions", text)


if __name__ == "__main__":
    unittest.main()
