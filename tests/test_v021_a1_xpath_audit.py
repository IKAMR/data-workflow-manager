"""v0.2.1-a1: KDRS identity, version scope and read-only XPath evidence GUI."""
from __future__ import annotations

import ast
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.noark5_xpath_audit_v021_a1 import (
    VERSIONS, _all_paths, _read_json, catalogue_summary,
    classify_execution, filter_work_rows, legacy_job_audit, legacy_source_expression, load_rows,
    project_work_rows, schema_inventory, schema_lexical_coverage,
    xpath_syntax_audit,
)


def make_test(test_id='kdrs.c01', legacy='C01', *, role='', status='active',
              versions=None, paths=None):
    paths = paths or [
        {'id': 'archives', 'type': 'xpath', 'expression': 'count(//arkiv)'},
        {'id': 'names', 'type': 'rows', 'select': '//arkiv',
         'fields': {'title': 'string(tittel)', 'id': 'string(systemID)'}},
    ]
    return {
        'test_id': test_id, 'legacy': {'job_id': legacy, 'test_point': 'N5.04'},
        'name': 'Arkiv og arkivskaper', 'source_xml': 'arkivstruktur.xml',
        'scope': 'source_document', 'status': status,
        'noark_versions': versions or list(VERSIONS),
        'version_basis': 'master_query_subtype_needs_qa',
        'execution': {'kind': 'metrics', 'metrics': paths},
        'standard_value_checks': [{'value_set_id': 'M050_arkivstatus'}],
        'lifecycle': {'role': role},
    }


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'dwm'
        self.root.mkdir()
        target = self.root / 'config/noark5/tests'
        target.mkdir(parents=True)
        model = {
            'tests': [make_test(),
                      make_test('kdrs.u01', 'U01', role='development_regression_reference'),
                      make_test('kdrs.u02', 'U02', role='development_regression_reference'),
                      make_test('kdrs.dwm.add', 'DWM-AU01')],
        }
        (target / 'xpath_catalog_2026_05_26.json').write_text(
            json.dumps(model), encoding='utf-8')
        self.work = self.root / 'work'
        self.work.mkdir()
        self.rows = load_rows(self.root)

    def refs(self, *, include_u2=True):
        folder = self.root / 'docs/reference/kdrs-query'
        folder.mkdir(parents=True)
        sources = {
            'xml-queries_noark5_2026-05-26.txt': 'C01\nU01\nU02',
            'xml-queries_noark5_2026-05-26_U1.txt': 'U01',
            'xml-queries_noark5_2026-05-26_U2.txt': 'U02' if include_u2 else 'H01',
        }
        for file, ids in sources.items():
            (folder / file).write_text(''.join('job_id=' + s + '\n' for s in ids.splitlines()),
                                       encoding='utf-8')

    def stored(self, *, statuses=None, values=None, file_override=None):
        dest = self.work / 'noark5_tests/xpath/run-0001'
        (dest / 'results').mkdir(parents=True)
        statuses = statuses or {'kdrs.c01': 'ok'}
        values = values or {}
        items = []
        for test_id, status in statuses.items():
            name = 'results/' + test_id.replace('.', '_') + '.json'
            items.append({'test_id': test_id, 'status': status, 'file': file_override or name})
            (dest / name).write_text(json.dumps({
                'test_id': test_id, 'status': status, 'values': values.get(test_id, {}),
                'missing_sources': ['offentligJournal.xml'], 'error': 'XPathEvalError: bad()',
            }), encoding='utf-8')
        index = dest / 'index.json'
        index.write_text(json.dumps({'tests': items}), encoding='utf-8')
        artifact = SimpleNamespace(category='XPath / Noark 5', title='index.json',
                                   modified_at=1,
                                   relative_path='noark5_tests/xpath/run-0001/index.json')
        shot = SimpleNamespace(job=SimpleNamespace(work=self.work, job_id='JOB-001',
                                name='test'), results=SimpleNamespace(artifacts=(artifact,)))
        return shot


class CatalogueTests(Fixture):
    def test_catalogue_and_xpath_fields(self):
        self.assertEqual(len(self.rows), 4)
        self.assertEqual(len(self.rows[0].paths), 4)
        self.assertIn('count(//arkiv)', self.rows[0].paths)
        self.assertIn('string(systemID)', self.rows[0].paths)
        self.assertEqual(catalogue_summary(self.rows)['regression_reference'], 2)

    def test_detects_duplicate_source_ids_without_confusing_source_with_catalogue(self):
        self.refs()
        result = legacy_job_audit(self.root)
        self.assertEqual(result['source_job_occurrences'], 5)
        self.assertEqual(result['source_unique_job_ids'], 3)
        self.assertEqual(result['duplicate_source_ids'], ['U01', 'U02'])
        self.assertEqual(result['dwm_only_ids'], ['DWM-AU01'])
        self.assertEqual(result['not_in_dwm_catalog'], [])
        self.assertTrue(result['verified_id_parity'])
        self.assertFalse(result['expression_parity_verified'])

    def test_original_kdrs_saxon_expression_available_including_u2(self):
        self.refs()
        path = self.root / 'docs/reference/kdrs-query/xml-queries_noark5_2026-05-26_U2.txt'
        path.write_text('[XML_QUERY]\njob_id=U02\n#START#\ncount(//arkivdel)\n#STOP#\n',
                        encoding='utf-8')
        original = legacy_source_expression(self.rows[2], self.root)
        self.assertEqual(original, 'count(//arkivdel)')
        self.assertEqual(legacy_source_expression(self.rows[3], self.root),
                         'DWM-tillegg; finnes ikke som egen KDRS Query-jobb.')

    def test_original_expression_is_not_inferred_from_incomplete_kdrs_file(self):
        self.refs()
        path = self.root / 'docs/reference/kdrs-query/xml-queries_noark5_2026-05-26.txt'
        path.write_text('[XML_QUERY]\njob_id=C01\n#START#\ncount(//arkiv)\n',
                        encoding='utf-8')
        self.assertIn('ikke et komplett', legacy_source_expression(self.rows[0], self.root))

    def test_missing_legacy_id_does_not_count_as_covered(self):
        self.refs(include_u2=False)
        result = legacy_job_audit(self.root)
        self.assertFalse(result['verified_id_parity'])
        self.assertEqual(result['not_in_dwm_catalog'], ['H01'])

    def test_missing_reference_files_never_claims_verification(self):
        result = legacy_job_audit(self.root)
        self.assertFalse(result['verified_id_parity'])
        self.assertEqual(len(result['source_files_missing']), 3)

    def test_duplicate_catalogue_id_rejected(self):
        catalog = self.root / 'config/noark5/tests/xpath_catalog_2026_05_26.json'
        data = json.loads(catalog.read_text(encoding='utf-8'))
        data['tests'].append(data['tests'][0])
        catalog.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            load_rows(self.root)

    def test_xpath_compiler_reports_invalid_selector_without_running_it(self):
        audit = xpath_syntax_audit(self.rows)
        if audit['status'] == 'lxml_missing':
            self.skipTest('lxml not installed')
        self.assertEqual(audit['invalid'], [])
        self.assertEqual(audit['compiled'], 16)

    def test_malformed_xpath_is_not_silently_accepted(self):
        bad = make_test(paths=[{'id': 'bad', 'type': 'xpath',
                                'expression': 'count(//arkiv[)'}])
        row = self.rows[0].__class__(**{**vars(self.rows[0]),
                                       'paths': _all_paths(bad['execution'])})
        result = xpath_syntax_audit([row])
        if result['status'] == 'lxml_missing':
            self.skipTest('lxml not installed')
        self.assertEqual(len(result['invalid']), 1)


class WorkProjectionTests(Fixture):
    def test_missing_execution_is_not_ok(self):
        projected = project_work_rows(self.rows)
        self.assertEqual(projected[0]['severity'], 'IKKE_KJORT')
        self.assertEqual(projected[1]['severity'], 'REGRESJON')

    def test_recorded_ok_means_executed_not_accepted(self):
        shot = self.stored()
        projected = project_work_rows(self.rows, shot)
        self.assertEqual(projected[0]['severity'], 'UTFORT')
        self.assertIn('ikke godkjent', projected[0]['reasons'][0])
        self.assertEqual(projected[1]['severity'], 'REGRESJON')

    def test_version_specific_warning_only_when_explicitly_selected(self):
        values = {'kdrs.c01': {
            '_standard_values': {'archive_status': {'versions': {
                '5.0': {'status': 'additional_observed_values'},
                '4.0': {'status': 'all_observed_values_standard'},
            }}}
        }}
        shot = self.stored(values=values)
        self.assertEqual(project_work_rows(self.rows, shot, version='5.0')[0]['severity'], 'WARNING')
        self.assertEqual(project_work_rows(self.rows, shot, version='4.0')[0]['severity'], 'UTFORT')
        self.assertEqual(project_work_rows(self.rows, shot, version='')[0]['severity'], 'UTFORT')

    def test_no_values_is_note_not_xml_error(self):
        shot = self.stored(values={'kdrs.c01': {'_standard_values': {
            'x': {'versions': {'3.1': {'status': 'no_observed_values'}}}}}})
        self.assertEqual(project_work_rows(self.rows, shot, version='3.1')[0]['severity'], 'NOTE')

    def test_true_execution_error_and_missing_source_are_distinct(self):
        shot = self.stored(statuses={'kdrs.c01': 'error', 'kdrs.u01': 'source_missing'})
        items = project_work_rows(self.rows, shot)
        self.assertEqual(items[0]['severity'], 'FEIL')
        self.assertEqual(items[1]['severity'], 'MANGLER')

    def test_mismatched_reconciliation_is_warning(self):
        shot = self.stored(values={'kdrs.c01': {'_reconciliation_summary': {'mismatches': 2}}})
        self.assertEqual(project_work_rows(self.rows, shot)[0]['severity'], 'WARNING')

    def test_path_escape_in_stored_index_is_rejected(self):
        shot = self.stored(file_override='../outside.json')
        result = project_work_rows(self.rows, shot)[0]
        self.assertEqual(result['severity'], 'UKJENT')
        self.assertIsNone(result['result'])

    def test_file_with_wrong_test_id_is_rejected(self):
        shot = self.stored()
        path = self.work / 'noark5_tests/xpath/run-0001/results/kdrs_c01.json'
        path.write_text(json.dumps({'test_id': 'other', 'status': 'ok'}), encoding='utf-8')
        self.assertEqual(project_work_rows(self.rows, shot)[0]['severity'], 'UKJENT')

    def test_search_severity_version_and_scope(self):
        projected = project_work_rows(self.rows)
        only = filter_work_rows(projected, source='U1/U2')
        self.assertEqual([x['row'].legacy_id for x in only], ['U01', 'U02'])
        self.assertEqual(len(filter_work_rows(projected, severity='REGRESJON')), 2)
        self.assertEqual(len(filter_work_rows(projected, version='5.0', query='systemID')), 4)
        self.assertEqual(len(filter_work_rows(projected, query='M050_arkivstatus')), 4)
        self.assertEqual(len(filter_work_rows(projected, query='nonsense')), 0)

    def test_bad_version_is_rejected(self):
        with self.assertRaises(ValueError):
            project_work_rows(self.rows, version='6.0')

    def test_safe_json_does_not_follow_escape(self):
        outside = self.root / 'outside.json'
        outside.write_text('{}', encoding='utf-8')
        self.assertIsNone(_read_json(outside, within=self.work))


class SchemaSourceTests(Fixture):
    def test_local_xsd_inventory_and_lexical_reference_not_normative(self):
        schemas = self.root / 'schemas'
        for version, tag in [('3.1', 'sakspart'), ('4.0', 'sakspart'), ('5.0', 'part')]:
            target = schemas / ('v' + version) / 'schemas'
            target.mkdir(parents=True)
            (target / 'arkivstruktur.xsd').write_text(
                '<?xml version="1.0"?><xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                f'version="{version}"><xs:element name="arkiv"/>'
                f'<xs:element name="{tag}"/></xs:schema>', encoding='utf-8')
        inventory = schema_inventory(schemas)
        self.assertEqual(sum(len(v) for v in inventory['versions'].values()), 3)
        self.assertEqual(len(inventory['missing']), 12)
        self.assertEqual(inventory['versions']['5.0']['arkivstruktur.xsd']['elements'], 2)
        self.assertEqual(len(inventory['versions']['5.0']['arkivstruktur.xsd']['sha256']), 64)
        coverage = schema_lexical_coverage(inventory, self.rows)
        self.assertEqual(coverage['5.0']['arkivstruktur.xsd']['mentioned_in_declarative_xpaths'], 1)
        self.assertIn('part', coverage['5.0']['arkivstruktur.xsd']['not_mentioned_in_declarative_xpaths'])

    def test_does_not_consider_bad_xsd_successfully_parsed(self):
        source = self.root / 'v3.1/schemas'
        source.mkdir(parents=True)
        (source / 'arkivstruktur.xsd').write_text('<xml>', encoding='utf-8')
        result = schema_inventory(self.root)
        self.assertEqual(len(result['errors']), 1)
        self.assertNotIn('arkivstruktur.xsd', result['versions']['3.1'])



class RealRepositoryInventoryTests(unittest.TestCase):
    """Use the actual 2026 sources when the full repository is available."""

    @unittest.skipUnless((ROOT / 'config/noark5/tests/xpath_catalog_2026_05_26.json').is_file(),
                         'full DWM catalogue not present in this partial test workspace')
    def test_real_standard_u1_u2_ids_and_declarative_lxml_syntax(self):
        rows = load_rows(ROOT)
        self.assertEqual(len(rows), 60)
        audit = legacy_job_audit(ROOT)
        self.assertTrue(audit['verified_id_parity'], audit)
        self.assertEqual(audit['source_counts'], {'Standard': 59, 'U1': 1, 'U2': 1})
        self.assertEqual(audit['duplicate_source_ids'], ['U01', 'U02'])
        self.assertEqual(audit['dwm_only_ids'], ['DWM-AU01'])
        self.assertFalse(audit['expression_parity_verified'])
        syntax = xpath_syntax_audit(rows)
        if syntax['status'] == 'lxml_missing':
            self.skipTest('lxml not installed')
        self.assertGreater(syntax['attempted'], 150)
        self.assertEqual(syntax['invalid'], [], syntax['invalid'])



class GUIContractTests(unittest.TestCase):
    def test_new_button_installed_after_existing_a6_navigation(self):
        text = (ROOT / 'gui_qt/main_v020_a6.py').read_text(encoding='utf-8')
        ast.parse(text)
        self.assertLess(text.index('install_compact_result_navigation(viewer)'),
                        text.index('install_xpath_catalog_link(viewer)'))
        self.assertIn('super()._a12_open_result_center(', text)

    def test_changing_version_does_not_read_work_again(self):
        source = (ROOT / 'gui_qt/noark5_xpath_audit_v021_a1.py').read_text(encoding='utf-8')
        self.assertIn('self.version.currentIndexChanged.connect(self._apply_version)', source)
        tree = ast.parse(source)
        dialog = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == 'XPathCoverageDialog')
        method = next(node for node in dialog.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_apply_version')
        text = ast.get_source_segment(source, method)
        self.assertIn('classify_execution(', text)
        self.assertNotIn('project_work_rows(', text)

    def test_gui_does_not_start_xpath_or_change_originals(self):
        source = (ROOT / 'gui_qt/noark5_xpath_audit_v021_a1.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('install_xpath_catalog_link(viewer)', source)
        self.assertIn('Vis alle XPath-kontroller...', source)
        self.assertIn('project_work_rows', source)
        self.assertNotIn('run_catalog(', source)
        self.assertNotIn('write_text(', source)
        self.assertNotIn('copytree(', source)

    def test_version_and_distribution_match(self):
        import re
        from version import VERSION
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', "0.2.1", 1)
        project = (ROOT / 'pyproject.toml').read_text(encoding='utf8')
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', project)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), VERSION.replace('-a', 'a'))


if __name__ == '__main__':
    unittest.main()
