from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]

class V016A9MissingDataExplanationTests(unittest.TestCase):
    def test_version_is_a9_or_newer_v016(self):
        text=(ROOT/'version.py').read_text(encoding='utf-8')
        match=re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.\d+)*"',text)
        self.assertIsNotNone(match); self.assertGreaterEqual(int(match.group(1)),9)
    def test_a9_builds_on_a8_queue(self):
        source=(ROOT/'gui'/'depot_result_views_a29.py').read_text(encoding='utf-8')
        self.assertIn('DepotResultViewsDialogA28',source); self.assertIn('super().__init__(master, **kwargs)',source)
    def test_zero_is_not_treated_as_missing(self):
        source=(ROOT/'gui'/'depot_result_views_a29.py').read_text(encoding='utf-8')
        block=source.split('def _missing_archive_fields',1)[1].split('class DepotResultViewsDialogA29',1)[0]
        self.assertIn('row.get(field_id) is None',block); self.assertNotIn('if not row.get(field_id)',block)
    def test_left_cards_list_missing_field_names(self):
        source=(ROOT/'gui'/'depot_result_views_a29.py').read_text(encoding='utf-8')
        self.assertIn('missing_text = f"Mangler: {names}"',source); self.assertIn('Alle nøkkelfelt tilgjengelig',source)
    def test_right_side_has_explicit_missing_data_block(self):
        source=(ROOT/'gui'/'depot_result_views_a29.py').read_text(encoding='utf-8')
        self.assertIn('text="Manglende datagrunnlag"',source); self.assertIn('ikke i seg selv en testfeil',source)
    def test_missing_fields_show_source_when_available(self):
        source=(ROOT/'gui'/'depot_result_views_a29.py').read_text(encoding='utf-8')
        self.assertIn('source = sources.get(field_id) or {}',source); self.assertIn('source.get("test_id")',source); self.assertIn('source.get("path")',source)
    def test_complete_vocabulary_is_not_faglig_acceptance(self):
        source=(ROOT/'gui'/'depot_result_views_a29.py').read_text(encoding='utf-8')
        self.assertIn('FILTER_COMPLETE = "Alle nøkkelfelt"',source); self.assertNotIn('godkjent',source.casefold()); self.assertNotIn('avvist',source.casefold())
    def test_runtime_activates_a69(self):
        main=(ROOT/'main.py').read_text(encoding='utf-8'); self.assertIn('from gui.persistent_app_a69 import run_gui',main)

if __name__ == '__main__': unittest.main()
