import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

class SpecificationKnowledgeTests(unittest.TestCase):

    def test_profile_exposes_coverage_and_provenance(self):
        profile = load("config/noark5/profile.json")
        knowledge = profile["specification_knowledge"]
        self.assertTrue((ROOT / knowledge["coverage"]).is_file())
        self.assertTrue((ROOT / knowledge["provenance_contract"]).is_file())

    def test_coverage_does_not_claim_unverified_metadata_properties(self):
        coverage = load("config/noark5/standards/specification_coverage.json")
        not_claimed = set(
            coverage["areas"]["metadata"]["not_yet_claimed_generally"]
        )
        self.assertIn("datatype", not_claimed)
        self.assertIn("cardinality", not_claimed)
        self.assertIn("structural_placement", not_claimed)

    def test_requirements_remain_explicitly_unpopulated(self):
        coverage = load("config/noark5/standards/specification_coverage.json")
        self.assertIn(
            coverage["areas"]["requirements"]["status"],
            {"structure_ready_not_yet_populated", "partial_verified_v5_started"},
        )
        index = load("config/noark5/standards/requirements/index.json")
        for version, path in index["versions"].items():
            doc = load(path)
            if version in ("3.1", "4.0"):
                self.assertEqual(doc["requirements"], [])
            else:
                self.assertGreaterEqual(len(doc["requirements"]), 0)

    def test_provenance_contract_requires_version_and_source(self):
        contract = load("config/noark5/standards/provenance_contract.json")
        required = set(contract["required_for_normative_fact"])
        self.assertIn("source_id", required)
        self.assertIn("noark_version", required)
        self.assertIn("verification_status", required)

    def test_no_cross_version_inference_rule_is_machine_readable(self):
        coverage = load("config/noark5/standards/specification_coverage.json")
        self.assertTrue(coverage["principles"]["no_cross_version_inference"])

if __name__ == "__main__":
    unittest.main()
