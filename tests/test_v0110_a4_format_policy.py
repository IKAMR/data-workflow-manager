"""a4: safe, versioned file-format rules independent of any PRONOM engine."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from app.format_policy_v0110_a4 import (
    FORMAT_PROFILE_DIR, STATUS_ACCEPTED, STATUS_CLARIFY,
    STATUS_NOT_ASSESSED, STATUS_UNIDENTIFIED,
    discover_format_policies, evaluate_puid, export_format_assessments_csv,
    load_format_policy, summarize_format_assessments,
)


class FormatPolicyV0110A4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile_path = FORMAT_PROFILE_DIR / 'nasjonalarkivet_2026-11-10.json'
        cls.policy = load_format_policy(cls.profile_path)

    def test_dated_snapshot_contains_all_111_unique_puids(self):
        self.assertEqual(len(self.policy.entries), 111)
        self.assertEqual(self.policy.edition, '2026-11-10 (datert kopi)')
        self.assertEqual(len(self.policy.sha256), 64)
        self.assertEqual(len(discover_format_policies()), 1)
        self.assertEqual(self.policy.entries['fmt/279'].versions, '1.2.1')

    def test_known_format_is_listed_not_automatically_approved_aip(self):
        for puid in ('fmt/101', 'x-fmt/18', 'fmt/279', 'fmt/947', 'fmt/354'):
            with self.subTest(puid=puid):
                d = evaluate_puid(puid, self.policy)
                self.assertEqual(d.status, STATUS_ACCEPTED)
                self.assertIsNotNone(d.matched_rule)
                self.assertIn('erstatter ikke faglig godkjenning', d.explanation)

    def test_nonlisted_format_only_needs_clarification(self):
        d = evaluate_puid('fmt/999999', self.policy)
        self.assertEqual(d.status, STATUS_CLARIFY)
        self.assertNotIn('må konverteres', d.explanation)

    def test_missing_and_invalid_puids_are_unidentified(self):
        for value in ('', None, '-', 'unknown', 'fmt/unknown', '../fmt/12', 'fmt/101;fmt/102'):
            with self.subTest(value=value):
                self.assertEqual(evaluate_puid(value, self.policy).status,
                                 STATUS_UNIDENTIFIED)

    def test_valid_puid_without_selected_policy_is_not_assessed(self):
        self.assertEqual(evaluate_puid('fmt/101', None).status, STATUS_NOT_ASSESSED)
        self.assertEqual(evaluate_puid('not_identified', None).status,
                         STATUS_UNIDENTIFIED)

    def test_normalizes_case_and_spaces_not_wrong_puid(self):
        self.assertEqual(evaluate_puid(' FMT/101  ', self.policy).status,
                         STATUS_ACCEPTED)
        self.assertEqual(evaluate_puid('fmt/1001', self.policy).status,
                         STATUS_CLARIFY)

    def test_summary_is_format_source_agnostic(self):
        observations = [
            {'format_id': 'fmt/101', 'count': '1 024', 'source': 'Arkade 5'},
            {'puid': 'fmt/999999', 'count': 5, 'source': 'Siegfried'},
            {'Format-ID': 'unknown', 'Antall': 2},
        ]
        summary = summarize_format_assessments(observations, self.policy)
        self.assertEqual(summary['statuses'][STATUS_ACCEPTED]['files'], 1024)
        self.assertEqual(summary['statuses'][STATUS_CLARIFY]['files'], 5)
        self.assertEqual(summary['statuses'][STATUS_UNIDENTIFIED]['files'], 2)
        self.assertEqual(summary['policy']['sha256'], self.policy.sha256)

    def test_csv_export_keeps_arkade_raf_separate_and_policy_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'formats.csv'
            rows = [
                {'job': 'Test', 'format_id': 'fmt/101', 'file_type': 'XML',
                 'version': '1.0', 'count': 7, 'raf': 'RAF-220301',
                 'evidence_source': 'import-A'},
                {'job': 'Test', 'format_id': 'fmt/999999', 'count': 3, 'raf': ''},
            ]
            export_format_assessments_csv(target, rows, self.policy)
            with target.open(encoding='utf-8-sig', newline='') as handle:
                actual = list(csv.DictReader(handle, delimiter=';'))
            self.assertEqual(actual[0]['Vurdering'], 'Akseptert i valgt profil')
            self.assertEqual(actual[1]['Vurdering'], 'Til avklaring')
            self.assertEqual(actual[0]['Profil SHA-256'], self.policy.sha256)
            self.assertEqual(actual[0]['Arkade RAF (historisk observasjon)'], 'RAF-220301')
            self.assertEqual(actual[0]['Kilde/import'], 'import-A')
            with self.assertRaises(FileExistsError):
                export_format_assessments_csv(target, rows, self.policy)
            self.assertEqual(len(actual), 2)

    def test_rejects_modified_profile_with_duplicate_or_malformed_puid(self):
        base = json.loads(self.profile_path.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'test.json'
            for bad in ('duplicate', 'traversal', 'unknown_schema', 'missing_source'):
                model = json.loads(json.dumps(base))
                if bad == 'duplicate':
                    model['accepted_puids'].append(model['accepted_puids'][0])
                elif bad == 'traversal':
                    model['accepted_puids'][0]['puid'] = '../fmt/101'
                elif bad == 'unknown_schema':
                    model['schema_version'] = 10
                elif bad == 'missing_source':
                    del model['source_url']
                path.write_text(json.dumps(model), encoding='utf-8')
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    load_format_policy(path)

    def test_pinned_versions_cannot_retroactively_change_previous_result(self):
        base = json.loads(self.profile_path.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'edition-v2.json'
            base['edition'] = 'user-example-2'
            base['accepted_puids'] = [r for r in base['accepted_puids']
                                      if r['puid'].strip() != 'fmt/101']
            path.write_text(json.dumps(base), encoding='utf-8')
            other = load_format_policy(path)
            self.assertNotEqual(other.sha256, self.policy.sha256)
            self.assertEqual(evaluate_puid('fmt/101', other).status, STATUS_CLARIFY)
            self.assertEqual(evaluate_puid('fmt/101', self.policy).status, STATUS_ACCEPTED)


if __name__ == '__main__':
    unittest.main()
