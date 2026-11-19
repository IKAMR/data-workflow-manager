"""Incremental projection of DWM-normalized Arkade JSON evidence.

The normalized file duplicates native data in ``source_raw`` and
``result_set_tree``. Those fields are parsed for JSON validity but never built
as Python objects; only the fields in the existing external-analysis contract
are retained. The projected result has a separate finite output bound.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import ijson


MAX_STRING = 8 * 1024 * 1024
MAX_FIELD = 2 * 1024 * 1024
MAX_PROJECTED_RECORD = 64 * 1024 * 1024
ISSUE_PREVIEW_LIMIT = 250  # inline DISPLAY limit; all source events still parsed
SUMMARY_FIELDS = ('number_of_tests_run', 'number_of_errors', 'number_of_warnings',
                  'archive_type', 'system_name', 'archival_period')
CONTENT_SUMMARY_FIELDS = ('archive_creators', 'system_name', 'system_type',
                          'archival_period', 'date_of_testing')
CONTENT_TESTS = frozenset(('N5.06', 'N5.10', 'N5.15', 'N5.22'))
MAX_CONTENT_PROJECTION = 32 * 1024 * 1024


class ArkadeStreamError(ValueError):
    """Malformed source or a documented per-element resource limit."""


def _plain(value: Any) -> Any:
    """Match json.loads number types when ijson yields Decimal values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _bounded(value: Any, label: str) -> Any:
    value = _plain(value)
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')) > MAX_FIELD:
        raise ArkadeStreamError(f'{label} overstiger {MAX_FIELD} bytes')
    return value


def has_normalized_arkade_tests(path: Path) -> bool:
    """Check A210's source marker and tests-array shape without loading tests."""
    source_system = None
    tests_list = False
    try:
        with path.open('rb') as stream:
            for prefix, event, value in ijson.parse(stream):
                if prefix == 'source_system' and event in ('string', 'null', 'boolean', 'number'):
                    source_system = value
                elif prefix == 'tests' and event == 'start_array':
                    tests_list = True
                if source_system is not None and tests_list:
                    return source_system == 'Arkade 5'
    except (OSError, UnicodeError, ValueError, ijson.JSONError) as exc:
        raise ArkadeStreamError(f'Ugyldig normalisert Arkade JSON: {exc}') from exc
    return source_system == 'Arkade 5' and tests_list


def inspect_arkade_stream(path: Path, relative: str, *, max_items: int | None,
                          max_output: int) -> dict[str, Any]:
    """Read Arkade records as events and retain only bounded projections.

    A full test, its ``results`` array, and duplicated raw structures are never
    materialized. The returned records are the required v1 projection, bounded
    by ``max_output`` so later serialization has a finite memory ceiling.
    """
    if not relative.lower().endswith('/normalized/arkade5_results.json'):
        raise ArkadeStreamError('Ukjent normalisert Arkade-sti')
    arrays: dict[str, list[Any]] = {'tests': [], 'results': []}
    present: set[str] = set()
    envelope: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    capture: tuple[str, ijson.ObjectBuilder, int] | None = None
    projected_bytes = 0
    root_is_map = False

    def assign(prefix: str, value: Any) -> None:
        nonlocal current, result
        value = _bounded(value, prefix)
        if prefix in ('format_version', 'evidence_type', 'source_system', 'source_version'):
            envelope[prefix] = value
        elif prefix.startswith('summary.') and prefix[8:] in SUMMARY_FIELDS:
            summary[prefix[8:]] = value
        elif current is not None:
            test_prefix = current['prefix']
            if prefix in (test_prefix + '.' + key for key in
                          ('test_id', 'id', 'source_status', 'status', 'test_name',
                           'test_type', 'number_of_errors')):
                current['fields'][prefix[len(test_prefix) + 1:]] = value
            elif result is not None and prefix in (test_prefix + '.results.item.' + key
                                                  for key in ('result_type', 'message',
                                                              'result_set_path', 'location')):
                result[prefix.rsplit('.', 1)[-1]] = value

    try:
        with path.open('rb') as stream:
            for prefix, event, value in ijson.parse(stream):
                if event == 'string' and len(value.encode('utf-8')) > MAX_STRING:
                    raise ArkadeStreamError(f'JSON-tekstfelt overstiger {MAX_STRING} bytes')
                if capture is not None:
                    name, builder, depth = capture
                    builder.event(event, value)
                    depth += (event in ('start_map', 'start_array')) - (event in ('end_map', 'end_array'))
                    if depth == 0:
                        assign(name, builder.value)
                        capture = None
                    else:
                        capture = (name, builder, depth)
                    continue
                if prefix == '' and event == 'start_map':
                    root_is_map = True
                if prefix in arrays and event == 'start_array':
                    present.add(prefix)
                    if prefix == 'tests':
                        # The established adapter gives tests precedence over
                        # a separate top-level results array.
                        arrays['results'].clear()
                        projected_bytes = 0
                    continue
                if prefix in ('tests.item', 'results.item'):
                    array_name = prefix.split('.')[0]
                    if array_name == 'results' and 'tests' in present:
                        continue
                    if event == 'start_map':
                        current = {'prefix': prefix, 'fields': {}, 'result_list': False,
                                   'invalid_result': False, 'result_counts': Counter(),
                                   'results_count': 0, 'issues': [], 'issues_bytes': 0,
                                   'issues_total': 0, 'preview_limit_reached': False}
                    elif event == 'end_map' and current is not None:
                        arrays[array_name].append(current)
                        projected_bytes += len(json.dumps(current['fields'], ensure_ascii=False).encode('utf-8'))
                        projected_bytes += sum(len(json.dumps(issue, ensure_ascii=False).encode('utf-8'))
                                               for issue in current['issues'])
                        if projected_bytes > max_output:
                            raise ArkadeStreamError(f'Projiserte testposter overstiger {max_output} bytes')
                        if max_items is not None and len(arrays[array_name]) > max_items:
                            raise ArkadeStreamError(f'Antall testposter overstiger {max_items}')
                        current = None
                    elif event in ('start_array', 'string', 'number', 'boolean', 'null'):
                        arrays[array_name].append(None)
                        if max_items is not None and len(arrays[array_name]) > max_items:
                            raise ArkadeStreamError(f'Antall testposter overstiger {max_items}')
                    continue
                if current is not None:
                    test_prefix = current['prefix']
                    if prefix == test_prefix + '.results':
                        if event == 'start_array':
                            current['result_list'] = True
                        continue
                    if prefix == test_prefix + '.results.item':
                        if event == 'start_map':
                            result = {}
                        elif event == 'end_map' and result is not None:
                            current['results_count'] += 1
                            if max_items is not None and current['results_count'] > max_items:
                                raise ArkadeStreamError(f'Resultatposter per test overstiger {max_items}')
                            kind = result.get('result_type')
                            current['result_counts'][kind if isinstance(kind, str) and kind in
                                                     ('Success', 'Error', 'Warning', 'Other') else 'Other'] += 1
                            if kind in ('Error', 'Warning'):
                                current['issues_total'] += 1
                                # No finding is discarded from source evidence. Only
                                # the *inline* A220 preview has a bounded size.
                                if (not current['preview_limit_reached'] and
                                        len(current['issues']) < ISSUE_PREVIEW_LIMIT):
                                    issue = {'index': current['results_count'] - 1, 'result_type': kind,
                                             'message': result.get('message') if isinstance(result.get('message'), str) else None,
                                             'result_set_path': result.get('result_set_path') if isinstance(result.get('result_set_path'), list) else [],
                                             'location': result.get('location') if isinstance(result.get('location'), dict) else None}
                                    size = len(json.dumps(issue, ensure_ascii=False).encode('utf-8'))
                                    if (current['issues_bytes'] + size <= MAX_PROJECTED_RECORD and
                                            projected_bytes + current['issues_bytes'] + size
                                            <= max_output // 2):
                                        current['issues'].append(issue)
                                        current['issues_bytes'] += size
                                    else:
                                        current['preview_limit_reached'] = True
                            result = None
                        elif event not in ('map_key', 'start_array', 'end_array'):
                            current['invalid_result'] = True
                        continue
                selected = (prefix in ('format_version', 'evidence_type', 'source_system', 'source_version') or
                            prefix.startswith('summary.') and prefix[8:] in SUMMARY_FIELDS or
                            current is not None and prefix in
                            (current['prefix'] + '.' + key for key in
                             ('test_id', 'id', 'source_status', 'status', 'test_name',
                              'test_type', 'number_of_errors')) or
                            current is not None and result is not None and prefix in
                            (current['prefix'] + '.results.item.' + key for key in
                             ('result_type', 'message', 'result_set_path', 'location')))
                if selected and event in ('start_map', 'start_array'):
                    builder = ijson.ObjectBuilder()
                    builder.event(event, value)
                    capture = (prefix, builder, 1)
                elif selected and event in ('string', 'number', 'boolean', 'null'):
                    assign(prefix, value)
    except (OSError, UnicodeError, ValueError, ijson.JSONError) as exc:
        if isinstance(exc, ArkadeStreamError):
            raise
        raise ArkadeStreamError(f'Ugyldig normalisert Arkade JSON: {exc}') from exc

    if not root_is_map:
        return {'source_format': 'arkade_normalized_candidate', 'interpretation': 'not_parsed',
                'reason': 'Forventer JSON-objekt'}
    chosen = 'tests' if 'tests' in present else 'results' if 'results' in present else None
    if chosen is None:
        return {'source_format': 'arkade_normalized_candidate', 'interpretation': 'not_parsed',
                'reason': 'Fant ikke eksplisitt tests/results-liste; trenger ekte eksempel'}
    is_dwm = (envelope.get('format_version') == 2 and
              envelope.get('evidence_type') == 'external_validation_report' and
              envelope.get('source_system') == 'Arkade 5')
    records = arrays[chosen]
    status_counts: Counter[str] = Counter()
    for index, entry in enumerate(records):
        if entry is None:
            return {'source_format': 'arkade_normalized_candidate', 'interpretation': 'not_parsed',
                    'reason': 'Testposter er ikke objekter'}
        fields = entry['fields']
        identifier = fields.get('test_id', fields.get('id'))
        status = fields.get('source_status') if is_dwm else fields.get('status')
        if (not isinstance(identifier, str) or not identifier.strip() or
                not isinstance(status, str) or not status.strip()):
            return {'source_format': 'arkade_normalized_candidate', 'interpretation': 'not_parsed',
                    'reason': 'Hver post maa inneholde tekstfeltene test_id/id og status'}
        if len(identifier) > 300 or len(status) > 120:
            raise ArkadeStreamError(f'Testpost {index}: ugyldig lang testidentifikator eller status')
        record = {'index': index, 'external_test_id': identifier, 'reported_status': status,
                  'status_interpretation': 'source_text_not_mapped',
                  'technical_verification': 'not_verified', 'depot_approval': None}
        if is_dwm:
            count = fields.get('number_of_errors')
            if (not entry['result_list'] or entry['invalid_result'] or
                    type(count) is not int or count < 0):
                return {'source_format': 'arkade_normalized_v2', 'interpretation': 'not_parsed',
                        'reason': 'Ugyldig resultatliste eller feiltall i Arkade v2'}
            counts = {key: entry['result_counts'].get(key, 0)
                      for key in ('Success', 'Error', 'Warning', 'Other')}
            record.update({'test_name': fields.get('test_name'), 'test_type': fields.get('test_type'),
                           'source_number_of_errors': count, 'reported_result_counts': counts,
                           'reported_issues': entry['issues']})
            if entry['issues_total'] > len(entry['issues']):
                # Downstream A260 reads *all* findings from the SHA-bound
                # original; legacy HTML must not mistake this preview for all.
                record.update({'reported_issues_total': entry['issues_total'],
                               'reported_issues_preview_count': len(entry['issues']),
                               'reported_issues_complete': False,
                               'complete_evidence_work_relative_path': relative})
            status_counts[status] += 1
        records[index] = record
    response = {'source_format': 'arkade_normalized_v2' if is_dwm else 'arkade_normalized_candidate',
                'interpretation': 'reported_test_records_unverified', 'record_count': len(records),
                'records': records,
                'note': 'Status er gjengitt ordrett. Arkade-resultater er ekstern evidens, ikke depotaksept.'}
    if is_dwm:
        response['source_version'] = envelope.get('source_version')
        response['reported_summary'] = {key: summary.get(key) for key in SUMMARY_FIELDS}
        response['reported_status_counts'] = dict(sorted(status_counts.items()))
    return response


def content_projection(path: Path) -> dict[str, Any]:
    """Read only the source fields used by the optional QA content annex.

    All JSON is parsed, including omitted raw duplicates. Selected test result
    fields are built one result at a time and kept under a separate bound.
    """
    summary: dict[str, Any] = {}
    tests: list[dict[str, Any]] = []
    envelope: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    capture: tuple[str, ijson.ObjectBuilder, int] | None = None
    projected = 0

    def assign(prefix: str, value: Any) -> None:
        nonlocal projected
        value = _bounded(value, prefix)
        if prefix in ('format_version', 'evidence_type'):
            envelope[prefix] = value
        elif prefix.startswith('summary.') and prefix[8:] in CONTENT_SUMMARY_FIELDS:
            summary[prefix[8:]] = value
        elif current is not None and prefix == 'tests.item.test_id':
            current['test_id'] = value
        elif current is not None and result is not None and prefix in (
                'tests.item.results.item.result_type', 'tests.item.results.item.message',
                'tests.item.results.item.result_set_path'):
            result[prefix.rsplit('.', 1)[-1]] = value

    try:
        with path.open('rb') as stream:
            for prefix, event, value in ijson.parse(stream):
                if event == 'string' and len(value.encode('utf-8')) > MAX_STRING:
                    raise ArkadeStreamError(f'JSON-tekstfelt overstiger {MAX_STRING} bytes')
                if capture is not None:
                    name, builder, depth = capture
                    builder.event(event, value)
                    depth += (event in ('start_map', 'start_array')) - (event in ('end_map', 'end_array'))
                    if depth == 0:
                        assign(name, builder.value)
                        capture = None
                    else:
                        capture = (name, builder, depth)
                    continue
                if prefix == 'tests.item' and event == 'start_map':
                    current = {'test_id': None, 'results': [], 'results_before_id': False}
                    continue
                if prefix == 'tests.item' and event == 'end_map' and current is not None:
                    if current['test_id'] in CONTENT_TESTS:
                        if current['results_before_id']:
                            raise ArkadeStreamError('test_id følger etter results; innhold kan ikke projiseres trygt')
                        tests.append({'test_id': current['test_id'], 'results': current['results']})
                    current = None
                    continue
                if current is not None and prefix == 'tests.item.results.item':
                    if event == 'start_map':
                        result = {}
                        if current['test_id'] is None:
                            current['results_before_id'] = True
                    elif event == 'end_map' and result is not None:
                        if current['test_id'] in CONTENT_TESTS:
                            projected += len(json.dumps(result, ensure_ascii=False).encode('utf-8'))
                            if projected > MAX_CONTENT_PROJECTION:
                                raise ArkadeStreamError(f'QA-innholdsuttrekk overstiger {MAX_CONTENT_PROJECTION} bytes')
                            current['results'].append(result)
                        result = None
                    continue
                selected = (prefix in ('format_version', 'evidence_type') or
                            prefix.startswith('summary.') and prefix[8:] in CONTENT_SUMMARY_FIELDS or
                            current is not None and prefix == 'tests.item.test_id' or
                            current is not None and result is not None and
                            current['test_id'] in CONTENT_TESTS and prefix in (
                                'tests.item.results.item.result_type',
                                'tests.item.results.item.message',
                                'tests.item.results.item.result_set_path'))
                if selected and event in ('start_map', 'start_array'):
                    builder = ijson.ObjectBuilder()
                    builder.event(event, value)
                    capture = (prefix, builder, 1)
                elif selected and event in ('string', 'number', 'boolean', 'null'):
                    assign(prefix, value)
    except (OSError, UnicodeError, ValueError, ijson.JSONError) as exc:
        if isinstance(exc, ArkadeStreamError):
            raise
        raise ArkadeStreamError(f'Ugyldig normalisert Arkade JSON: {exc}') from exc
    return {'format_version': envelope.get('format_version'),
            'evidence_type': envelope.get('evidence_type'),
            'summary': summary, 'tests': tests}
