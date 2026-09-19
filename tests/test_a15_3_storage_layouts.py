from __future__ import annotations

from pathlib import Path
import unittest

from app.storage_layouts import (
    infer_package_root,
    materialize_storage_roles,
    storage_layout_by_id,
    suggested_job_name,
)


class A153StorageLayoutTests(unittest.TestCase):
    def test_ikamr_standard_materializes_roles(self):
        extraction = Path(
            r"G:\arkiv-noark5\1525\1525_004_E-1525-2025-0001\content\sip\content"
        )
        roles = materialize_storage_roles(
            extraction, layout_id="ikamr_standard"
        )
        root = Path(r"G:\arkiv-noark5\1525\1525_004_E-1525-2025-0001")
        self.assertEqual(roles["source_root"], root)
        self.assertEqual(roles["source_extraction"], extraction)
        self.assertEqual(roles["work_root"], root)
        self.assertEqual(roles["work_content"], root / "content")
        self.assertEqual(
            roles["work_operations"], root / "repository_operations"
        )
        self.assertEqual(roles["archive_root"], root / "aip")

    def test_extra_content_level_still_finds_package_root(self):
        extraction = Path(
            r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5"
            r"\content\sip\content\content"
        )
        layout = storage_layout_by_id("ikamr_standard")
        root = infer_package_root(extraction, layout)
        self.assertEqual(
            root,
            Path(r"G:\arkiv-noark5\1543\1543_012_E-Docu-2025-0001_AIC-5"),
        )
        self.assertEqual(
            suggested_job_name(extraction, layout_id="ikamr_standard"),
            "1543_012_E-Docu-2025-0001_AIC-5",
        )

    def test_none_only_sets_source_extraction(self):
        extraction = Path(r"G:\x\content\sip\content")
        self.assertEqual(
            materialize_storage_roles(extraction, layout_id="none"),
            {"source_extraction": extraction},
        )

    def test_unknown_structure_does_not_invent_package_root(self):
        extraction = Path(r"G:\odd\somewhere\extract")
        self.assertEqual(
            materialize_storage_roles(
                extraction, layout_id="ikamr_standard"
            ),
            {"source_extraction": extraction},
        )


if __name__ == "__main__":
    unittest.main()
