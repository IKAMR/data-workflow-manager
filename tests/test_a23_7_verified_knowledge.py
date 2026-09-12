import json, unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
def load(path): return json.loads((ROOT/path).read_text(encoding="utf-8"))

class A237VerifiedKnowledgeTests(unittest.TestCase):
    def test_v5_m001_verified(self):
        doc=load("config/noark5/standards/metadata/5.0.json")
        m=[x for x in doc["metadata"] if x.get("metadata_id")=="M001" and x.get("verification_status")=="verified"]
        self.assertEqual(len(m),1)
        x=m[0]
        self.assertEqual(x["source_id"],"noark5-5.0-metadata-catalog")
        self.assertEqual(x["normative_properties"]["obligation"],"mandatory")
        self.assertEqual(x["normative_properties"]["occurrence"],"one")
        self.assertEqual(x["normative_properties"]["condition"],"Skal ikke kunne endres")
    def test_v5_requirements_provenance(self):
        doc=load("config/noark5/standards/requirements/5.0.json")
        self.assertEqual(len(doc["requirements"]),2)
        for r in doc["requirements"]:
            self.assertEqual(r["verification_status"],"verified")
            self.assertEqual(r["id_role"],"local_registry_id")
            self.assertFalse(r["extract_validation"]["directly_testable_from_extract"])
    def test_older_versions_still_empty(self):
        for v in ("3.1","4.0"):
            d=load(f"config/noark5/standards/requirements/{v}.json")
            self.assertEqual(d["requirements"],[])
    def test_coverage_explicitly_incomplete(self):
        c=load("config/noark5/standards/specification_coverage.json")
        self.assertEqual(c["areas"]["requirements"]["verified_requirement_count"]["5.0"],2)
        p=load("config/noark5/profile.json")
        self.assertFalse(p["specification_knowledge"]["maturity"]["full_specification_coverage"])
if __name__=="__main__": unittest.main()
