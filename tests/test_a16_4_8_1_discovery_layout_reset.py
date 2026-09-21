from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A16481DiscoveryLayoutResetTests(unittest.TestCase):
    def test_job_list_remains_in_original_expanding_row(self):
        source = (ROOT / "gui" / "jobs_window_a20.py").read_text(encoding="utf-8")
        self.assertIn("self.list_frame.grid(row=3", source)
        self.assertIn("self.grid_rowconfigure(3, weight=1)", source)
        self.assertIn("frame.grid(row=4", source)
        self.assertNotIn("self.list_frame.grid_configure(row=4)", source)

    def test_result_inventory_stays_visible_on_job_row(self):
        source = (ROOT / "gui" / "jobs_window_a20.py").read_text(encoding="utf-8")
        self.assertIn('job._result_inventory_summary', source)
        self.assertIn('parts.append(f"Eksisterende: {inventory}")', source)

    def test_reset_requires_explicit_confirmation(self):
        source = (
            ROOT / "gui" / "discovered_sources_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("messagebox.askyesno(", source)
        self.assertIn("Nullstille kjørestatus/cursor for valgte jobber?", source)
        self.assertIn("Eksisterende resultatfiler og logger på disk slettes ikke", source)

    def test_result_control_is_read_only_without_reset_choice(self):
        source = (
            ROOT / "gui" / "discovered_sources_dialog.py"
        ).read_text(encoding="utf-8")
        accept = source.split("def _accept(self) -> None:", 1)[1]
        self.assertIn("wants_reset = bool(", accept)
        self.assertIn("self.reset_execution_state = wants_reset", accept)


if __name__ == "__main__":
    unittest.main()
