"""A18: independent, source-bound DWM/Arkade technical control coverage.

All counts are of *observed records in the selected run*, NOT a claim of
complete normative test coverage, a sum of the two engines, or an approval.
A streamed Arkade parser verifies the original JSON bytes against the SHA-256
already pinned by the saved Work import. Unrelated PRONOM statistics are not
counted as Noark controls.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any
import re


MODEL = 'dwm.noark5.qa-control-coverage.v023-a18.v1'
STATES = ('executed_ok', 'reported_error', 'reported_warning', 'not_run',
          'interrupted', 'not_relevant', 'skipped', 'unknown')
MAX_TOKEN_BYTES = 8 * 1024 * 1024


class ControlCoverageError(ValueError):
    """Do not issue a misleading control summary from unverified evidence."""


class _HashingReader:
    def __init__(self, source):
        self.source = source
        self.hasher = sha256()
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        data = self.source.read(size)
        if data:
            self.hasher.update(data)
            self.bytes_read += len(data)
        return data

    def readable(self):
        return True


def _state(raw: Any) -> str:
    """Classify provenance status, not legal/Noark compliance."""
    value = str(raw or '').strip().casefold().replace(' ', '_').replace('-', '_')
    if value in ('ok', 'success', 'successful', 'pass', 'passed', 'completed', 'complete'):
        return 'executed_ok'
    if value in ('error', 'failed', 'fail', 'failure', 'invalid'):
        return 'reported_error'
    if value in ('warning', 'warn'):
        return 'reported_warning'
    if value in ('not_run', 'notrun', 'pending', 'queued', 'waiting', 'not_started'):
        return 'not_run'
    if value in ('cancelled', 'canceled', 'aborted', 'interrupted', 'stopped', 'running'):
        return 'interrupted'
    if value in ('not_applicable', 'not_relevant', 'na', 'n/a'):
        return 'not_relevant'
    if value in ('source_missing', 'skipped', 'skip', 'disabled_by_legacy_source',
                 'legacy_disabled', 'disabled'):
        return 'skipped'
    return 'unknown'


def _blank_counts() -> dict[str, int]:
    return {item: 0 for item in STATES}


def _non_ok(state: str) -> bool:
    return state not in ('executed_ok', 'not_relevant')


def _complete_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: int(counter.get(key, 0)) for key in STATES}


def _read_arkade(path: Path, *, expected_sha256: str,
                 expected_original_sha256: str) -> dict:
    """Count all tests, not just tests that have findings or are in a preview.

    No findings or large result arrays are materialized; the entire source JSON
    is parsed to EOF. Distinct test IDs are counted separately from array rows.
    """
    try:
        import ijson
    except ImportError as exc:
        raise ControlCoverageError('A18 trenger ijson fra requirements-core.txt') from exc
    if (not path.is_file() or path.is_symlink() or
            not re.fullmatch('[a-fA-F0-9]{64}', expected_sha256 or '') or
            not re.fullmatch('[a-fA-F0-9]{64}', expected_original_sha256 or '')):
        raise ControlCoverageError('Utrygg Arkade-kilde eller manglende kildehash')
    before = path.stat()
    statuses: Counter[str] = Counter()
    duplicate_ids: list[str] = []
    contradictions: list[str] = []
    observed_ids: set[str] = set()
    total = 0
    src_hash = None
    seen_top: set[str] = set()
    root_start = root_end = tests_start = tests_end = False
    valid_format = valid_source = valid_marker = False
    test: dict | None = None
    seen_test_fields: set[str] = set()
    reported_summary = None
    try:
        with path.open('rb') as raw:
            reader = _HashingReader(raw)
            for prefix, event, value in ijson.parse(reader):
                if event == 'string' and len(value.encode('utf-8')) > MAX_TOKEN_BYTES:
                    raise ControlCoverageError('For stort enkeltfelt i Arkade-kilden')
                if prefix == '' and event == 'start_map':
                    if root_start:
                        raise ControlCoverageError('Flere JSON-rotobjekter i Arkade-kilden')
                    root_start = True
                elif prefix == '' and event == 'map_key':
                    if value in seen_top:
                        raise ControlCoverageError('Duplisert rotfelt i Arkade-kilden')
                    seen_top.add(value)
                elif prefix == '' and event == 'end_map':
                    root_end = True
                elif prefix == 'format_version':
                    if event not in ('number', 'integer') or type(value) is not int or value != 2:
                        raise ControlCoverageError('Uventet Arkade-formatversjon')
                    valid_format = True
                elif prefix == 'source_system':
                    if event != 'string' or value != 'Arkade 5':
                        raise ControlCoverageError('Uventet kilde i Arkade-filen')
                    valid_source = True
                elif prefix == 'evidence_type':
                    if event != 'string' or value != 'arkade5_normalized_results':
                        raise ControlCoverageError('Ukjent type Arkade-evidens')
                    valid_marker = True
                elif prefix == 'source.sha256' and event == 'string':
                    if src_hash is not None:
                        raise ControlCoverageError('Duplisert originalhash i Arkade-filen')
                    src_hash = value
                elif prefix == 'summary.number_of_tests_run' and event in ('string', 'integer', 'number'):
                    reported_summary = str(value)
                elif prefix == 'tests' and event == 'start_array':
                    if tests_start:
                        raise ControlCoverageError('Duplisert Arkade-testliste')
                    tests_start = True
                elif prefix == 'tests' and event == 'end_array':
                    tests_end = True
                elif prefix == 'tests.item' and event == 'start_map':
                    if not tests_start or tests_end or test is not None:
                        raise ControlCoverageError('Ugyldig Arkade-teststruktur')
                    test = {}
                    seen_test_fields = set()
                elif prefix == 'tests.item' and event == 'end_map':
                    if test is None:
                        raise ControlCoverageError('Arkade-test mangler start')
                    ident = str(test.get('test_id') or '').strip()
                    if not ident:
                        raise ControlCoverageError('Arkade-test mangler test-ID')
                    if ident in observed_ids:
                        duplicate_ids.append(ident)
                    observed_ids.add(ident)
                    raw_state = str(test.get('source_status') or '')
                    state = _state(raw_state)
                    statuses[state] += 1
                    errors = test.get('number_of_errors')
                    if isinstance(errors, str) and errors.isdecimal():
                        errors = int(errors)
                    if (type(errors) is int and errors > 0 and state in ('executed_ok', 'not_relevant', 'skipped')):
                        contradictions.append(ident + ': oppgitt ' + raw_state + ', men number_of_errors=' + str(errors))
                    test = None
                    total += 1
                elif test is not None and prefix.startswith('tests.item.'):
                    field = prefix[len('tests.item.'):]
                    if field in ('test_id', 'source_status', 'number_of_errors'):
                        if event in ('start_map', 'start_array'):
                            raise ControlCoverageError('Uventet struktur i Arkade-testfelt: ' + field)
                        if event in ('string', 'integer', 'number', 'null'):
                            if field in seen_test_fields:
                                raise ControlCoverageError('Duplisert Arkade-testfelt: ' + field)
                            if field in ('test_id', 'source_status') and event not in ('string', 'null'):
                                raise ControlCoverageError('Ugyldig testidentitet eller status')
                            seen_test_fields.add(field)
                            test[field] = value
        if (not root_start or not root_end or not tests_start or not tests_end or
                test is not None or not valid_format or not (valid_source or valid_marker)):
            raise ControlCoverageError('Ufullstendig Arkade-testgrunnlag')
        if src_hash is None or src_hash.lower() != expected_original_sha256.lower():
            raise ControlCoverageError('Normalisert Arkade-rapport gjelder en annen originalkilde')
        if (reader.hasher.hexdigest().lower() != expected_sha256.lower() or
                path.stat().st_size != before.st_size or
                path.stat().st_mtime_ns != before.st_mtime_ns):
            raise ControlCoverageError('Arkade-rapporten er endret etter SHA-256-binding')
    except (OSError, UnicodeError, getattr(ijson, 'JSONError', ValueError), ValueError) as exc:
        if isinstance(exc, ControlCoverageError):
            raise
        raise ControlCoverageError('Kunne ikke strømlese Arkade-kontroller') from exc

    declared = None
    parsed = re.fullmatch(r'\s*(\d+)\s+av\s+(\d+)\s*', reported_summary or '', re.I)
    if parsed:
        declared = {'reported_run': int(parsed.group(1)), 'reported_total': int(parsed.group(2))}
        if declared['reported_run'] != total:
            contradictions.append('Arkade-sammendragets antall kjørte tester avviker fra testlisten')
    return {
        'available': True, 'source_sha256': reader.hasher.hexdigest(),
        'source_original_sha256': expected_original_sha256,
        'observed_test_rows': total, 'distinct_test_ids': len(observed_ids),
        'by_state': _complete_counts(statuses),
        'duplicate_test_ids': sorted(set(duplicate_ids)),
        'source_contradictions': contradictions,
        'reported_test_denominator': declared,
        'reported_raw_summary': reported_summary,
    }


def _dwm_coverage(master: dict, depot_tests: list[dict]) -> dict:
    if not isinstance(master, dict) or not isinstance(master.get('tests'), list):
        raise ControlCoverageError('Manglende verifisert DWM XPath-master')
    if not isinstance(depot_tests, list):
        raise ControlCoverageError('Ugyldig depotrapportert DWM-testliste')
    states: Counter[str] = Counter()
    master_tests: dict[str, dict] = {}
    for item in master['tests']:
        if not isinstance(item, dict):
            raise ControlCoverageError('Ugyldig DWM-testpost')
        ident = str(item.get('test_id') or '').strip()
        if not ident or ident in master_tests:
            raise ControlCoverageError('Tomme eller dupliserte DWM-mastertest-ID-er')
        master_tests[ident] = item
        states[_state(item.get('status'))] += 1
    report_seen: set[str] = set()
    duplicated: list[str] = []
    for item in depot_tests:
        if not isinstance(item, dict):
            raise ControlCoverageError('Ugyldig rapportert DWM-testpost')
        ident = str(item.get('test_id') or '').strip()
        if ident not in master_tests:
            raise ControlCoverageError('Depotrapportert DWM-test finnes ikke i XPath-master')
        if ident in report_seen:
            duplicated.append(ident)
        report_seen.add(ident)
        if str(item.get('status') or '').casefold() != str(master_tests[ident].get('status') or '').casefold():
            raise ControlCoverageError('Ulik DWM-teststatus mellom depotrapport og master')
    missing = sorted(set(master_tests) - report_seen)
    non_ok = [
        {'test_id': str(item['test_id']), 'status': str(item.get('status') or ''),
         'test_point': str(item.get('test_point') or '')}
        for item in depot_tests if _non_ok(_state(item.get('status')))
    ]
    return {
        'available': True,
        'observed_master_tests': len(master_tests),
        'reported_depot_test_rows': len(depot_tests),
        'distinct_depot_test_ids': len(report_seen),
        'by_state': _complete_counts(states),
        'missing_from_depot_report': missing,
        'duplicate_depot_test_ids': sorted(set(duplicated)),
        'non_ok_reported_tests': non_ok,
        'planned_catalog_total': None,
        'planned_catalog_total_note': 'Kun testene dokumentert i valgt XPath-master er kjent her; full planlagt testliste er ikke verifisert.',
    }


def _part_coverage(depot_summary: dict, parts: list[dict]) -> dict:
    if not isinstance(depot_summary, dict) or not isinstance(parts, list):
        raise ControlCoverageError('Ugyldige arkivdelstall i depotrapport')
    comparisons = {}
    for summary_field, part_field in (
            ('archive_part_count', None), ('folder_count', 'folder_count'),
            ('registration_count', 'registration_count'),
            ('document_object_count', 'document_object_count')):
        reported = depot_summary.get(summary_field)
        if type(reported) is not int or reported < 0:
            reported = None
        if part_field is None:
            observed = len(parts)
        else:
            values = [item.get(part_field) for item in parts]
            observed = sum(values) if all(type(n) is int and n >= 0 for n in values) else None
        matches = (reported == observed) if reported is not None and observed is not None else None
        comparisons[summary_field] = {
            'depot_report_total': reported, 'sum_of_archive_parts': observed,
            'matches': matches, 'comparable': matches is not None,
        }
    return comparisons


def reconcile_controls(*, master: dict, depot_tests: list[dict],
                       depot_summary: dict, parts: list[dict],
                       arkade_path: Path | None = None,
                       arkade_source_sha256: str | None = None,
                       arkade_original_sha256: str | None = None,
                       pronom_imported: bool = False,
                       depot_technical_status: str = '') -> dict:
    """One evidence-bound control overview, deliberately non-additive by tool."""
    dwm = _dwm_coverage(master, depot_tests)
    archive = _part_coverage(depot_summary, parts)
    arkade = (
        _read_arkade(arkade_path, expected_sha256=arkade_source_sha256 or '',
                     expected_original_sha256=arkade_original_sha256 or '')
        if arkade_path is not None else
        {'available': False, 'observed_test_rows': None, 'distinct_test_ids': None,
         'by_state': None, 'source_contradictions': [],
         'duplicate_test_ids': [], 'reported_test_denominator': None})
    if arkade_path is None and (arkade_source_sha256 or arkade_original_sha256):
        raise ControlCoverageError('Arkade-kildehash uten valgt kildefil')
    issues = []
    if (_state(depot_technical_status) == 'executed_ok' and
            any(dwm['by_state'][k] for k in STATES if k != 'executed_ok')):
        issues.append('Depotrapportens samlede DWM-status er OK, men individuelle DWM-teststatuser er ikke alle OK')
    if arkade['available'] and arkade['observed_test_rows'] == 0:
        issues.append('Arkade-kilden inneholder ingen testposter; fravær er ikke bestått kontroll')
    if dwm['missing_from_depot_report']:
        issues.append(f"{len(dwm['missing_from_depot_report'])} DWM-tester mangler i depotrapportens kontrolltabell")
    if dwm['duplicate_depot_test_ids']:
        issues.append('Dupliserte DWM-test-ID-er i depotrapporten')
    if arkade['duplicate_test_ids']:
        issues.append('Dupliserte Arkade-test-ID-er')
    issues.extend(arkade['source_contradictions'])
    for field, status in archive.items():
        if status['matches'] is False:
            issues.append('Avvik mellom hovedtall og arkivdeler: ' + field)
    for engine, block in (('DWM XPath', dwm), ('Arkade 5 Noark', arkade)):
        counts = block.get('by_state') or {}
        unresolved = sum(counts.get(k, 0) for k in ('not_run', 'interrupted', 'skipped', 'unknown'))
        if unresolved:
            issues.append(f'{engine}: {unresolved} ikke kjørte, avbrutte, hoppede over eller ukjente kontrollstatuser')
        non_ok = sum(counts.get(k, 0) for k in ('reported_error', 'reported_warning'))
        if non_ok:
            issues.append(f'{engine}: {non_ok} testposter med rapportert feil eller advarsel')
    return {
        'model_id': MODEL,
        'meaning': 'Kildetro status per testmotor; ingen summert normativ PASS eller faglig godkjenning',
        'dwm_xpath': dwm, 'arkade_noark': arkade,
        'depot_technical_status_as_reported': depot_technical_status or None,
        'archive_part_reconciliation': archive,
        'pronom': {
            'arkade_format_statistics': 'imported_and_work_hash_checked' if pronom_imported else 'not_linked_to_selected_report',
            'siegfried_format_statistics': 'not_assessed_in_this_snapshot',
            'counts_as_noark_tests': False,
        },
        'control_issues': issues,
        'status': 'REQUIRES_REVIEW' if issues else 'SOURCE_OBSERVATIONS_ONLY_NOT_APPROVED',
        'total_test_count_across_tools': None,
        'expected_test_plan_coverage_verified': False,
        'automatic_approval': False,
    }
