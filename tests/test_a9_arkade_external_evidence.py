from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.external_evidence.arkade5 import (
    Arkade5ImportError,
    build_arkade5_reconciliation,
    import_arkade5_report,
    list_arkade5_imports,
    load_arkade5_import,
    normalize_arkade5_report,
)


SAMPLE = {"Summary": {"Uuid": "u", "ArchiveType": "Noark5", "DateOfTesting": "2026-02-26T12:00:00", "NumberOfTestsRun": 3, "NumberOfErrors": 0, "NumberOfWarnings": 0}, "TestsResults": [{"TestId": "N5.04", "TestName": "N5.04 - Antall arkiv", "TestType": "ContentAnalysis", "TestDescription": None, "ResultSet": {"Name": None, "ResultSets": [], "Results": [{"ResultType": "Success", "Location": {"String": "", "FileName": None, "LineNumbers": None}, "Message": "Totalt: 1"}]}, "HasResults": True, "NumberOfErrors": "0"}, {"TestId": "N5.05", "TestName": "N5.05 - Antall arkivdeler", "TestType": "ContentAnalysis", "TestDescription": None, "ResultSet": {"Name": None, "ResultSets": [], "Results": [{"ResultType": "Success", "Location": {"String": "", "FileName": None, "LineNumbers": None}, "Message": "Totalt: 5"}]}, "HasResults": True, "NumberOfErrors": "0"}, {"TestId": "N5.15", "TestName": "N5.15 - statuser", "TestType": "ContentAnalysis", "TestDescription": None, "ResultSet": {"Name": None, "ResultSets": [{"Name": "Arkivdel A", "ResultSets": [], "Results": [{"ResultType": "Error", "Location": {"String": "arkivstruktur.xml", "FileName": None, "LineNumbers": [10]}, "Message": "Under behandling: 19"}]}], "Results": []}, "HasResults": True, "NumberOfErrors": "1"}]}


class A9ArkadeExternalEvidenceTests(unittest.TestCase):
    def test_normalization_preserves_test_identity_errors_and_nested_results(self):
        normalized = normalize_arkade5_report(SAMPLE, source_file="arkade.json", source_sha256="abc")
        self.assertEqual(normalized["source_system"], "Arkade 5")
        self.assertEqual(normalized["format_version"], 2)
        test = next(item for item in normalized["tests"] if item["test_id"] == "N5.15")
        self.assertEqual(test["number_of_errors"], 1)
        self.assertEqual(test["source_status"], "error")
        self.assertEqual(test["results"][0]["result_set_path"], ["Arkivdel A"])
        self.assertEqual(test["results"][0]["location"]["line_numbers"], [10])
        self.assertIn("source_raw", test)
        self.assertIn("result_set_tree", test)

    def test_reconciliation_is_empty_until_scalar_equivalence_is_explicitly_verified(self):
        normalized = normalize_arkade5_report(SAMPLE)
        rec = build_arkade5_reconciliation(normalized, {"summary": {"archive_count": 1, "archive_part_count": 4}})
        self.assertEqual(rec["items"], [])
        self.assertEqual(rec["summary"], {"match": 0, "mismatch": 0, "not_available": 0})

    def test_import_preserves_original_normalizes_and_writes_reconciliation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "arkade.json"
            source.write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
            depot = root / "depot_validation_report.json"
            depot.write_text(json.dumps({"summary": {"archive_count": 1, "archive_part_count": 5}}), encoding="utf-8")
            work = root / "work"
            manifest = import_arkade5_report(source, work_operations=work, depot_report_path=depot, imported_by={"user_id": "u1", "username": "tester"})
            self.assertEqual(manifest["evidence_source"], "Arkade 5")
            self.assertEqual(manifest["normalized_format_version"], 2)
            self.assertEqual(manifest["imported_by"]["user_id"], "u1")
            self.assertTrue((work / manifest["source"]["preserved_file"]).is_file())
            self.assertTrue((work / manifest["normalized_file"]).is_file())
            self.assertTrue((work / manifest["reconciliation_file"]).is_file())

    def test_same_source_hash_is_stable_import_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "arkade.json"
            source.write_text(json.dumps(SAMPLE), encoding="utf-8")
            work = root / "work"
            a = import_arkade5_report(source, work_operations=work)
            b = import_arkade5_report(source, work_operations=work)
            self.assertEqual(a["import_id"], b["import_id"])
            self.assertEqual(len(list_arkade5_imports(work)), 1)

    def test_list_and_load_return_materialized_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "arkade.json"
            source.write_text(json.dumps(SAMPLE), encoding="utf-8")
            work = root / "work"
            manifest = import_arkade5_report(source, work_operations=work)
            listed = list_arkade5_imports(work)
            self.assertEqual(listed[0]["import_id"], manifest["import_id"])
            loaded = load_arkade5_import(work, manifest["import_id"])
            self.assertEqual(loaded["normalized"]["tests"][0]["test_id"], "N5.04")

    def test_invalid_json_shape_is_rejected(self):
        with self.assertRaises(Arkade5ImportError):
            normalize_arkade5_report({"foo": "bar"})

    def test_gui_exposes_external_evidence_tab_and_import_action(self):
        gui = (Path(__file__).resolve().parents[1] / "gui" / "depot_result_views.py").read_text(encoding="utf-8")
        self.assertIn('"Ekstern evidens"', gui)
        self.assertIn("Importer Arkade 5 JSON...", gui)
        self.assertIn("import_arkade5_report", gui)
        self.assertIn("arkade_evidence_text", gui)


if __name__ == "__main__":
    unittest.main()
