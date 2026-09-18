from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from noark5_workflow.plugins.noark5.discovery import (
    discover_from_robocopy_log,
    discover_from_robocopy_text,
)


class A151Noark5JobDiscoveryTests(unittest.TestCase):
    def test_multi_extraction_sip_finds_each_avleveringspakke(self):
        text = r"""
 New Dir          2 G:\arkiv-noark5\1502_003_AIC-1\content\sip\content\mei-2023\avleveringspakke\
   New File        123 arkivstruktur.xml
   New File        123 arkivuttrekk.xml
 New Dir          2 G:\arkiv-noark5\1502_003_AIC-1\content\sip\content\mk_2TB_2023\avleveringspakke\
   New File        456 arkivstruktur.xml
   New File        123 arkivuttrekk.xml
"""
        found = discover_from_robocopy_text(text)
        self.assertEqual(len(found), 2)
        self.assertEqual([x.suggested_name for x in found], ["mei-2023", "mk_2TB_2023"])
        self.assertTrue(all(x.confidence == "Sikker" for x in found))

    def test_single_extraction_content_root_uses_aic_name(self):
        text = r"""
 New Dir          2 G:\arkiv-noark5\1525\1525_004_E-1525-2025-0001\content\sip\content\
   New File        123 arkivstruktur.xml
   New File        123 arkivuttrekk.xml
"""
        found = discover_from_robocopy_text(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].suggested_name, "1525_004_E-1525-2025-0001")

    def test_generated_and_reference_areas_are_excluded(self):
        text = r"""
 New Dir          2 G:\x\repository_operations\analyse2\copy\
   New File        123 arkivstruktur.xml
   New File        123 arkivuttrekk.xml
 New Dir          2 G:\x\content\_work\n5-u-dok\
   New File        123 arkivstruktur.xml
   New File        123 arkivuttrekk.xml
 New Dir          2 G:\x\content\sip\content\real\avleveringspakke\
   New File        123 arkivstruktur.xml
   New File        123 arkivuttrekk.xml
"""
        found = discover_from_robocopy_text(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].suggested_name, "real")

    def test_incomplete_candidate_is_visible_but_not_safe_default(self):
        text = r"""
 New Dir          1 G:\x\candidate\
   New File        123 arkivstruktur.xml
"""
        found = discover_from_robocopy_text(text)
        self.assertEqual(found[0].confidence, "Kontroller")
        self.assertFalse(found[0].safe_default)

    def test_log_file_decode_and_parse(self):
        text = (
            " New Dir          2 G:\\x\\part\\avleveringspakke\\\r\n"
            "   New File        123 arkivstruktur.xml\r\n"
            "   New File        123 arkivuttrekk.xml\r\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "robocopy.log"
            path.write_bytes(text.encode("cp1252"))
            found = discover_from_robocopy_log(path)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].suggested_name, "part")


if __name__ == "__main__":
    unittest.main()
