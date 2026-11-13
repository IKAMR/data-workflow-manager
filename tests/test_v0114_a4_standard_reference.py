from __future__ import annotations
import unittest
from app.noark_standard_reference_v0114_a4 import reference_for_finding, reference_versions

class MetadataReferenceTests(unittest.TestCase):
    def test_m300_versions_and_exact_values(self):
        self.assertEqual(reference_versions('kdrs.c02', 'document_medium'), ('3.1','4.0','5.0'))
        ref=reference_for_finding('kdrs.c02','document_medium','5.0')
        self.assertEqual(ref['metadata_id'],'M300')
        self.assertIn('Elektronisk arkiv',ref['values'])
        self.assertNotIn('Elektroniskarkiv',ref['values'])
        self.assertEqual(ref['source_xml'],'arkivstruktur.xml')
        self.assertEqual(ref['xpath'],'//arkivdel//dokumentbeskrivelse/dokumentmedium')

    def test_journal_and_screening(self):
        self.assertEqual(reference_for_finding('kdrs.c15','journalpost_type','5.0')['metadata_id'],'M082')
        self.assertEqual(reference_for_finding('kdrs.f08','access_restriction','5.0')['metadata_id'],'M500')
        self.assertEqual(reference_for_finding('kdrs.f08','screening_metadata','5.0')['metadata_id'],'M502')

    def test_missing_version_or_unknown_field_does_not_guess(self):
        self.assertIsNone(reference_for_finding('kdrs.c02','document_medium','6.0'))
        self.assertIsNone(reference_for_finding('kdrs.c02','arbitrary','5.0'))
        self.assertEqual(reference_versions('unknown','journalpost_type'),())

if __name__=='__main__': unittest.main()
