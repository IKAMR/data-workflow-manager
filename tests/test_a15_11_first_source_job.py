from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A1511FirstSourceJobTests(unittest.TestCase):
    def setUp(self):
        self.runtime = (
            ROOT / "gui" / "persistent_app_a27.py"
        ).read_text(encoding="utf-8")
        self.main = (ROOT / "main.py").read_text(encoding="utf-8")

    def test_current_runtime_is_a27(self):
        self.assertIn(
            "from gui.persistent_app_a27 import run_gui",
            self.main,
        )

    def test_only_empty_job_list_can_create_first_job_from_source(self):
        method = self.runtime.split(
            "def _ensure_job_for_current_source(self):", 1
        )[1].split("def run_gui", 1)[0]
        self.assertIn("if len(self.jobs) != 0:", method)
        self.assertIn("return None", method)
        self.assertIn("job = self.jobs.new_job(None)", method)

    def test_existing_active_job_is_reused(self):
        method = self.runtime.split(
            "def _ensure_job_for_current_source(self):", 1
        )[1].split("def run_gui", 1)[0]
        active_block = method.split(
            "# Normal case:", 1
        )[1].split(
            "# If there is no active job", 1
        )[0]
        self.assertIn("if self.current_job is not None:", active_block)
        self.assertIn(
            "self.current_job.source_extraction = path",
            active_block,
        )
        self.assertNotIn("new_job(", active_block)

    def test_existing_matching_job_is_reused_before_creation(self):
        method = self.runtime.split(
            "def _ensure_job_for_current_source(self):", 1
        )[1].split("def run_gui", 1)[0]
        self.assertLess(
            method.index("existing = next("),
            method.index("job = self.jobs.new_job(None)"),
        )
        self.assertIn(
            "if job.active_extraction_root == path",
            method,
        )

    def test_automatic_first_job_keeps_current_profile_and_owner(self):
        self.assertIn(
            "job.profile_id = self.active_profile_id",
            self.runtime,
        )
        self.assertIn(
            "set_owner(current_identity())",
            self.runtime,
        )

    def test_old_a13_contract_remains_untouched(self):
        # The old boundary still documents that established jobs are never
        # implicitly duplicated by Source changes. a15.11 adds its exception
        # only in a later runtime layer.
        old = (
            ROOT / "gui" / "persistent_app_a13.py"
        ).read_text(encoding="utf-8")
        start = old.index("def _ensure_job_for_current_source")
        end = old.index("def _open_job", start)
        self.assertNotIn("self.jobs.new_job(", old[start:end])


if __name__ == "__main__":
    unittest.main()
