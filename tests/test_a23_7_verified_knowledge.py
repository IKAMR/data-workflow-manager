"""Regression checks for source-verified Noark 5 knowledge.

Originally introduced in a23 with two functional requirements. The registry
was extended in v0.2.1-a4 with four metadata obligations; tests must validate
that extension rather than assuming the historic number of entries.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


ORIGINAL_FUNCTIONAL_IDS = {
    "noark5.v5.class.authorized_creation",
    "noark5.v5.class.closure_prevents_new_folders",
}

A4_METADATA_REQUIREMENTS = {
    "noark5.v5.class.class_id_mandatory": ("M002", "klasseID", "klasse"),
    "noark5.v5.folder.folder_id_mandatory": ("M003", "mappeID", "mappe"),
    "noark5.v5.document_object.version_number_mandatory": (
        "M005", "versjonsnummer", "dokumentobjekt"
    ),
    "noark5.v5.document_description.document_number_mandatory": (
        "M007", "dokumentnummer", "dokumentbeskrivelse"
    ),
}


class A237VerifiedKnowledgeTests(unittest.TestCase):
    def test_v5_m001_verified(self):
        doc = load("config/noark5/standards/metadata/5.0.json")
        entries = [
            item for item in doc["metadata"]
            if item.get("metadata_id") == "M001"
            and item.get("verification_status") == "verified"
        ]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["source_id"], "noark5-5.0-metadata-catalog")
        self.assertEqual(entry["normative_properties"]["obligation"], "mandatory")
        self.assertEqual(entry["normative_properties"]["occurrence"], "one")
        self.assertEqual(entry["normative_properties"]["condition"], "Skal ikke kunne endres")

    def test_v5_requirements_provenance(self):
        doc = load("config/noark5/standards/requirements/5.0.json")
        requirements = doc["requirements"]
        ids = [item["requirement_id"] for item in requirements]
        self.assertEqual(len(ids), len(set(ids)), "Krav-ID-er må være unike")
        self.assertTrue(ORIGINAL_FUNCTIONAL_IDS.issubset(ids))
        self.assertTrue(set(A4_METADATA_REQUIREMENTS).issubset(ids))
        for requirement in requirements:
            with self.subTest(requirement=requirement["requirement_id"]):
                self.assertEqual(requirement["verification_status"], "verified")
                self.assertEqual(requirement["id_role"], "local_registry_id")
                self.assertEqual(requirement["noark_version"], "5.0")
                self.assertTrue(requirement["source_id"])
                self.assertTrue(requirement["source_location"])
                self.assertIsInstance(
                    requirement["extract_validation"]["directly_testable_from_extract"],
                    bool,
                )

    def test_original_functional_requirements_not_extract_testable(self):
        doc = load("config/noark5/standards/requirements/5.0.json")
        by_id = {item["requirement_id"]: item for item in doc["requirements"]}
        for requirement_id in sorted(ORIGINAL_FUNCTIONAL_IDS):
            with self.subTest(requirement=requirement_id):
                item = by_id[requirement_id]
                self.assertEqual(item["rule_type"], "functional_requirement")
                self.assertFalse(item["extract_validation"]["directly_testable_from_extract"])

    def test_new_metadata_requirements_are_not_claimed_implemented(self):
        doc = load("config/noark5/standards/requirements/5.0.json")
        metadata = load("config/noark5/standards/metadata/5.0.json")
        by_id = {item["requirement_id"]: item for item in doc["requirements"]}
        metadata_by_id = {item["metadata_id"]: item for item in metadata["metadata"]}
        for requirement_id, (metadata_id, xml_name, subject) in A4_METADATA_REQUIREMENTS.items():
            with self.subTest(requirement=requirement_id):
                item = by_id[requirement_id]
                field = metadata_by_id[metadata_id]
                self.assertEqual(item["rule_type"], "metadata_obligation")
                self.assertEqual(item["source_id"], "noark5-5.0-metadata-catalog")
                self.assertEqual(item["related_metadata_id"], metadata_id)
                self.assertEqual(item["xml_field_name"], xml_name)
                self.assertEqual(item["subject"], subject)
                self.assertEqual(field["name"], xml_name)
                self.assertEqual(field["normative_properties"]["obligation"], "mandatory")
                self.assertEqual(field["normative_properties"]["occurrence"], "one")
                self.assertTrue(item["extract_validation"]["directly_testable_from_extract"])
                self.assertFalse(item["extract_validation"]["implemented_as_dwm_control"])

    def test_older_versions_still_empty(self):
        for version in ("3.1", "4.0"):
            with self.subTest(version=version):
                doc = load(f"config/noark5/standards/requirements/{version}.json")
                self.assertEqual(doc["requirements"], [])

    def test_coverage_explicitly_incomplete(self):
        coverage = load("config/noark5/standards/specification_coverage.json")
        registered = load("config/noark5/standards/requirements/5.0.json")["requirements"]
        verified = sum(item.get("verification_status") == "verified" for item in registered)
        counts = coverage["areas"]["requirements"]["verified_requirement_count"]
        self.assertEqual(counts["5.0"], verified)
        self.assertGreaterEqual(verified, len(ORIGINAL_FUNCTIONAL_IDS) + len(A4_METADATA_REQUIREMENTS))
        self.assertEqual(counts["3.1"], 0)
        self.assertEqual(counts["4.0"], 0)
        profile = load("config/noark5/profile.json")
        self.assertFalse(profile["specification_knowledge"]["maturity"]["full_specification_coverage"])


if __name__ == "__main__":
    unittest.main()
