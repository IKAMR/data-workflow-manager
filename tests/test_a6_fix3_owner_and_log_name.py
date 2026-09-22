from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6Fix3OwnerAndLogNameTests(unittest.TestCase):
    def test_discovery_fills_missing_owner_from_current_user(self):
        text = (
            ROOT / "gui" / "jobs_window_a23.py"
        ).read_text(encoding="utf-8")
        method = text.split(
            "def _discover_jobs", 1
        )[1].split("def _refresh_output_rule_preview", 1)[0]
        self.assertIn('getattr(self.master, "current_user_identity"', method)
        self.assertIn("job.set_owner_identity(identity)", method)
        self.assertIn("if job.owner_identity:", method)

    def test_overview_log_uses_current_application_name(self):
        text = (
            ROOT / "noark5_workflow" / "sinks" / "text_run_log.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from version import APP_NAME", text)
        self.assertIn('f"{APP_NAME} - overordnet kjørelogg"', text)
        self.assertNotIn(
            '"Noark 5 Workflow Manager - overordnet kjørelogg"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
