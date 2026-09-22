from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DataWorkflowManagerDocumentationA12Tests(unittest.TestCase):
    def setUp(self):
        self.text = (
            ROOT / "docs" / "DATA-WORKFLOW-MANAGER.md"
        ).read_text(encoding="utf-8")

    def test_planned_repository_and_history_strategy_are_documented(self):
        self.assertIn("IKAMR/data-workflow-manager", self.text)
        self.assertIn("viderefør Git-historikken", self.text)

    def test_profile_registry_and_source_boundaries_are_documented(self):
        self.assertIn("WorkflowProfile", self.text)
        self.assertIn("OperationRegistry", self.text)
        self.assertIn("WorkflowSource", self.text)
        self.assertIn("OperationContext.input_root", self.text)

    def test_migration_directions_are_documented(self):
        self.assertIn("ADDML 7.3 -> SIARD", self.text)
        self.assertIn("SIARD -> SIARD", self.text)
        self.assertIn("Noark 5 -> SIARD", self.text)
        self.assertIn("generering av Noark 5-uttrekk", self.text)

    def test_a12_scope_explicitly_avoids_large_refactor(self):
        self.assertIn("Hva a12 uttrykkelig ikke gjør", self.text)
        self.assertIn("dynamisk plugin-discovery/installasjon", self.text)
        self.assertIn("bred omdøping av `noark5_workflow`", self.text)


if __name__ == "__main__":
    unittest.main()
