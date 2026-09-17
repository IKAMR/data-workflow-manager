from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.operation_metadata import (
    belongs_to_profile,
    display_category,
    load_operation_metadata,
    operation_profiles,
    short_name,
)
from app.workflow_sequence import (
    WorkflowSequence,
    load_workflow_sequences,
    save_user_workflow_sequences,
)
from noark5_workflow.app import build_registry


class A10OperationCatalogAndSequenceTests(unittest.TestCase):
    def test_noark5_catalog_has_short_names_for_registered_operations(self):
        registry = build_registry()
        for operation in registry.all():
            op_id = operation.definition.operation_id
            self.assertTrue(short_name(op_id, ""), op_id)

    def test_current_operations_are_explicitly_scoped_to_noark5(self):
        registry = build_registry()
        for operation in registry.all():
            op_id = operation.definition.operation_id
            self.assertIn("noark5", operation_profiles(op_id), op_id)
            # A registered operation may be deliberately hidden from the user
            # catalogue while still belonging to the Noark 5 implementation.
            if op_id == "analyse_noark5_core":
                self.assertFalse(belongs_to_profile(op_id, "noark5"), op_id)
            else:
                self.assertTrue(belongs_to_profile(op_id, "noark5"), op_id)
            self.assertFalse(belongs_to_profile(op_id, "default"), op_id)

    def test_catalog_uses_compact_display_categories(self):
        metadata = load_operation_metadata()
        self.assertEqual(
            list(metadata["display_categories"]),
            ["Kontroll", "Analyse", "Resultat", "Pakking", "Referanse", "Avansert"],
        )
        self.assertEqual(display_category("run_noark5_xpath_tests_2026"), "Kontroll")
        self.assertEqual(display_category("compose_noark5_views"), "Resultat")
        self.assertEqual(display_category("analyse_noark5_u1"), "Referanse")

    def test_user_facing_names_hide_implementation_language(self):
        self.assertEqual(short_name("run_noark5_xpath_tests_2026"), "Noark 5-tester")
        self.assertEqual(short_name("compose_noark5_views"), "Resultatvisninger")
        self.assertEqual(short_name("build_noark5_depot_report"), "Depotrapport")

    def test_builtin_standard_sequence_is_valid_for_current_registry(self):
        registry = build_registry()
        catalog = load_workflow_sequences()
        sequence = catalog.get("noark5_standard")
        self.assertEqual(sequence.profile_id, "noark5")
        self.assertEqual(catalog.validate_operations(op.definition.operation_id for op in registry.all())[sequence.sequence_id], ())
        self.assertNotIn("run_noark5_xpath_regression_2026", sequence.operation_ids)
        self.assertNotIn("dias_package", sequence.operation_ids)

    def test_sequence_catalog_can_filter_by_profile(self):
        catalog = load_workflow_sequences()
        noark5 = catalog.for_profile("noark5")
        self.assertGreaterEqual(len(noark5), 2)
        self.assertEqual(catalog.for_profile("default"), [])

    def test_user_sequences_can_be_saved_and_loaded_as_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workflow_sequences.json"
            custom = WorkflowSequence(
                sequence_id="my_noark5",
                name="Min Noark 5",
                profile_id="noark5",
                operation_ids=("validate_xml_schema", "run_noark5_xpath_tests_2026"),
                builtin=False,
            )
            save_user_workflow_sequences(path, [custom])
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["sequences"][0]["sequence_id"], "my_noark5")
            catalog = load_workflow_sequences(path)
            self.assertEqual(catalog.get("my_noark5").operation_ids, custom.operation_ids)
            self.assertFalse(catalog.get("my_noark5").builtin)


if __name__ == "__main__":
    unittest.main()
