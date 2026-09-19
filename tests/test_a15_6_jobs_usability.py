from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A156JobsUsabilityTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "gui" / "jobs_window_a17.py").read_text(encoding="utf-8")

    def test_jobs_refresh_has_in_place_fast_path(self):
        self.assertIn("job_ids == self._rendered_job_ids", self.text)
        self.assertIn("self._update_row_view(", self.text)
        # Structural rebuild is still allowed, but progress updates must have a
        # path that does not destroy every row.
        fast_path = self.text.split("def refresh(self) -> None:", 1)[1].split(
            "def _update_summary", 1
        )[0]
        self.assertIn("super().refresh()", fast_path)
        self.assertIn("return", fast_path)

    def test_job_rows_expose_mapper_and_standard_setup(self):
        self.assertIn('text="Mapper"', self.text)
        self.assertIn('text="Standard"', self.text)
        self.assertIn("self._edit_job_mappers(j)", self.text)
        self.assertIn("self._apply_standard_setup(j)", self.text)

    def test_mapper_from_job_list_uses_existing_storage_dialog(self):
        self.assertIn('getattr(self.master, "_show_storage_roles", None)', self.text)
        self.assertIn("callback(job)", self.text)

    def test_standard_setup_uses_configured_layout_and_workflow(self):
        self.assertIn('settings.get("storage_layout_profile", "ikamr_standard")', self.text)
        self.assertIn('settings.get("noark5_discovery_workflow", "noark5_standard")', self.text)
        self.assertIn("materialize_storage_roles(", self.text)
        self.assertIn("workflow_sequence_by_id(", self.text)
        self.assertIn('job.profile_id = "noark5"', self.text)

    def test_standard_setup_requires_confirmation_before_overwrite(self):
        method = self.text.split("def _apply_standard_setup(self, job: Job) -> None:", 1)[1]
        method = method.split("# ------------------------------------------------------------------\n    # Discovery", 1)[0]
        self.assertIn("messagebox.askyesno(", method)
        self.assertIn("Eksisterende verdier som avviker", method)


if __name__ == "__main__":
    unittest.main()
