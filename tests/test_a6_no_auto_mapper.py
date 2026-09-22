from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6NoAutoMapperTests(unittest.TestCase):
    def test_new_job_does_not_open_mapper_automatically(self):
        text = (
            ROOT / "gui" / "persistent_app_a38.py"
        ).read_text(encoding="utf-8")

        method = text.split(
            "def _create_job", 1
        )[1].split(
            "def _restore_default_workflow_if_empty", 1
        )[0]

        self.assertIn("self.jobs.new_job(None)", method)
        self.assertNotIn("_show_storage_roles", method)
        self.assertNotIn("_edit_storage_roles", method)
        self.assertNotIn("self.after(", method)

    def test_mapper_remains_explicit_action_in_inherited_ui(self):
        text = (
            ROOT / "gui" / "persistent_app_a13.py"
        ).read_text(encoding="utf-8")
        self.assertIn('text="Mapper"', text)
        self.assertIn("command=self._edit_storage_roles", text)


if __name__ == "__main__":
    unittest.main()
