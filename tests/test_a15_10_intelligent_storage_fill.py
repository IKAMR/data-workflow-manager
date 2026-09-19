from __future__ import annotations

from pathlib import Path
import unittest

from app.storage_layouts import (
    materialize_storage_roles_from_root,
    suggest_storage_roles,
)


class A1510IntelligentStorageFillTests(unittest.TestCase):
    def test_root_can_materialize_standard_roles(self):
        root = Path(r"G:\arkiv-noark5\1525\1525_006_E-1525-2025-0001")
        roles = materialize_storage_roles_from_root(
            root,
            layout_id="ikamr_standard",
        )
        self.assertEqual(roles["source_root"], root)
        self.assertEqual(
            roles["source_extraction"],
            root / "content" / "sip" / "content",
        )
        self.assertEqual(roles["work_root"], root)
        self.assertEqual(roles["work_content"], root / "content")
        self.assertEqual(
            roles["work_operations"],
            root / "repository_operations",
        )
        self.assertEqual(roles["archive_root"], root / "aip")

    def test_known_extraction_has_priority_over_root_guess(self):
        root = Path(r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5")
        extraction = root / "content" / "sip" / "content" / "content"
        roles = suggest_storage_roles(
            source_root=root,
            extraction_root=extraction,
            layout_id="ikamr_standard",
        )
        self.assertEqual(roles["source_root"], root)
        self.assertEqual(roles["source_extraction"], extraction)

    def test_none_profile_does_not_invent_other_roles(self):
        root = Path(r"G:\x\package")
        roles = materialize_storage_roles_from_root(
            root,
            layout_id="none",
        )
        self.assertEqual(roles, {"source_root": root})

    def test_mapper_dialog_has_explicit_fill_action(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "storage_roles_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn('text="Fyll ut forslag"', text)
        self.assertIn("def _fill_suggestions", text)
        self.assertIn("suggest_storage_roles(", text)

    def test_existing_conflicts_are_not_silently_overwritten(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "gui"
            / "storage_roles_dialog.py"
        ).read_text(encoding="utf-8")
        self.assertIn("messagebox.askyesno(", text)
        self.assertIn(
            "Nei = fyll bare tomme felt og behold eksisterende verdier.",
            text,
        )


if __name__ == "__main__":
    unittest.main()
