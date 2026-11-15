"""a10: static candidate crosswalk must never inflate implementation coverage."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.noark5_requirement_registry_v021_a9 import REPORT_TYPE as A9_REPORT_TYPE
from app.noark5_requirement_coverage_v021_a10 import (
    REPORT_TYPE, REPORT_NAMES, _csv_text, build_coverage, filter_coverage_rows,
    inventory_controls, write_reports, markdown_summary, _source_field_tokens,
)

COMMIT = '8d28e312e1e38af8cb93bfe05cecef11e09af34f'


def clause(version, number, text, suffix='1', severity='WARNING'):
    return {
        'candidate_id': f'{version}:{number}:{suffix}', 'noark_version': version,
        'number': number, 'text': text, 'origin': 'docx_word_numbered_table_paragraph',
        'requirement_class': 'B', 'remarks_or_conditions': '',
        'source': f'noark5/v{version}/spesifikasjoner/test.docx',
        'location': 'word/document.xml:tbl1:row2',
        'source_sha256': 'a'*64, 'qa_severity': severity,
        'qa_reasons': ['docx_transcription_not_normatively_approved'],
        'review_state': 'PENDING_MANUAL_QA', 'retired_text': False,
    }


def a9_report(rows):
    return {
        'report_type': A9_REPORT_TYPE,
        'source_repository': 'IKAMR/digital-archive-workflow',
        'source_checkout_commit_current': COMMIT,
        'source_manifest_sha256': 'b'*64,
        'normative_requirements_approved': False,
        'full_normative_coverage_verified': False,
        'dwm_implementation_coverage_verified': False,
        'saxon_lxml_semantic_parity_verified': False,
        'source_files_modified': False,
        'versions': {v: {'requirements_indexed': sum(r['noark_version'] == v for r in rows)}
                     for v in ('3.1', '4.0', '5.0')},
        'candidate_rows': rows,
        'qa_issues': [{'severity': 'FEIL', 'kind': 'source_duplicate',
                       'noark_version': '5.0'},
                      {'severity': 'WARNING', 'kind': 'text_diff',
                       'noark_version': '3.1'}],
    }


class A10Coverage(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.dwm = self.tmp / 'data-workflow-manager'
        self.dwm.mkdir()
        self.a9file = self.tmp / 'a9' / 'noark5-a9-requirements.json'
        self.a9file.parent.mkdir()
        self._create_inventory()
        self.rows = [
            clause('3.1', '5.1.5', 'I et arkivuttrekk skal feltet systemID være entydig.'),
            clause('4.0', '5.2.3', 'M050 arkivstatus skal kunne rapporteres i arkivstruktur.xml'),
            clause('5.0', '2.1.4', 'Mappe skal bruke mappeID; arkivstruktur.xml er nevnt'),
            clause('5.0', '2.1.5', 'Teknisk funksjon kan ikke vurderes fra uttrekk'),
            clause('3.1', '6.1.3', 'Kildekrav utgår', suffix='retired',severity='NOTE'),
        ]
        self.a9 = a9_report(self.rows)
        self.a9file.write_text(json.dumps(self.a9),encoding='utf8')

    def put(self, relative: str, content: str):
        path = self.dwm / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def _create_inventory(self):
        self.put('config/noark5/tests/xpath_catalog_2026_05_26.json', json.dumps({
            'tests': [
                {'test_id': 'kdrs.c01', 'legacy': {'job_id': 'C01'},
                 'name': 'Arkiv og arkivstatus', 'source_xml': 'arkivstruktur.xml',
                 'noark_versions': ['3.1', '4.0', '5.0'],
                 'execution': {'kind': 'metrics', 'metrics': [
                     {'expression': 'count(//arkiv[systemID])'},
                     {'select': '//arkiv/arkivstatus'}]},
                 'standard_value_checks': [{'value_set_id': 'M050_arkivstatus', 'versions':['3.1','4.0','5.0']}]},
                {'test_id': 'kdrs.c02', 'legacy': {'job_id': 'C02'},
                 'name': 'MappeID', 'source_xml': 'arkivstruktur.xml',
                 'noark_versions': ['4.0', '5.0'],
                 'execution': {'kind': 'metrics', 'metrics': [
                     {'expression': 'count(//mappe[mappeID])'}]}},
                {'test_id': 'kdrs.u1', 'legacy': {'job_id': 'U01'},
                 'name': 'Utvidet test', 'source_xml': 'arkivstruktur.xml',
                 'noark_versions': ['3.1'], 'execution': {'kind': 'special_kind'}},
            ]
        }))
        self.put('noark5_workflow/analysis/xpath_test_engine.py',
                 'def _special(kind):\n'
                 '    if kind == "special_kind":\n'
                 '        return True\n'
                 '    return False\n')
        self.put('app/noark5_xsd_full_xml_v021_a8.py',
                 'XML_TO_SCHEMA = {"arkivstruktur.xml": "arkivstruktur.xsd", '
                 '"endringslogg.xml": "endringslogg.xsd", '
                 '"loependeJournal.xml": "loependeJournal.xsd", '
                 '"offentligJournal.xml": "offentligJournal.xsd", '
                 '"arkivuttrekk.xml": None}\n'
                 'def validate_extraction(*args, **kwargs):\n'
                 '    return {}\n')
        names = ['arkivstruktur.xsd','endringslogg.xsd','loependeJournal.xsd',
                 'offentligJournal.xsd','metadatakatalog.xsd']
        signatures = [{'version': v, 'filename': n, 'sha256': 'a'*64}
                      for v in ('3.1','4.0','5.0') for n in names]
        self.put('config/noark5/standards/noark5_xsd_signatures_v0114_a5.json',
                 json.dumps({'signatures': signatures}))
        self.put('config/noark5/standards/requirements/index.json',
                 json.dumps({'versions': {v:f'config/noark5/standards/requirements/{v}.json'
                                         for v in ('3.1','4.0','5.0')}}))
        for v in ('3.1','4.0','5.0'):
            self.put(f'config/noark5/standards/requirements/{v}.json',json.dumps({
                'noark_version': v,
                'requirements': ([{'requirement_id': 'local.mappeID',
                                   'xml_field_name': 'mappeID',
                                   'extract_validation': {'implemented_as_dwm_control': False}}]
                                 if v == '5.0' else [])}))

    def test_inventory_tracks_real_catalogue_and_technical_xsd_separately(self):
        controls, refs, issues, hashes = inventory_controls(self.dwm)
        self.assertEqual(len(controls), 18)
        self.assertEqual(Counter(c['control_type'] for c in controls),
                         {'xpath_catalog_test': 3, 'technical_xsd_validator': 15})
        self.assertEqual(len(refs), 1)
        self.assertTrue(refs[0]['reference_only'])
        x = next(c for c in controls if c['control_id']=='kdrs.u1')
        self.assertTrue(x['dispatch_identified_by_ast'])
        self.assertFalse(x['runtime_semantics_verified'])
        self.assertFalse(x['normative_requirement_coverage_verified'])
        self.assertTrue(hashes['config/noark5/tests/xpath_catalog_2026_05_26.json'])
        self.assertFalse(issues)
        a = next(c for c in controls if c['control_id']=='xsd.v3.1.arkivuttrekk.xml')
        self.assertIsNone(a['schema_file'])
        self.assertTrue(a['addml_supplied_by_extract_not_pinned'])
        self.assertFalse(a['xsd_signature_pinned'])

    def test_version_scoped_literal_links_never_verified(self):
        report = build_coverage(self.a9, self.dwm, a9_sha256='0'*64)
        self.assertEqual(report['report_type'], REPORT_TYPE)
        self.assertEqual(len(report['coverage_matrix']), 5)
        self.assertFalse(report['normative_requirements_approved'])
        self.assertFalse(report['dwm_implementation_coverage_verified'])
        self.assertFalse(report['archive_extract_conformance_verified'])
        self.assertEqual(report['summary']['source_qa_issue_counts'],
                         {'FEIL':1,'WARNING':1})
        first = report['coverage_matrix'][0]
        self.assertEqual(first['coverage_state'], 'IKKE_VERIFISERT')
        self.assertEqual([c['control_id'] for c in first['technical_control_candidates']], ['kdrs.c01'])
        self.assertEqual(first['technical_control_candidates'][0]['literal_witness'], 'systemID')
        self.assertFalse(first['implementation_verified'])
        second = report['coverage_matrix'][1]
        matches = {c['control_id']:c for c in second['technical_control_candidates']}
        self.assertIn('kdrs.c01', matches)
        self.assertEqual(matches['kdrs.c01']['evidence_type'], 'explicit_metadata_id_vs_value_set')
        self.assertIn('xsd.v4.0.arkivstruktur.xml', matches)
        self.assertNotIn('xsd.v3.1.arkivstruktur.xml', matches)
        third = report['coverage_matrix'][2]
        self.assertIn('kdrs.c02', [c['control_id'] for c in third['technical_control_candidates']])
        self.assertIn('local.mappeID', [x['requirement_id'] for x in third['local_requirement_registry_references']])
        self.assertFalse(third['local_requirement_registry_references'][0]['implemented_as_dwm_control'])
        self.assertEqual(report['coverage_matrix'][3]['evidence_state'], 'INGEN_DOKUMENTERT_KOBLING')
        self.assertEqual(report['coverage_matrix'][4]['source_qa_severity'], 'NOTE')
        self.assertTrue(all(row['coverage_state']=='IKKE_VERIFISERT' for row in report['coverage_matrix']))

    def test_explicit_metadata_tokens_and_general_terms(self):
        self.assertIn('systemID',_source_field_tokens(('count(//arkiv/systemID)',)))
        self.assertIn('arkivstatus',_source_field_tokens(('//arkiv/arkivstatus',)))
        self.assertNotIn('arkiv',_source_field_tokens(('//arkiv/klasse/mappe',)))
        self.assertNotIn('string',_source_field_tokens(('string(//arkiv)',)))
        self.assertNotIn('fakeID', _source_field_tokens(('//mappe[@type="fakeID"]',)))

    def test_filters_include_versions_qa_and_missing_links(self):
        report = build_coverage(self.a9, self.dwm)
        self.assertEqual(len(filter_coverage_rows(report,version='5.0')), 2)
        self.assertEqual(len(filter_coverage_rows(report, source_qa='NOTE')), 1)
        self.assertEqual(len(filter_coverage_rows(report,evidence='INGEN_DOKUMENTERT_KOBLING')), 2)
        self.assertEqual(len(filter_coverage_rows(report,query='kdrs.c02')), 1)
        self.assertEqual(len(filter_coverage_rows(report,coverage='IMPLEMENTERT_VERIFISERT')), 0)
        for keyword in ('WRONG',):
            with self.assertRaises(ValueError):
                filter_coverage_rows(report,source_qa=keyword)
            with self.assertRaises(ValueError):
                filter_coverage_rows(report,coverage=keyword)

    def test_wrong_a9_format_and_provenance_fail_closed(self):
        cases = [
            ('report_type','bogus'),
            ('normative_requirements_approved',True),
            ('dwm_implementation_coverage_verified',True),
            ('source_files_modified',True),
            ('source_checkout_commit_current','unknown'),
        ]
        for key, value in cases:
            a9 = {**self.a9, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_coverage(a9, self.dwm)
        duplicate = {**self.a9,'candidate_rows':self.rows + [self.rows[0]]}
        with self.assertRaisesRegex(ValueError,'duplisert'):
            build_coverage(duplicate,self.dwm)
        inconsistent = {**self.a9, 'versions': {
            **self.a9['versions'], '3.1': {'requirements_indexed': 999}}}
        with self.assertRaisesRegex(ValueError, 'kravtall'):
            build_coverage(inconsistent, self.dwm)
        altered = dict(self.rows[0], candidate_id='5.0:5.1.5:1')
        invalid = {**self.a9, 'candidate_rows': [altered] + self.rows[1:]}
        with self.assertRaisesRegex(ValueError, 'ID'):
            build_coverage(invalid, self.dwm)
        no_hash = dict(self.rows[0], source_sha256=None)
        invalid = {**self.a9, 'candidate_rows': [no_hash] + self.rows[1:]}
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            build_coverage(invalid, self.dwm)

    def test_missing_engine_reports_unverified_not_dispatch(self):
        (self.dwm/'noark5_workflow/analysis/xpath_test_engine.py').unlink()
        report = build_coverage(self.a9,self.dwm)
        self.assertTrue(any(x['kind']=='xpath_engine_source_unavailable'
                            for x in report['control_inventory_issues']))
        x = next(c for c in report['control_inventory'] if c['control_id']=='kdrs.u1')
        self.assertIsNone(x['dispatch_identified_by_ast'])
        self.assertEqual(report['summary']['implementation_verified'],0)

    def test_missing_catalogue_rejected_not_empty_coverage(self):
        (self.dwm/'config/noark5/tests/xpath_catalog_2026_05_26.json').unlink()
        with self.assertRaisesRegex(ValueError,'katalogen'):
            build_coverage(self.a9,self.dwm)

    def test_local_registry_is_reference_not_executed_test(self):
        report=build_coverage(self.a9,self.dwm)
        self.assertEqual(report['summary']['local_requirement_registry_references'],1)
        self.assertEqual(report['summary']['xpath_catalog_controls'],3)
        self.assertEqual(report['summary']['xsd_technical_controls'],15)
        self.assertNotIn('local.mappeID',{c['control_id'] for c in report['control_inventory']})

    def test_writer_protects_repos_and_a9_and_csv(self):
        report = build_coverage(self.a9,self.dwm)
        with self.assertRaises(ValueError):
            write_reports(report,self.dwm/'docs'/'generated',dwm_root=self.dwm)
        with self.assertRaises(ValueError):
            write_reports(report,self.a9file.parent,dwm_root=self.dwm,a9_report_path=self.a9file)
        out=self.tmp/'a10_results'
        paths=write_reports(report,out,dwm_root=self.dwm,a9_report_path=self.a9file)
        self.assertEqual([x.name for x in paths],list(REPORT_NAMES))
        self.assertEqual(json.loads(paths[0].read_text())['report_type'],REPORT_TYPE)
        self.assertEqual(len(paths[1].read_text(encoding='utf-8').splitlines()),6)
        self.assertIn('Ingen verifisert normativ',paths[-1].read_text(encoding='utf8'))
        with self.assertRaises(FileExistsError):
            write_reports(report,out,dwm_root=self.dwm)
        self.assertIn("'=HYPERLINK",_csv_text([{'x':'=HYPERLINK(1)'}],('x',)))

    def test_gui_integration_and_packaging_version(self):
        root=Path(__file__).resolve().parents[1]
        gui=(root/'gui_qt/noark5_xpath_audit_v021_a1.py').read_text(encoding='utf-8')
        for needle in ('Krav–kontroll a10','_choose_a10_report', 'filter_coverage_rows',
                       'self.a10_table', 'self.a10_evidence', 'self.a10_control_table'):
            self.assertIn(needle,gui)
        from version import VERSION
        self.assertRegex(VERSION, r'^0\.2\.1-a[0-9]+$')
        self.assertIn('version = "' + VERSION.replace('-a', 'a') + '"',
                      (root/'pyproject.toml').read_text(encoding='utf-8'))

    def test_summary_transparency(self):
        report=build_coverage(self.a9,self.dwm)
        summary=markdown_summary(report)
        self.assertIn('Ingen verifisert normativ',summary)
        self.assertIn('Saxon/lxml',summary)
        self.assertIn('ingen dokumentert kobling',summary.casefold())

if __name__=='__main__':
    from unittest import main
    main()
