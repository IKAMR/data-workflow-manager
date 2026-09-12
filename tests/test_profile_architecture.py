import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class ProfileArchitectureTests(unittest.TestCase):

    def test_noark5_profile_manifest_exists_and_is_complete(self):
        profile = load_json("config/noark5/profile.json")
        required = {
            "profile_format_version",
            "profile_id",
            "display_name",
            "status",
            "profile_root",
            "principles",
            "sources",
            "capabilities",
            "definitions",
            "documentation",
        }
        self.assertTrue(required <= set(profile))
        self.assertEqual(profile["profile_id"], "noark5")
        self.assertTrue(
            profile["principles"]["manifest_is_authoritative_entrypoint"]
        )

    def test_noark5_profile_references_existing_local_paths(self):
        profile = load_json("config/noark5/profile.json")
        paths = [profile["sources"]["registry"]]

        for key in (
            "tests",
            "analysis",
            "standards",
            "schemas",
            "views",
            "field_definitions",
            "metadata",
            "requirements",
        ):
            paths.extend(profile["definitions"].get(key, []))

        paths.extend(profile.get("documentation", []))

        missing = [path for path in paths if not (ROOT / path).exists()]
        base_repo_marker = ROOT / "config/noark5/analysis/u1_total.json"
        if missing and not base_repo_marker.exists():
            self.skipTest(
                "Overlay-pakke: full repo-referanser valideres etter innliming i repoet"
            )
        self.assertEqual(missing, [])

    def test_source_registry_roles(self):
        profile = load_json("config/noark5/profile.json")
        registry = load_json(profile["sources"]["registry"])

        self.assertTrue(
            any(
                "authoritative_metadata" in source.get("role", [])
                for source in registry["sources"]
            )
        )
        self.assertTrue(
            any(
                "legacy_reference" in source.get("role", [])
                for source in registry["sources"]
            )
        )

    def test_generic_profile_schema_exists(self):
        schema = load_json("config/profile.schema.json")
        self.assertIn("profile_id", schema["required"])
        self.assertIn("definitions", schema["required"])
        self.assertIn("sources", schema["required"])


if __name__ == "__main__":
    unittest.main()
