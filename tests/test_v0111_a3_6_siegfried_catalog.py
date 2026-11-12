"""Prevent newly registered Noark 5 tools from losing their catalog metadata.

These checks intentionally use the public metadata API and actual registry; a
missing registration must fail, rather than being silently accepted as generic.
"""
from __future__ import annotations

import unittest

from app.operation_metadata import (
    belongs_to_profile,
    catalogue_visible,
    display_category,
    maturity_name,
    operation_profiles,
    short_name,
)
from noark5_workflow.app import build_registry


class SiegfriedCatalogA36Tests(unittest.TestCase):
    ID = "siegfried_pronom_identification"

    def test_siegfried_registered_in_noark5(self):
        registry = build_registry()
        ids = [op.definition.operation_id for op in registry.all()]
        self.assertEqual(ids.count(self.ID), 1)
        self.assertIn(self.ID, ids)

    def test_siegfried_visible_in_noark5_but_not_default(self):
        self.assertEqual(operation_profiles(self.ID), ("noark5",))
        self.assertTrue(belongs_to_profile(self.ID, "noark5"))
        self.assertFalse(belongs_to_profile(self.ID, "default"))
        self.assertTrue(catalogue_visible(self.ID))

    def test_siegfried_has_explicit_presentation_metadata(self):
        self.assertEqual(short_name(self.ID), "Siegfried PRONOM")
        self.assertEqual(display_category(self.ID), "Analyse")
        self.assertEqual(maturity_name(self.ID), "alpha")


if __name__ == "__main__":
    unittest.main()
