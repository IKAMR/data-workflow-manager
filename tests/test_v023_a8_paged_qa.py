"""v0.2.3-a8: paged large-Arkade KS, fail-closed publication and provenance.

The lightweight fake event parser tests the A8 integration without a native
ijson wheel. In installed DWM, the real ijson and A260 parser are used.
"""
from __future__ import annotations

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from noark5_workflow.reporting.qa_paged_v023_a8 import (
    QaIndexError, build_arkade_index, page_arkade_index,
)


def _isolated_module(public_name: str, suffix: str):
    """Load a test-only copy. Never reload a production module in sys.modules.

    The old a8 test used importlib.reload on shared QA modules with fake
    dependencies. This permanently changed references held by earlier suites
    and broke unrelated Work/KS tests during full unittest discovery.
    """
    file = Path(__file__).resolve().parents[1].joinpath(
        *public_name.split('.')).with_suffix('.py')
    test_name = public_name.rpartition('.')[0] + '._a8_test_' + suffix
    spec = spec_from_file_location(test_name, file)
    if spec is None or spec.loader is None:
        raise AssertionError('Cannot load isolated QA test module: ' + public_name)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def to_events(obj, prefix=''):
    if isinstance(obj, dict):
        yield prefix, 'start_map', None
        for key, value in obj.items():
            yield prefix, 'map_key', key
            yield from to_events(value, prefix + '.' + key if prefix else key)
        yield prefix, 'end_map', None
    elif isinstance(obj, list):
        yield prefix, 'start_array', None
        for item in obj:
            yield from to_events(item, prefix + '.item' if prefix else 'item')
        yield prefix, 'end_array', None
    else:
        ev = 'null' if obj is None else 'boolean' if type(obj) is bool else (
            'number' if isinstance(obj, (int, float)) else 'string')
        yield prefix, ev, obj


def mock_ijson_parse(stream):
    yield from to_events(json.load(stream))


def mock_findings(events, *, source_ref, source_sha):
    test_id = ''
    issue = {}
    seq = 0
    for prefix, event, value in events:
        if prefix == 'tests.item.test_id' and event == 'string':
            test_id = value
        elif prefix == 'tests.item.results.item' and event == 'start_map':
            issue = {}
        elif prefix in ('tests.item.results.item.result_type',
                        'tests.item.results.item.message') and event == 'string':
            issue[prefix.rsplit('.', 1)[-1]] = value
        elif prefix == 'tests.item.results.item' and event == 'end_map':
            if issue.get('result_type', '').lower() in ('error', 'warning'):
                seq += 1
                severity = issue['result_type'].upper()
                yield {'source': 'Arkade 5', 'test_id': test_id,
                       'severity': severity, 'message': issue['message'],
                       'context': '', 'file': '', 'lines': [],
                       'source_ref': source_ref, 'requires_review': True,
                       'finding_key': digest((source_sha + str(seq)).encode()),
                       'finding_uid': digest(('issue-' + str(seq)).encode())}
            issue = {}


class A8IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name) / 'work'
        (self.work / 'noark5_evidence').mkdir(parents=True)
        self.base = self.work / 'external_evidence/arkade5/one'
        (self.base / 'normalized').mkdir(parents=True)
        (self.base / 'source').mkdir(parents=True)
        original = b'{"Summary":{},"TestsResults":[]}'
        (self.base / 'source/arkade.json').write_bytes(original)
        self.original_sha = digest(original)
        self.relative = 'external_evidence/arkade5/one/normalized/arkade5_results.json'
        self.source = self.work / self.relative
        self.mocks = patch.dict(sys.modules, {
            'ijson': types.SimpleNamespace(parse=mock_ijson_parse, JSONError=ValueError),
            'noark5_workflow.reporting.qa_a260_v023_a6': types.SimpleNamespace(
                iter_arkade_findings=mock_findings),
        })
        self.mocks.start()
        self.addCleanup(self.mocks.stop)

    def write(self, errors=301, warnings=2):
        value = {'format_version': 2, 'evidence_type': 'external_validation_report',
                 'source_system': 'Arkade 5', 'source': {'sha256': self.original_sha},
                 'summary': {'number_of_tests_run': 2, 'system_name': 'Synthetic'},
                 'tests': [
                    {'test_id': 'N5.15', 'source_status': 'error', 'number_of_errors': errors,
                     'results': [{'result_type': 'Error', 'message': f'failure-{i}'}
                                 for i in range(errors)]},
                    {'test_id': 'N5.22', 'source_status': 'warning', 'number_of_errors': 0,
                     'results': [{'result_type': 'Warning', 'message': f'warn-{i}'}
                                 for i in range(warnings)]}]}
        self.source.write_text(json.dumps(value), encoding='utf-8')
        return value

    def test_301_plus_warnings_fully_indexed_with_bounded_preview(self):
        self.write()
        info = build_arkade_index(self.work, self.relative,
                                  original_sha256=self.original_sha,
                                  job_uid='stable-001')
        self.assertTrue(info['complete'])
        self.assertEqual(info['finding_count'], 303)
        self.assertEqual(info['test_count'], 2)
        self.assertEqual(info['severity_counts'], {'ERROR': 301, 'WARNING': 2})
        self.assertEqual(len(info['preview']), 250)
        self.assertFalse(info['technical_validation_verified'])
        page = page_arkade_index(self.work, info, page=1, page_size=200)
        self.assertEqual(len(page['rows']), 103)
        self.assertEqual(page['rows'][-1]['message'], 'warn-1')
        filtered = page_arkade_index(self.work, info, severity='WARNING', test_id='N5.22')
        self.assertEqual(filtered['total'], 2)
        self.assertEqual([r['message'] for r in filtered['rows']], ['warn-0', 'warn-1'])

    def test_more_than_1000_does_not_truncate_or_fail(self):
        self.write(1250, 0)
        info = build_arkade_index(self.work, self.relative,
                                  original_sha256=self.original_sha, job_uid='stable-002')
        self.assertEqual(info['finding_count'], 1250)
        tail = page_arkade_index(self.work, info, page=6, page_size=200)
        self.assertEqual(len(tail['rows']), 50)
        self.assertEqual(tail['rows'][-1]['message'], 'failure-1249')

    def test_empty_and_exactly_300_are_indexed_without_missing_rows(self):
        self.write(0, 0)
        empty = build_arkade_index(self.work, self.relative,
                                   original_sha256=self.original_sha, job_uid='stable-zero')
        self.assertEqual(empty['finding_count'], 0)
        self.assertEqual(empty['preview'], [])
        self.assertEqual(page_arkade_index(self.work, empty)['total'], 0)
        self.write(300, 0)
        found = build_arkade_index(self.work, self.relative,
                                   original_sha256=self.original_sha, job_uid='stable-300')
        self.assertEqual(found['finding_count'], 300)
        self.assertEqual(len(found['preview']), 250)
        self.assertEqual(page_arkade_index(self.work, found, page=1,
                                            page_size=200)['total'], 300)

    def test_cached_index_is_reused_and_mutations_rejected(self):
        self.write(301, 0)
        first = build_arkade_index(self.work, self.relative,
                                   original_sha256=self.original_sha, job_uid='stable-003')
        second = build_arkade_index(self.work, self.relative,
                                    original_sha256=self.original_sha, job_uid='stable-003')
        self.assertEqual(second['index_sha256'], first['index_sha256'])
        self.assertEqual(second['finding_count'], 301)
        self.source.write_text(self.source.read_text() + ' ', encoding='utf-8')
        with self.assertRaisesRegex(QaIndexError, 'endret siden'):
            page_arkade_index(self.work, first)

    def test_preserved_original_must_stay_byte_identical(self):
        self.write(302, 0)
        original_rel = 'external_evidence/arkade5/one/source/arkade.json'
        index = build_arkade_index(self.work, self.relative,
                                   original_sha256=self.original_sha,
                                   preserved_relative=original_rel,
                                   job_uid='stable-original')
        self.assertEqual(page_arkade_index(self.work, index)['total'], 302)
        (self.work / original_rel).write_bytes(b'TAMPER')
        with self.assertRaisesRegex(QaIndexError, 'original er endret'):
            page_arkade_index(self.work, index)
        with self.assertRaisesRegex(QaIndexError, 'original stemmer ikke'):
            build_arkade_index(self.work, self.relative,
                               original_sha256=self.original_sha,
                               preserved_relative=original_rel,
                               job_uid='stable-original')

    def test_wrong_original_hash_and_incomplete_source_fail_closed(self):
        self.write(301, 0)
        with self.assertRaisesRegex(QaIndexError, 'ulik SHA-256'):
            build_arkade_index(self.work, self.relative,
                               original_sha256='a' * 64, job_uid='stable-004')
        self.assertFalse(any((self.work / 'noark5_evidence/qa_index_v023_a8').glob('*.json')))
        self.source.write_text('{"source_system": "Arkade 5", "tests": [', encoding='utf-8')
        with self.assertRaises((ValueError, QaIndexError)):
            build_arkade_index(self.work, self.relative,
                               original_sha256=self.original_sha, job_uid='stable-004')

    def test_tampered_database_and_unsafe_page_are_rejected(self):
        self.write(12, 0)
        info = build_arkade_index(self.work, self.relative,
                                  original_sha256=self.original_sha, job_uid='stable-005')
        with self.assertRaises(QaIndexError):
            page_arkade_index(self.work, info, page=-1)
        with self.assertRaises(QaIndexError):
            page_arkade_index(self.work, info, page_size=1001)
        db = self.work / info['index_relative_path']
        with db.open('ab') as f:
            f.write(b'TAMPERED')
        with self.assertRaisesRegex(QaIndexError, 'SHA-256-avvik'):
            page_arkade_index(self.work, info)

    def test_a8_existing_small_work_adapter_and_301_fallback(self):
        """The ordinary Work adapter keeps small evidence in memory as before."""
        self.write(1, 1)
        decision = types.ModuleType('noark5_workflow.reporting.qa_decision_v021_a12')
        decision.ReportInputError = type('ReportInputError', (ValueError,), {})
        def _rel(root, relative):
            return root / relative
        def _json(path, limit=None):
            return json.loads(Path(path).read_text(encoding='utf-8'))
        def _source(root, relative, expected_hash=None, **kw):
            p = root / relative
            sha = digest(p.read_bytes())
            if expected_hash and expected_hash != sha:
                raise ValueError('SHA mismatch')
            return {'path': relative, 'sha256': sha, 'bytes': p.stat().st_size}
        for name in ('MODEL', 'MAX_DEPO', 'MAX_ISSUES', 'MAX_JSON'):
            setattr(decision, name, {
                'MODEL': 'ikamr.dwm.noark5.qa-decision.a12.v1',
                'MAX_DEPO': 24 * 1024 * 1024, 'MAX_ISSUES': 300,
                'MAX_JSON': 20 * 1024 * 1024}[name])
        for name, val in {
            '_rel': _rel, '_json': _json, '_source': _source,
            '_count': lambda n: n if type(n) is int and n >= 0 else None,
            '_hash': lambda p: digest(p.read_bytes()), '_parts': lambda r: [],
            '_assessments': lambda *a: {}, '_kdrs': lambda *a: {},
            '_extraction_label': lambda x: '', '_find_depot': lambda *a: None,
        }.items():
            setattr(decision, name, val)
        ext = types.ModuleType('noark5_workflow.analysis.canonical_external_import_v0115_a10')
        ext.MAX_SOURCE_ARKADE = 512 * 1024 * 1024
        ext.MAX_SOURCE_NORMALIZED = 48 * 1024 * 1024
        linked = {'external_validation': {'arkade5': {'imports': [
            {'normalized_file': self.relative, 'source_sha256': self.original_sha}]}}}
        meta = {'format_version': 2, 'import_id': 'one',
                'normalized_file': self.relative, 'imported_by': {'job_id': 'JOB-001'},
                'source': {'sha256': self.original_sha,
                           'preserved_file': 'external_evidence/arkade5/one/source/arkade.json'}}
        (self.base / 'manifest.json').write_text(json.dumps(meta), encoding='utf-8')
        package = 'noark5_workflow.reporting.qa_work_snapshot_v022_a3'
        production_module = sys.modules.get(package)
        production_find_depot = (getattr(production_module, '_find_depot', None)
                                 if production_module is not None else None)
        with patch.dict(sys.modules, {
                'noark5_workflow.reporting.qa_decision_v021_a12': decision,
                'noark5_workflow.analysis.canonical_external_import_v0115_a10': ext}):
            mod = _isolated_module(package, 'work_snapshot')
            small = mod._linked_arkade(self.work, linked, 'JOB-001', [], None, job_uid='stable-007')
            self.assertEqual(small['finding_count'], 2)
            self.assertTrue(small['findings_complete'])
            self.assertIsNone(small['a8_paged_index'])
            self.write(301, 1)
            large = mod._linked_arkade(self.work, linked, 'JOB-001', [], None, job_uid='stable-007')
            self.assertEqual(large['finding_count'], 302)
            self.assertFalse(large['findings_complete'])
            self.assertEqual(len(large['findings']), 250)
            self.assertEqual(page_arkade_index(self.work, large['a8_paged_index'],
                                                page=1, page_size=200)['total'], 302)
            # Simulate >20 MiB with a smaller configured read threshold:
            # no wholesale JSON decode is allowed in this branch.
            with patch.object(mod, 'MAX_JSON', 20):
                streamed = mod._linked_arkade(self.work, linked, 'JOB-001', [], None,
                                              job_uid='stable-007')
            self.assertEqual(streamed['finding_count'], 302)
            self.assertFalse(streamed['findings_complete'])
            self.assertEqual(streamed['a8_paged_index']['source_sha256'],
                             digest(self.source.read_bytes()))
        # Full unittest discovery must see the original module and references.
        self.assertIs(sys.modules.get(package), production_module)
        if production_module is not None:
            self.assertIs(production_module._find_depot, production_find_depot)


    def test_legacy_ks_export_refuses_incomplete_preview(self):
        """No partial HTML/CSV package may be silently published as complete."""
        export_name = 'noark5_workflow.reporting.qa_export_v022_a3'
        helper = types.ModuleType('noark5_workflow.reporting.qa_decision_v021_a12')
        helper._csv_cell = lambda x: str(x)
        helper._json = lambda *a, **k: {}
        helper.publish = lambda *a, **k: self.fail('Must not publish partial KS')
        helper.ReportInputError = type('ReportInputError', (ValueError,), {})
        a13 = types.ModuleType('noark5_workflow.reporting.qa_decision_v021_a13')
        a13._safe_destination = lambda *a, **k: self.fail('Must guard before destination')
        a13._validate_a20_job = lambda *a, **k: None
        review = types.ModuleType('noark5_workflow.reporting.qa_review_v021_a13')
        review.finding_key = lambda *a, **k: ''
        review.latest_reviews = lambda *a, **k: {'current': {}}
        review.STATUSES = {}
        workflow = types.ModuleType('noark5_workflow.reporting.qa_workflow_v022_a3')
        workflow.build_review_snapshot_v022_a3 = lambda *a, **k: {
            'findings_complete': False, 'findings': [{'test_id': 'N5.15'}]}
        workflow.finding_summary = lambda *a, **k: {}
        production_module = sys.modules.get(export_name)
        production_safe_destination = (getattr(production_module, '_safe_destination', None)
                                       if production_module is not None else None)
        production_error_class = (getattr(production_module, 'ReportInputError', None)
                                  if production_module is not None else None)
        with patch.dict(sys.modules, {
            'noark5_workflow.reporting.qa_decision_v021_a12': helper,
            'noark5_workflow.reporting.qa_decision_v021_a13': a13,
            'noark5_workflow.reporting.qa_review_v021_a13': review,
            'noark5_workflow.reporting.qa_workflow_v022_a3': workflow,
        }):
            mod = _isolated_module(export_name, 'qa_export')
            out = Path(self.tmp.name) / 'must-not-exist'
            with self.assertRaisesRegex(helper.ReportInputError, 'forhåndsvisning'):
                mod.export_review_bundle_v022_a3(work=self.work, output_dir=out)
            self.assertFalse(out.exists())
        self.assertIs(sys.modules.get(export_name), production_module)
        if production_module is not None:
            self.assertIs(production_module._safe_destination, production_safe_destination)
            self.assertIs(production_module.ReportInputError, production_error_class)


if __name__ == '__main__':
    unittest.main()
