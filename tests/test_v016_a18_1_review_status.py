from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from noark5_workflow.analysis.depot_review_status import (
    get_area_status,
    load_review_status,
    set_area_status,
)
from version_assertions import assert_v016_at_least

ROOT = Path(__file__).resolve().parents[1]


class A181ReviewStatusTests(unittest.TestCase):
    def test_status_roundtrip_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "depot_report.json"
            report.write_text('{"ok": true}\n', encoding="utf-8")
            set_area_status(
                report,
                scope_id="A1",
                scope_label="Arkivdel 1",
                area="period",
                status="approved",
                comment="Kontrollert",
                user={"username": "tester"},
            )
            current = get_area_status(report, scope_id="A1", area="period")
            self.assertEqual(current["status"], "approved")
            self.assertEqual(current["comment"], "Kontrollert")
            self.assertEqual(len(load_review_status(report)["history"]), 1)

    def test_minus_requires_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "depot_report.json"
            report.write_text('{"ok": true}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                set_area_status(
                    report,
                    scope_id="A1",
                    scope_label="Arkivdel 1",
                    area="period",
                    status="rejected",
                    comment="",
                )

    def test_runtime_and_version_wiring(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        chain = (ROOT / "gui" / "persistent_app_a18_2.py").read_text(encoding="utf-8")
        self.assertIn("from .persistent_app_a18_1 import WorkflowApp as A18_1WorkflowApp", chain)
        assert_v016_at_least(self, version, 18, 0)

    def test_gui_exposes_period_review(self):
        source = (ROOT / "gui" / "depot_result_center_a18_1.py").read_text(encoding="utf-8")
        self.assertIn("Vurder / kommenter", source)
        self.assertIn("Virtuelt utvalg kan ikke vurderes", source)
        self.assertIn('area="period"', source)


if __name__ == "__main__":
    unittest.main()
