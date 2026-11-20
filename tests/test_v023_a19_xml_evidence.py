"""A19: verify source-scoped, on-demand XML hierarchy, never invented evidence."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.ks_xml_evidence_v023_a19 import (
    XmlEvidenceError, documented_anchors, inspect_xml_anchor, resolve_source_xml,
)


XML = '''<?xml version="1.0" encoding="utf-8"?>
<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur">
  <systemID>ark-1</systemID>
  <arkivdel>
    <systemID>AD-1</systemID>
    <tittel>Første arkivdel</tittel>
    <mappe>
      <systemID>MAP-1</systemID>
      <registrering>
        <systemID>REG-1</systemID>
        <journalstatus>Arkivert</journalstatus>
      </registrering>
    </mappe>
  </arkivdel>
  <arkivdel>
    <systemID>AD-2</systemID>
    <tittel>Andre arkivdel</tittel>
    <mappe>
      <systemID>MAP-2</systemID>
      <registrering>
        <systemID>REG-2</systemID>
        <journalstatus>Utgår</journalstatus>
      </registrering>
    </mappe>
  </arkivdel>
</arkiv>
'''


class A19XmlEvidence(unittest.TestCase):
    def setUp(self):
        t = TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.xml = self.source / 'arkivstruktur.xml'
        self.xml.write_text(XML, encoding='utf-8')
        self.job = self.work / 'job.json'
        self.write_job(self.source)
        self.target_line = next(i for i, v in enumerate(XML.splitlines(), 1)
                                if '<journalstatus>Utgår</journalstatus>' in v)

    def write_job(self, source, **more):
        self.job.write_text(json.dumps({
            'file_type': 'dwm-work-job', 'format_version': 1, 'job_uid': 'job-19',
            'job': {'job_id': 'JOB-001', 'job_uid': 'job-19',
                    'source_root': str(source), **more},
        }), encoding='utf-8')

    def anchor(self, **kwargs):
        return {'file': 'arkivstruktur.xml', 'line': self.target_line,
                'test_id': 'N5.22', 'source_ref': 'work/verified-finding.json',
                **kwargs}

    def test_one_documented_line_includes_actual_ancestor_chain(self):
        result = inspect_xml_anchor(self.work, self.anchor())
        self.assertTrue(result['available'])
        self.assertIn('Utgår', result['excerpt'])
        self.assertEqual(result['source_identity'], 'not_attested')
        self.assertFalse(result['metadata']['ambiguous'])
        self.assertTrue(result['metadata']['xpath'].endswith(
            '/arkivdel[2]/mappe[1]/registrering[1]/journalstatus[1]'))
        levels = result['metadata']['hierarchy']
        parts = [row for row in levels if row['element'] == 'arkivdel']
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]['position'], 2)
        self.assertEqual(parts[0]['system_id'], 'AD-2')
        self.assertEqual(parts[0]['title'], 'Andre arkivdel')
        self.assertEqual(next(row for row in levels if row['element'] == 'mappe')['system_id'], 'MAP-2')
        self.assertEqual(next(row for row in levels if row['element'] == 'registrering')['system_id'], 'REG-2')
        self.assertTrue(all(row['total_siblings'] is None for row in levels))
        self.assertIn('IKKE dokumentert', result['provenance_note'])

    def test_exact_source_hash_provides_verified_identity(self):
        expected = sha256(self.xml.read_bytes()).hexdigest()
        result = inspect_xml_anchor(self.work, self.anchor(source_xml_sha256=expected))
        self.assertEqual(result['source_identity'], 'sha256_verified')
        self.assertEqual(result['expected_source_sha256'], expected)

    def test_modified_source_hash_is_rejected(self):
        with self.assertRaisesRegex(XmlEvidenceError, 'endret SHA-256'):
            inspect_xml_anchor(self.work, self.anchor(source_xml_sha256='0' * 64))

    def test_reported_xpath_is_a_label_not_a_substitute_for_actual_xpath(self):
        result = inspect_xml_anchor(self.work, self.anchor(reported_xpath='/arkiv[99]/mappe[8]'))
        self.assertEqual(result['reported_xpath'], '/arkiv[99]/mappe[8]')
        self.assertNotEqual(result['metadata']['xpath'], result['reported_xpath'])

    def test_ambiguous_multiple_tags_on_same_xml_line_never_get_exact_xpath(self):
        self.xml.write_text('<arkiv><arkivdel><systemID>A</systemID></arkivdel></arkiv>\n', encoding='utf-8')
        result = inspect_xml_anchor(self.work, self.anchor(line=1))
        self.assertEqual(result['metadata']['xpath'], '')
        self.assertTrue(result['metadata']['ambiguous'])

    def test_non_element_line_is_not_guessed(self):
        result = inspect_xml_anchor(self.work, self.anchor(line=1))
        self.assertEqual(result['metadata']['xpath'], '')
        self.assertEqual(result['metadata']['hierarchy'], [])

    def test_missing_line_is_rejected_not_shown_as_zero(self):
        with self.assertRaisesRegex(XmlEvidenceError, 'mangler dokumentert linje'):
            inspect_xml_anchor(self.work, self.anchor(line=1000))

    def test_unavailable_or_relocated_source_is_explained(self):
        self.write_job(self.root / 'missing')
        result = inspect_xml_anchor(self.work, self.anchor())
        self.assertFalse(result['available'])
        self.assertIn('ikke tilgjengelig', result['message'])

    def test_known_content_folder_works_without_scanning_other_jobs(self):
        folder = self.source / 'content'
        folder.mkdir()
        self.xml.rename(folder / self.xml.name)
        resolved = resolve_source_xml(self.work, 'arkivstruktur.xml')
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.samefile(folder / 'arkivstruktur.xml'),
                        'Source must be the exact file in the selected job, including Windows 8.3 aliases')
        self.assertTrue(inspect_xml_anchor(self.work, self.anchor())['available'])

    def test_ambiguous_configured_source_rejected(self):
        other = self.root / 'other'
        other.mkdir()
        (other / self.xml.name).write_text(XML, encoding='utf-8')
        self.write_job(self.source, source_extraction=str(other))
        with self.assertRaisesRegex(XmlEvidenceError, 'Flere ulike XML-kilder'):
            inspect_xml_anchor(self.work, self.anchor())

    def test_symlink_source_file_not_followed(self):
        self.xml.unlink()
        outside = self.root / 'elsewhere.xml'
        outside.write_text(XML, encoding='utf-8')
        try:
            self.xml.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('Symbolske lenker er ikke tilgjengelige')
        self.assertFalse(inspect_xml_anchor(self.work, self.anchor())['available'])

    def test_rejects_untrusted_filename_and_invalid_line(self):
        for name in ('../arkivstruktur.xml', 'C:/other/arkivstruktur.xml',
                     'dokumenter.xml', 'http://ex/arkivstruktur.xml', 'arkivstruktur.xml/..'):
            with self.subTest(name=name), self.assertRaises(XmlEvidenceError):
                inspect_xml_anchor(self.work, self.anchor(file=name))
        for line in (0, -1, True, '22', None):
            with self.subTest(line=line), self.assertRaises(XmlEvidenceError):
                inspect_xml_anchor(self.work, self.anchor(line=line))

    def test_multiple_jobs_not_cross_scanned(self):
        other_work = self.root / 'other_work'
        other_work.mkdir()
        (other_work / 'job.json').write_text(json.dumps({
            'file_type': 'dwm-work-job', 'job_uid': 'other',
            'job': {'job_id': 'JOB-002', 'source_root': str(self.root / 'not-source')},
        }), encoding='utf-8')
        self.assertFalse(inspect_xml_anchor(other_work, self.anchor())['available'])

    def test_changed_during_inspection_is_rejected(self):
        from app import ks_xml_evidence_v023_a19 as module
        original = module._context_at_line
        def altered(*args, **kwargs):
            value = original(*args, **kwargs)
            self.xml.write_text(XML + '<!-- changed -->\n', encoding='utf-8')
            return value
        with patch.object(module, '_context_at_line', side_effect=altered):
            with self.assertRaisesRegex(XmlEvidenceError, 'endret under inspeksjonen'):
                inspect_xml_anchor(self.work, self.anchor())

    def test_read_only_no_work_or_source_mutations(self):
        before = [(str(p.relative_to(self.root)), sha256(p.read_bytes()).hexdigest())
                  for p in (self.xml, self.job)]
        inspect_xml_anchor(self.work, self.anchor())
        after = [(str(p.relative_to(self.root)), sha256(p.read_bytes()).hexdigest())
                 for p in (self.xml, self.job)]
        self.assertEqual(before, after)
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), ['job.json'])

    def test_documented_anchors_do_not_guess_when_only_aggregate(self):
        row = {'source': 'Arkade 5', 'file': 'arkivstruktur.xml',
               'source_ref': 'external_evidence/arkade5/x/normalized/arkade5_results.json',
               'test_id': 'N5.22', 'message': 'Antall: 100', 'lines': []}
        result = documented_anchors(row)
        self.assertTrue(result['supported'])
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['rows'], [])

    def test_bounded_display_keeps_full_line_count_and_hash_role(self):
        row = {'source': 'DWM', 'file': 'arkivstruktur.xml', 'source_ref': 'qa/a.jsonl',
               'lines': list(range(1, 1302)), 'test_id': 'DWM-1',
               'source_xml_sha256': 'a' * 64}
        result = documented_anchors(row)
        self.assertEqual(result['total'], 1301)
        self.assertEqual(len(result['rows']), 1000)
        self.assertTrue(result['truncated_preview'])
        self.assertEqual(result['rows'][0]['source_xml_sha256'], 'a' * 64)

    def test_invalid_reported_lines_fail_closed(self):
        row = {'source': 'Arkade 5', 'file': 'arkivstruktur.xml',
               'source_ref': 'qa/a.jsonl', 'lines': [12, 14, 'x']}
        result = documented_anchors(row)
        self.assertFalse(result['supported'])
        self.assertEqual(result['rows'], [])

    def test_verified_different_xml_file_is_allowed_only_under_explicit_source(self):
        extra = self.source / 'offentligJournal.xml'
        extra.write_text('<offentligJournal>\n<journalpost/>\n</offentligJournal>\n', encoding='utf-8')
        result = inspect_xml_anchor(self.work, self.anchor(file='offentligJournal.xml', line=2))
        self.assertTrue(result['available'])
        self.assertTrue(Path(result['source_path']).samefile(extra),
                        'XML inspection must return the exact selected Source file')

    def test_many_archive_parts_are_counted_from_source_without_guessing_total(self):
        parts = '\n'.join(f'<arkivdel>\n<systemID>AD-{i}</systemID>\n</arkivdel>'
                          for i in range(1, 3002))
        doc = '<arkiv>\n' + parts + '\n</arkiv>\n'
        self.xml.write_text(doc, encoding='utf-8')
        line = next(i for i, text in enumerate(doc.splitlines(), 1)
                    if text == '<systemID>AD-3001</systemID>')
        result = inspect_xml_anchor(self.work, self.anchor(line=line))
        self.assertIn('/arkivdel[3001]/systemID[1]', result['metadata']['xpath'])
        record = next(row for row in result['metadata']['hierarchy'] if row['element'] == 'arkivdel')
        self.assertEqual(record['system_id'], 'AD-3001')
        self.assertEqual(record['position'], 3001)
        self.assertIsNone(record['total_siblings'])

    def test_invalid_declared_xml_hash_fails_closed(self):
        with self.assertRaisesRegex(XmlEvidenceError, 'Ugyldig oppgitt XML-kildehash'):
            inspect_xml_anchor(self.work, self.anchor(source_xml_sha256='not-a-sha256'))

    def test_same_source_declared_twice_is_not_false_ambiguity(self):
        self.write_job(self.source, source_extraction=str(self.source / '.'))
        result = inspect_xml_anchor(self.work, self.anchor())
        self.assertTrue(result['available'])

    def test_cancelled_inspection_raises_without_changing_evidence(self):
        with self.assertRaisesRegex(XmlEvidenceError, 'avbrutt'):
            inspect_xml_anchor(self.work, self.anchor(), cancelled=lambda: True)


if __name__ == '__main__':
    unittest.main()
