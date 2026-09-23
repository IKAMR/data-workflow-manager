import unittest

from noark5_workflow.external_evidence.combined_coverage import build_combined_coverage


MAPPING = {
    "mapping_id": "test-mapping",
    "arkade_to_dwm": [
        {"arkade_test_id": "N5.19", "relation": "equivalent", "dwm_test_ids": ["kdrs.c17"]},
        {"arkade_test_id": "N5.30", "relation": "arkade_only", "dwm_test_ids": []},
        {"arkade_test_id": "N5.24", "relation": "partial", "dwm_test_ids": ["kdrs.c22"]},
    ],
    "dwm_only": [{"dwm_test_id": "kdrs.f13", "legacy_namespace_id": None, "note_nb": "x"}],
}

CATALOG = {
    "catalog_id": "arkade-test",
    "tests": [
        {"arkade_test_id": "N5.19", "name_nb": "Klasse/registrering", "arkade_type": "ContentAnalysis"},
        {"arkade_test_id": "N5.30", "name_nb": "Sjekksum", "arkade_type": "ContentControl"},
        {"arkade_test_id": "N5.24", "name_nb": "Dokumentobjekt", "arkade_type": "ContentAnalysis"},
    ],
}


class V015A4CombinedArkadeCoverageTests(unittest.TestCase):
    def test_arkade_only_fills_documented_gap(self):
        normalized = {"tests": [{"test_id": "N5.30", "source_status": "ok", "number_of_errors": 0, "results": []}]}
        model = build_combined_coverage(
            arkade_normalized=normalized,
            dwm_test_ids_present=[],
            mapping=MAPPING,
            arkade_catalog=CATALOG,
        )
        row = next(x for x in model["arkade_control_areas"] if x["arkade_test_id"] == "N5.30")
        self.assertEqual(row["combined_status"], "covered_by_arkade")
        self.assertEqual(row["coverage_strategy"], "arkade_fills_dwm_gap")

    def test_partial_keeps_both_sources_separate(self):
        normalized = {"tests": [{"test_id": "N5.24", "source_status": "error", "number_of_errors": 1, "results": [{"message": "x"}]}]}
        model = build_combined_coverage(
            arkade_normalized=normalized,
            dwm_test_ids_present=["kdrs.c22"],
            mapping=MAPPING,
            arkade_catalog=CATALOG,
        )
        row = next(x for x in model["arkade_control_areas"] if x["arkade_test_id"] == "N5.24")
        self.assertEqual(row["combined_status"], "covered_by_both")
        self.assertEqual(row["relation"], "partial")
        self.assertEqual(row["arkade"]["status"], "error")
        self.assertEqual(model["summary"]["arkade_errors"], 1)

    def test_missing_arkade_does_not_claim_gap_is_covered(self):
        model = build_combined_coverage(
            arkade_normalized={"tests": []},
            dwm_test_ids_present=[],
            mapping=MAPPING,
            arkade_catalog=CATALOG,
        )
        row = next(x for x in model["arkade_control_areas"] if x["arkade_test_id"] == "N5.30")
        self.assertEqual(row["combined_status"], "not_covered_in_run")

    def test_dwm_only_namespace_is_preserved(self):
        model = build_combined_coverage(
            arkade_normalized={"tests": []},
            dwm_test_ids_present=["kdrs.f13"],
            mapping=MAPPING,
            arkade_catalog=CATALOG,
        )
        self.assertTrue(model["dwm_only"][0]["present"])
        self.assertEqual(model["dwm_only"][0]["relation"], "dwm_only")


if __name__ == "__main__":
    unittest.main()
