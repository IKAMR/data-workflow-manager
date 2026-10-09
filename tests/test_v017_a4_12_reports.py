import tempfile
import unittest
from pathlib import Path
from noark5_workflow.external_evidence.legacy_layout_a410 import write_legacy_audit
from noark5_workflow.external_evidence.kdrs_query_views import presentation_text
from noark5_workflow.external_evidence.number_format import format_result_text


class A412Tests(unittest.TestCase):
    def test_both_work_root_forms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repository_operations'
            (root / 'dwm').mkdir(parents=True)
            a = write_legacy_audit(root)
            b = write_legacy_audit(root / 'dwm')
            self.assertEqual(a, b)
            self.assertNotIn('dwm/dwm/', a.as_posix())

    def test_presentation_only(self):
        original = '1: Sak; Mappe=6848, Reg=41467, Doc=49926 @@\nElektr: 49926'
        shown = presentation_text(original)
        self.assertIn('Mappe=6 848', shown)
        self.assertIn('Reg=41 467', shown)
        self.assertNotIn('@@', shown)
        self.assertIn('49926', original)

    def test_no_untyped_numbers(self):
        self.assertEqual(format_result_text('ID: 1502; Dato: 2023-11-22; Fil: abc12345.xml'), 'ID: 1502; Dato: 2023-11-22; Fil: abc12345.xml')


if __name__ == '__main__':
    unittest.main()
