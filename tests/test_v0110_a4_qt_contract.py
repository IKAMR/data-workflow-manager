"""A4 compatibility checks continued into a5 without locking old CSV internals.

Static contract tests are runnable without Qt; real Qt UI requires Windows QA.
"""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResultCenterA4Contract(unittest.TestCase):
    def test_main_window_uses_a4_result_center(self):
        code = (ROOT / 'gui_qt/main_window.py').read_text(encoding='utf-8')
        self.assertIn('from .result_center_v0110_a4 import ResultCenterWindow as EvidenceResultCenter', code)

    def test_existing_evidence_functions_unchanged_by_delta(self):
        # Keep existing source importers and action contracts intact.
        code = (ROOT / 'gui_qt/result_center_v0110_a4.py').read_text(encoding='utf-8')
        self.assertIn('from .result_center_v019_a1 import ResultCenterWindow', code)
        self.assertIn("'Periodevurdering': ('Vurder periode…',)", code)
        self.assertIn("'Depotrapporter': ('Åpne kildefil', 'Lag rapport / samlerapport…')", code)
        self.assertIn("'KDRS Query': ('Åpne kildefil', 'Velg KDRS-evidens…')", code)
        self.assertIn('self.tabs.currentChanged.connect(self._a4_apply_context_actions)', code)
        self.assertIn('FORMAT_PROFILE_DIR', code)
        # a5 adds import/snapshot dates to the export without losing the a4 fields.
        self.assertIn('export_comparison_csv', code)
        self.assertIn('read_pronom_import_context', code)
        self.assertNotIn('shutil.copy', code)
        self.assertNotIn('.mkdir(', code)
        self.assertNotIn('manuell_konvertering', code)


if __name__ == '__main__':
    unittest.main()
