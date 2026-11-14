from pathlib import Path
import re
import unittest
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


class A183VisibleReviewTests(unittest.TestCase):
    def test_review_controls_are_integrated_in_existing_period_panel(self):
        source = (ROOT / "gui/depot_result_center_a18_3.py").read_text(encoding="utf-8")
        self.assertIn('_a1616_period_panel', source)
        self.assertIn('legacy_panel.grid_remove()', source)
        self.assertIn('text="Periodevurdering:"', source)
        self.assertIn('text="+"', source)
        self.assertIn('text="−"', source)
        self.assertIn('text="?"', source)
        self.assertIn('text="Kommentar…"', source)

    def test_runtime_and_version_wiring(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")

        # a18.3 remains part of the runtime chain. The consolidated a18 milestone
        # and all later alpha milestones are valid successors.
        chain = (ROOT / "gui" / "persistent_app_a18_4.py").read_text(encoding="utf-8")
        self.assertIn("from .persistent_app_a18_3 import WorkflowApp as A18_3WorkflowApp", chain)

        assert_v016_at_least(self, version, 18, 0)


if __name__ == "__main__":
    unittest.main()
