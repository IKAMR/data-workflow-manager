from __future__ import annotations

import unittest

from app.profile import WorkflowProfile
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, OperationDefinition
from noark5_workflow.core.result import OperationResult
from noark5_workflow.profile import (
    NOARK5_CATEGORIES,
    NOARK5_CATEGORY_COLORS,
    NOARK5_PROFILE,
)


class DummyOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id="dummy",
        name="Dummy",
        description="Test operation",
        category="Generated category",
    )

    def run(self, ctx: OperationContext) -> OperationResult:
        return OperationResult(True, "OK")


class ProfileRegistryA12Tests(unittest.TestCase):
    def test_profile_builds_registry(self):
        profile = WorkflowProfile(
            profile_id="test",
            name="Test",
            categories=("First", "Second"),
            operation_factories=(DummyOperation,),
        )
        registry = profile.build_registry()
        self.assertEqual(registry.get("dummy").definition.name, "Dummy")
        self.assertEqual(
            registry.categories(),
            ["First", "Second", "Generated category"],
        )

    def test_noark5_profile_preserves_operations(self):
        registry = NOARK5_PROFILE.build_registry()
        self.assertEqual(
            [op.definition.operation_id for op in registry.all()],
            [
                "metadata_inventory",
                "analyse_arkivstruktur",
                "analyse_noark5_core",
                "analyse_noark5_u1",
                "run_noark5_xpath_tests_2026",
                "run_noark5_xpath_regression_2026",
                "compose_noark5_views",
                "build_noark5_depot_report",
                "validate_xml_schema",
                "dias_package",
            ],
        )

    def test_profile_carries_category_presentation_metadata(self):
        registry = NOARK5_PROFILE.build_registry()
        self.assertEqual(
            registry.category_color("Metadata"),
            NOARK5_CATEGORY_COLORS["Metadata"],
        )
        self.assertEqual(
            registry.category_color("Unknown", "#fallback"),
            "#fallback",
        )

    def test_noark5_profile_preserves_categories(self):
        self.assertEqual(
            NOARK5_PROFILE.build_registry().categories(),
            list(NOARK5_CATEGORIES),
        )


if __name__ == "__main__":
    unittest.main()
