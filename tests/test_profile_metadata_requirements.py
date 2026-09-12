import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

class ProfileMetadataRequirementTests(unittest.TestCase):

    def test_profile_declares_metadata_and_requirements(self):
        profile = load("config/noark5/profile.json")
        self.assertEqual(
            profile["definitions"]["metadata"],
            ["config/noark5/standards/metadata/index.json"],
        )
        self.assertEqual(
            profile["definitions"]["requirements"],
            ["config/noark5/standards/requirements/index.json"],
        )

    def test_metadata_registry_versions_exist(self):
        index = load("config/noark5/standards/metadata/index.json")
        for version, path in index["versions"].items():
            self.assertTrue((ROOT / path).is_file(), version)
            doc = load(path)
            self.assertEqual(doc["noark_version"], version)
            self.assertTrue(doc["principles"]["missing_fields_are_not_inferred"])

    def test_metadata_entries_point_to_registered_value_sets(self):
        standards = load("config/noark5/standards/noark5_standard_values.json")
        index = load("config/noark5/standards/metadata/index.json")
        for version, path in index["versions"].items():
            valid_sets = set(standards["versions"][version]["value_sets"])
            doc = load(path)
            for item in doc["metadata"]:
                if "standard_value_set_id" in item:
                    self.assertIn(item["standard_value_set_id"], valid_sets)
                else:
                    self.assertEqual(item.get("verification_status"), "verified")
                    self.assertIn("source_id", item)

    def test_requirement_registries_are_explicitly_empty_until_verified(self):
        index = load("config/noark5/standards/requirements/index.json")
        for version, path in index["versions"].items():
            doc = load(path)
            self.assertTrue(
                doc["principles"]["only_explicitly_verified_requirements_may_be_added"]
            )
            if version in ("3.1", "4.0"):
                self.assertEqual(doc["status"], "not_yet_populated")
                self.assertEqual(doc["requirements"], [])
            else:
                self.assertEqual(doc["status"], "partial_verified_registry")
                self.assertGreater(len(doc["requirements"]), 0)

    def test_profile_paths_exist_including_new_definition_types(self):
        profile = load("config/noark5/profile.json")
        paths = [profile["sources"]["registry"]]
        for values in profile["definitions"].values():
            if isinstance(values, list):
                paths.extend(values)
        paths.extend(profile["documentation"])
        missing = [path for path in paths if not (ROOT / path).exists()]
        base_repo_marker = ROOT / "config/noark5/analysis/u1_total.json"
        if missing and not base_repo_marker.exists():
            self.skipTest(
                "Overlay-pakke: full repo-referanser valideres etter innliming i repoet"
            )
        self.assertEqual(missing, [])

if __name__ == "__main__":
    unittest.main()
