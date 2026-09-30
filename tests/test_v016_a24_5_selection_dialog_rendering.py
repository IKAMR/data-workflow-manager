from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class A245SelectionDialogRenderingTests(unittest.TestCase):
    def test_checklist_uses_explicit_rows_and_separate_visible_labels(self):
        source = (ROOT / "gui" / "extraction_candidate_selection_dialog.py").read_text(encoding="utf-8")
        self.assertIn("row = ctk.CTkFrame(listing", source)
        self.assertIn('text=""', source)
        self.assertIn("label = ctk.CTkLabel(", source)
        self.assertIn("text_color=theme.TEXT", source)
        self.assertIn('wraplength=830', source)
        self.assertIn('f"{index}. {name}\\n{path}"', source)

    def test_selection_actions_and_count_are_kept_above_scrollable_list(self):
        source = (ROOT / "gui" / "extraction_candidate_selection_dialog.py").read_text(encoding="utf-8")
        toolbar = source.index('toolbar = ctk.CTkFrame')
        confirm = source.index('text="Legg til valgte"')
        listing = source.index('listing = ctk.CTkScrollableFrame')
        self.assertLess(toolbar, listing)
        self.assertLess(confirm, listing)
        self.assertIn('text=f"Valgt: {selected} av {len(self._candidates)}"', source)

    def test_all_selected_default_and_select_clear_controls_are_preserved(self):
        source = (ROOT / "gui" / "extraction_candidate_selection_dialog.py").read_text(encoding="utf-8")
        self.assertIn("ctk.BooleanVar(value=True)", source)
        self.assertIn('text="Velg alle"', source)
        self.assertIn('text="Tøm"', source)
        self.assertIn("def _toggle", source)

    def test_version_is_a245(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        locked = re.search(r'VERSION\s*=\s*"0\.1\.6-a24"', version)
        match = re.search(r'VERSION\s*=\s*"0\.1\.6-a24\.(\d+)"', version)
        self.assertTrue(locked is not None or (match is not None and int(match.group(1)) >= 5))


if __name__ == "__main__":
    unittest.main()
