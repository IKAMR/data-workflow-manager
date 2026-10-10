"""Source regression: report reconciliation is explicitly non-destructive and reachable."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class EvidenceCompanionGuiTests(unittest.TestCase):
    def test_result_center_has_refresh_action(self):
        source = (ROOT/'gui/depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        self.assertIn('command=self._refresh_a5_evidence', source)
        self.assertIn('self.after_idle(self._refresh_a5_evidence)', source)
        self.assertIn('write_depot_evidence_companion(report_path, work)', source)
    def test_companion_is_separate_from_native_report(self):
        source = (ROOT/'noark5_workflow/external_evidence/evidence_report_bridge_a5.py').read_text(encoding='utf-8')
        self.assertIn("rp.with_name('depot-external-evidence.json')", source)
        self.assertNotIn('rp.write_text(', source)

if __name__ == '__main__': unittest.main()
