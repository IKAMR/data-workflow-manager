"""A260: complete, source-bound Arkade finding exports with bounded HTML preview.

This module does not change test outcomes, source evidence, or review decisions.
It reads the Work-selected normalized Arkade source as incremental JSON events,
spooling one test's findings to disk before emitting stable issue rows.  The
entire source is parsed and checked before any new report is published.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import csv
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable, Iterator
from uuid import uuid4

MODEL = 'dwm.noark5.a260.complete-findings.a6.v1'
PREVIEW_LIMIT = 250
MAX_TESTS_INLINE = 250
MAX_TEXT_TOKEN = 8 * 1024 * 1024  # Same guard as A220; reject, never truncate.
CSV_FIELDS = ('finding_uid', 'source', 'test_id', 'severity', 'message', 'context',
              'file', 'lines', 'source_ref', 'requires_review', 'finding_key',
              'professional_status', 'review_comment', 'include_in_ks', 'include_in_depot')


class A260CapacityError(ValueError):
    """Unusable evidence or resource failure; never report incomplete results."""


def _sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as inp:
        for piece in iter(lambda: inp.read(1024 * 1024), b''):
            h.update(piece)
    return h.hexdigest()


def _secure_work_file(work: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or '\\' in relative or
            ':' in relative.split('/')[0] or relative.startswith('/')):
        raise A260CapacityError('Forventer sikker Work-relativ evidenssti')
    bits = relative.split('/')
    if any(bit in ('', '.', '..') for bit in bits):
        raise A260CapacityError('Evidenssti har ugyldig segment')
    result = work
    for bit in bits:
        result = result / bit
        if result.is_symlink():
            raise A260CapacityError('Symbolsk lenke i evidenssti: ' + relative)
    if not result.resolve(strict=False).is_relative_to(work.resolve(strict=True)):
        raise A260CapacityError('Evidens utenfor Work')
    if not result.is_file():
        raise A260CapacityError('Evidens mangler: ' + relative)
    return result


def _text(value: Any) -> str:
    result = str(value) if value is not None else ''
    if len(result.encode('utf-8')) > MAX_TEXT_TOKEN:
        raise A260CapacityError('Tekstfelt overstiger A220s 8 MiB-grense')
    return result


def _finding_key(row: dict) -> str:
    # Exact field set and canonicalization of qa_review_v021_a13.finding_key.
    fields = ('source', 'test_id', 'severity', 'message', 'context', 'file', 'source_ref', 'lines')
    data = {key: row.get(key) for key in fields}
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def _issue_uid(source_sha: str, test_index: int, result_index: int) -> str:
    # Per occurrence, unlike the historical review-key that may match duplicates.
    return sha256(f'{source_sha}:{test_index}:{result_index}'.encode()).hexdigest()


def iter_arkade_findings(events: Iterable[tuple[str, str, Any]], *,
                         source_ref: str, source_sha: str) -> Iterator[dict]:
    """Consume ijson.parse() events. Never load an entire test/results array.

    Disk-spool result detail rows until the test ID/status are known, even when
    those fields appear *after* results.  A malformed source is rejected at end
    (the caller discards staged exports). Unknown raw fields are not projected.
    """
    source_ok = False
    format_ok = False
    has_tests = False
    current: dict | None = None
    issue: dict | None = None
    per_test = None
    test_index = -1
    result_index = -1
    emitted_count = 0
    try:
        for prefix, event, value in events:
            if prefix == 'source_system' and event == 'string':
                source_ok = value == 'Arkade 5'
            elif prefix == 'format_version' and event in ('number', 'integer'):
                format_ok = value == 2
            elif prefix == 'tests' and event == 'start_array':
                has_tests = True
            elif prefix == 'tests.item' and event == 'start_map':
                if per_test is not None:
                    raise A260CapacityError('Ugyldig nestet testpost')
                current = {'test_id': '', 'source_status': '', 'number_of_errors': 0}
                per_test = tempfile.SpooledTemporaryFile(mode='w+t', max_size=1024 * 1024,
                                                         encoding='utf-8', newline='\n')
                test_index += 1
                result_index = -1
                emitted_count = 0
            elif prefix == 'tests.item.results.item' and event == 'start_map':
                issue = {'result_type': '', 'message': '', 'result_set_path': [],
                         'file_name': '', 'location_string': '', 'line_numbers': []}
                result_index += 1
            elif issue is not None and prefix.startswith('tests.item.results.item.'):
                if event in ('string', 'null', 'number', 'integer', 'boolean'):
                    if prefix == 'tests.item.results.item.result_type':
                        issue['result_type'] = _text(value)
                    elif prefix == 'tests.item.results.item.message':
                        issue['message'] = _text(value)
                    elif prefix == 'tests.item.results.item.location.file_name':
                        issue['file_name'] = _text(value)
                    elif prefix == 'tests.item.results.item.location.string':
                        issue['location_string'] = _text(value)
                    elif prefix == 'tests.item.results.item.result_set_path.item':
                        issue['result_set_path'].append(_text(value))
                    elif prefix == 'tests.item.results.item.location.line_numbers.item':
                        if type(value) is int and value > 0:
                            issue['line_numbers'].append(value)
            elif prefix == 'tests.item.results.item' and event == 'end_map':
                if issue is None or per_test is None:
                    raise A260CapacityError('Resultatpost uten test')
                kind = issue['result_type'].casefold()
                if kind in ('error', 'warning', 'warn', 'failed', 'failure'):
                    severity = 'WARNING' if kind in ('warning', 'warn') else 'ERROR'
                    payload = {
                        'severity': severity,
                        'message': issue['message'] or 'Arkade reports an issue without details',
                        'context': ' / '.join(issue['result_set_path']),
                        'file': issue['file_name'] or issue['location_string'],
                        'lines': issue['line_numbers'],
                        'result_index': result_index,
                    }
                    per_test.write(json.dumps(payload, ensure_ascii=False) + '\n')
                    emitted_count += 1
                issue = None
            elif current is not None and prefix.startswith('tests.item.') and event in (
                    'string', 'null', 'number', 'integer', 'boolean'):
                if prefix == 'tests.item.test_id':
                    current['test_id'] = _text(value)
                elif prefix == 'tests.item.source_status':
                    current['source_status'] = _text(value)
                elif prefix == 'tests.item.number_of_errors':
                    current['number_of_errors'] = value
            elif prefix == 'tests.item' and event == 'end_map':
                if per_test is None or current is None:
                    raise A260CapacityError('Uventet slutten på test')
                test_id = current['test_id'].strip()
                if not test_id:
                    raise A260CapacityError(f'Arkade-testpost {test_index} mangler test_id')
                per_test.seek(0)
                for line in per_test:
                    payload = json.loads(line)
                    ordinal = payload.pop('result_index')
                    row = {'source': 'Arkade 5', 'test_id': test_id,
                           'source_ref': source_ref, 'requires_review': True, **payload}
                    row['finding_uid'] = _issue_uid(source_sha, test_index, ordinal)
                    row['finding_key'] = _finding_key(row)
                    yield row
                status = current['source_status'].casefold()
                raw_count = current['number_of_errors']
                if emitted_count == 0 and (status in ('error', 'failed', 'warning', 'warn') or
                                           (isinstance(raw_count, (int, Decimal)) and not isinstance(raw_count, bool) and raw_count > 0)):
                    row = {'source': 'Arkade 5', 'test_id': test_id,
                           'severity': 'WARNING' if status in ('warning', 'warn') else 'ERROR',
                           'message': 'Arkade reports a non-OK test; check its original source report.',
                           'context': '', 'file': '', 'lines': [], 'source_ref': source_ref,
                           'requires_review': True}
                    row['finding_uid'] = _issue_uid(source_sha, test_index, -1)
                    row['finding_key'] = _finding_key(row)
                    yield row
                per_test.close()
                per_test = None
                current = None
        if not (source_ok and format_ok and has_tests):
            raise A260CapacityError('Arkade-kilden mangler bekreftet v2-struktur og tests-array')
        if current is not None or issue is not None or per_test is not None:
            raise A260CapacityError('Arkade-kilden inneholder ufullstendig test-/resultatpost')
    finally:
        if per_test is not None:
            per_test.close()


def _csv_cell(value: Any) -> str:
    text = (', '.join(str(v) for v in value) if isinstance(value, list) else
            '' if value is None else str(value))
    # Spreadsheet-formula protection only for CSV, never alter JSONL evidence.
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text


class FindingWriter:
    """Incremental full JSONL/CSV export and constant-size HTML preview."""
    def __init__(self, jsonl: Path, csv_file: Path, *, preview_limit: int = PREVIEW_LIMIT,
                 reviewed_events: dict[str, dict] | None = None):
        self.jsonl_file = jsonl.open('w', encoding='utf-8', newline='\n')
        self.csv_file = csv_file.open('w', encoding='utf-8-sig', newline='')
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=CSV_FIELDS, delimiter=';',
                                         lineterminator='\r\n', extrasaction='ignore')
        self.csv_writer.writeheader()
        self.preview_limit = preview_limit
        self.preview: list[dict] = []
        self.severity = Counter()
        self.by_test = Counter()
        self.by_arkade_test = Counter()
        self.by_source = Counter()
        self.reviewed_events = reviewed_events or {}
        self.reviewed = 0
        self.manual = 0
        self.count = 0

    def add(self, row: dict) -> None:
        if not all(isinstance(row.get(x), str) and row[x] for x in
                   ('source', 'test_id', 'message', 'source_ref')):
            raise A260CapacityError('Avviksrad mangler kilde, test eller beskrivelse')
        row = dict(row)
        row.setdefault('context', '')
        row.setdefault('file', '')
        row.setdefault('lines', [])
        row.setdefault('requires_review', True)
        row.setdefault('severity', 'REVIEW')
        row.setdefault('finding_key', _finding_key(row))
        row.setdefault('finding_uid', sha256((row['finding_key'] + ':' +
                             str(self.count)).encode()).hexdigest())
        match = self.reviewed_events.get(row['finding_key'])
        if match:
            row['professional_status'] = str(match['status'])
            row['review_comment'] = str(match.get('comment') or '')
            row['include_in_ks'] = bool(match.get('include_in_ks'))
            row['include_in_depot'] = bool(match.get('include_in_depot'))
            self.reviewed += 1
        else:
            row['professional_status'] = 'Ikke vurdert'
            row['review_comment'] = ''
            row['include_in_ks'] = False
            row['include_in_depot'] = False
        self.manual += int(bool(row.get('manual_event_id')))
        self.jsonl_file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        self.csv_writer.writerow({k: _csv_cell(row.get(k)) for k in CSV_FIELDS})
        self.count += 1
        self.severity[row['severity'].upper()] += 1
        self.by_test[row['test_id']] += 1
        if row['source'] == 'Arkade 5':
            self.by_arkade_test[row['test_id']] += 1
        self.by_source[row['source']] += 1
        if len(self.preview) < self.preview_limit:
            self.preview.append({k: row[k] for k in ('source', 'test_id', 'severity', 'message',
                                                     'professional_status')})

    def summary(self) -> dict:
        return {'total': self.count, 'reviewed': self.reviewed,
                'unreviewed': self.count - self.reviewed,
                'errors': self.severity['ERROR'], 'warnings': self.severity['WARNING'],
                'review_points': self.severity['REVIEW'], 'manual': self.manual,
                'by_severity': dict(sorted(self.severity.items())),
                'by_test': dict(sorted(self.by_test.items())),
                'by_arkade_test': dict(sorted(self.by_arkade_test.items())),
                'by_source': dict(sorted(self.by_source.items())),
                'automatic_approval': False}

    def close(self) -> None:
        self.jsonl_file.close()
        self.csv_file.close()


def _h(value: Any) -> str:
    return escape(str(value if value is not None else ''), quote=True)


def _html(summary: dict, preview: list[dict], job_id: str, export_relative: str) -> str:
    arkade_tests = summary['by_arkade_test']
    displayed_tests = sorted(arkade_tests.items())[:MAX_TESTS_INLINE]
    counts = ''.join('<tr><td>' + _h(k) + '</td><td>' + str(n) + '</td></tr>'
                     for k, n in displayed_tests)
    rows = ''.join('<tr><td>' + _h(item['source']) + '</td><td>' +
                   _h(item['test_id']) + '</td><td>' + _h(item['severity']) +
                   '</td><td>' + _h(item['message'][:500]) + (' … (forkortet i forhåndsvisning)' if len(item['message']) > 500 else '') + '</td><td>' +
                   _h(item['professional_status']) + '</td></tr>' for item in preview)
    count_label = ('Viser de første ' + str(len(preview)) + ' av ' + str(summary['total']) +
                   ' funn.' if len(preview) < summary['total'] else
                   'Viser alle ' + str(summary['total']) + ' funn.')
    link = _h(export_relative)
    return ("<!doctype html><html lang='no'><head><meta charset='utf-8'>"
            "<title>Noark 5 KS-grunnlag (UTKAST)</title>"
            "<style>body{font:15px/1.5 Segoe UI,Arial,sans-serif;max-width:1100px;"
            "margin:2em auto;padding:0 1em}td,th{padding:7px;border:1px solid #c8d1da;"
            "vertical-align:top}table{border-collapse:collapse;width:100%}"
            "th{background:#f1f5f9;text-align:left}p{max-width:88ch}</style></head><body>"
            "<h1>KS-grunnlag - UTKAST, IKKE GODKJENT</h1>"
            "<p>Jobb: " + _h(job_id) + ". Ingen automatisk depotgodkjenning.</p>"
            "<p><b>Funn totalt:</b> " + str(summary['total']) +
            "; feil: " + str(summary['errors']) + "; advarsler: " +
            str(summary['warnings']) + "; vurdert: " + str(summary['reviewed']) +
            "; åpne: " + str(summary['unreviewed']) + ".</p>"
            "<p>Eksterne Arkade-funn er kilderapporterte og ikke uavhengig verifisert av DWM. "
            "Faglige vurderinger endrer ikke teknisk teststatus.</p>"
            "<p><b>Fullstendig register:</b> <a href='" + link + "/funn.csv'>CSV (alle funn)</a> "
            "og <a href='" + link + "/funn.jsonl'>JSONL (alle funn)</a>. "
            "Begge er kildebundet til manifest og original Work-evidens.</p>"
            "<h2>Antall per Arkade 5-test</h2><p>" + ("Viser de første 250 testene av " + str(len(arkade_tests)) + ". Komplett antall finnes i JSON-rapportgrunnlaget." if len(arkade_tests) > MAX_TESTS_INLINE else "Alle Arkade-testgrupper er vist.") + "</p><table><tr><th>Test-ID</th><th>Funn</th></tr>"+
            (counts or '<tr><td colspan=2>Ingen funn</td></tr>') + "</table>"
            "<h2>Forhåndsvisning</h2><p>" + _h(count_label) + "</p>"
            "<table><tr><th>Kilde</th><th>Test</th><th>Nivå</th><th>Funn</th>"
            "<th>Faglig status</th></tr>" + (rows or '<tr><td colspan=5>Ingen funn</td></tr>') +
            '</table></body></html>\n')


def _large_pronom_raf_candidates(path: Path, source_ref: str, digest: str) -> Iterator[dict]:
    """Stream historical RAF-220301 observations for PRONOM files >20 MiB.

    This is only a *historical source observation*, never a current normative
    PRONOM verdict, and avoids the legacy QA reader's 20 MiB all-at-once cap.
    """
    try:
        import ijson
    except ImportError as exc:
        raise A260CapacityError('Mangler ijson for stor PRONOM-evidens') from exc
    declared_type = ''
    original_name = ''
    current = None
    with path.open('rb') as inp:
        for prefix, event, value in ijson.parse(inp):
            if prefix == 'evidence_type' and event == 'string':
                declared_type = str(value)
            elif prefix == 'source.original_name' and event == 'string':
                original_name = _text(value)
            elif prefix == 'csv.rows.item' and event == 'start_map':
                current = {}
            elif current is not None and prefix.startswith('csv.rows.item.') and event in (
                    'string', 'null', 'number', 'integer', 'boolean'):
                key = prefix.rsplit('.', 1)[-1]
                if key in ('RAF-220301', 'Format-ID', 'Antall', 'Filtype', 'Formatversjon'):
                    current[key] = _text(value)
            elif prefix == 'csv.rows.item' and event == 'end_map':
                if current is None:
                    raise A260CapacityError('Ugyldig PRONOM-rad')
                if str(current.get('RAF-220301') or '').casefold() == 'ikke gyldig':
                    puid = str(current.get('Format-ID') or '').strip()
                    count = str(current.get('Antall') or '').strip()
                    if puid and count.isdecimal():
                        yield {
                            'source': 'Arkade 5 – historisk RAF-220301 (PRONOM)',
                            'test_id': 'RAF-220301:' + puid,
                            'severity': 'REVIEW',
                            'message': 'Historisk RAF-220301: Ikke gyldig – ' + puid +
                                       '. Filobservasjoner: ' + count +
                                       '. Vurder mot dagens valgt regelprofil separat; ikke automatisk filfeil.',
                            'context': str(current.get('Filtype') or '') + ' / ' +
                                       str(current.get('Formatversjon') or 'Ukjent'),
                            'file': original_name,
                            'lines': [], 'source_ref': source_ref, 'requires_review': True,
                        }
                current = None
    if declared_type != 'arkade5_pronom_format_statistics':
        raise A260CapacityError('Ukjent PRONOM-evidenstype')
    if _sha(path) != digest:
        raise A260CapacityError('PRONOM-evidens ble endret under lesing')


def _manual_and_depot_findings(work: Path, identity: dict, depot_path: Path,
                               depot_rel: str, depot: dict, arkade_rel: str = '',
                               pronom_ref: dict | None = None) -> Iterator[dict]:
    """Fallback when the old snapshot cannot load a large Arkade file.

    Preserve DWM depot deviations, non-OK XPath test statuses, archive parts,
    and independently recorded manual observations.  RAF-specific candidates
    are not reinterpreted here; keep source families separate in the manifest.
    """
    from .qa_delivery_v023_a11 import AGGREGATE_CATEGORIES
    complete_delivery = bool((depot.get('delivery_validation') or {}).get('complete'))
    for dev in depot.get('deviations') or ():
        if not isinstance(dev, dict):
            continue
        if complete_delivery and dev.get('category') in AGGREGATE_CATEGORIES:
            # Full individual records are streamed separately by the a11 bridge.
            continue
        yield {'source': 'DWM depotvalidering',
               'test_id': str(dev.get('category') or 'unknown'),
               'severity': str(dev.get('severity') or 'REVIEW').upper(),
               'message': str(dev.get('summary') or 'Ingen beskrivelse'),
               'context': '', 'file': '', 'lines': [], 'source_ref': depot_rel,
               'requires_review': bool(dev.get('requires_review'))}
    for row in (depot.get('technical_validation') or {}).get('tests') or ():
        if not isinstance(row, dict):
            continue
        state = str(row.get('status') or '').casefold()
        if state in ('', 'ok', 'pass', 'passed', 'success', 'legacy_disabled'):
            continue
        test_id = str(row.get('test_id') or row.get('legacy_job_id') or '')
        if not test_id:
            continue
        level = 'ERROR' if state in ('error', 'fail', 'failed') else 'WARNING' if state in ('warning', 'warn') else 'REVIEW'
        yield {'source': 'DWM – XPath-kontroll (lagret teknisk resultat)',
               'test_id': test_id, 'severity': level,
               'message': 'DWM-kontroll har status ' + state + '. Undersøk kildetesten og årsaken; ikke automatisk depotvedtak.',
               'context': str(row.get('test_point') or ''), 'file': '', 'lines': [],
               'source_ref': depot_rel, 'requires_review': True}
    for item in depot.get('archive_parts') or ():
        if not isinstance(item, dict):
            continue
        part = item.get('archive_part') or {}
        if not isinstance(part, dict):
            continue
        if 'aktiv' in str(part.get('status') or '').casefold():
            yield {'source': 'DWM arkivdelstatus', 'test_id': 'arkivdel.active_period',
                   'severity': 'REVIEW',
                   'message': 'Archive part has an active period at delivery; human review required.',
                   'context': str(part.get('title') or '') + ' (' + str(part.get('system_id') or '') + ')',
                   'file': '', 'lines': [], 'source_ref': depot_rel, 'requires_review': True}
    from noark5_workflow.reporting.qa_workflow_v022_a3 import (
        manual_findings, _verified_raf_candidates,
    )
    manifest = [{'kind': 'dwm_depot', 'path': depot_rel,
                 'sha256': _sha(depot_path)}]
    if pronom_ref and pronom_ref.get('file'):
        pronom_path = _secure_work_file(work, pronom_ref['file'])
        if _sha(pronom_path) != pronom_ref.get('sha256'):
            raise A260CapacityError('PRONOM-kildehash stemmer ikke')
        manifest.append({'kind': 'external', 'path': pronom_ref['file'],
                         'sha256': pronom_ref['sha256']})
    stub = {'model_id': 'ikamr.dwm.noark5.qa-decision.a12.v1',
            'work_identity': {'job_uid': identity['job_uid']},
            'evidence_manifest': manifest, 'arkade': {'source': arkade_rel}}
    for row in manual_findings(work, stub):
        yield row
    if pronom_ref and pronom_ref.get('file') and pronom_path.stat().st_size > 20 * 1024 * 1024:
        yield from _large_pronom_raf_candidates(
            pronom_path, pronom_ref['file'], pronom_ref['sha256'])
    else:
        for row in _verified_raf_candidates(work, stub):
            yield row


def _reviews(work: Path, identity: dict, depot_hash: str) -> dict[str, dict]:
    """Latest verified event per fingerprint, streamed from the original ledger.

    A14 handles unlimited historic events without an in-memory history list.
    Sorting by the original immutable timestamp prevents filesystem order
    from changing an already recorded professional assessment.
    """
    import importlib
    review_api = importlib.import_module('.qa_review_v021_a13', __package__)
    reader = getattr(review_api, '_iter_events', None) or review_api._read_events
    selected: dict[str, dict] = {}
    ranks: dict[str, tuple[int, str, int]] = {}
    for sequence, ev in enumerate(reader(work), 1):
        if ev.get('job_uid') != identity['job_uid'] or ev.get('depot_report_sha256') != depot_hash:
            continue
        key = str(ev.get('finding_key') or '')
        stamp = ev.get('recorded_ns')
        rank = ((stamp, str(ev.get('event_id') or ''), 0)
                if type(stamp) is int else (0, '', sequence))
        if key not in ranks or rank > ranks[key]:
            selected[key] = ev
            ranks[key] = rank
    return selected


def build_qa_basis_a6(work: str | Path, *, job_id: str = '') -> dict:
    """A260 output: immutable full exports, short HTML, source SHA + review binding.

    A220, A230 and A250 must have run first. Standard snapshot is preferred
    when safe; otherwise a source-verified streaming path avoids the 300-issue
    and 20 MiB *preview* limits in the old A260 adapter.
    """
    from noark5_workflow.operations.canonical_evidence_v022_a7 import (
        ROOT_NAME, _read, _work_identity,
    )
    from noark5_workflow.reporting.qa_workflow_v022_a3 import build_review_snapshot_v022_a3
    from noark5_workflow.reporting.qa_decision_v021_a12 import _find_depot, _json, MAX_DEPO

    root, identity = _work_identity(Path(work), job_id)
    evidence_dir = root / ROOT_NAME
    audit_path = evidence_dir / 'evidence-audit.json'
    audit = _read(audit_path)
    if audit.get('job_uid') != identity['job_uid']:
        raise A260CapacityError('Evidensrevisjonen tilhører feil Work-jobb')
    canonical = _read(evidence_dir / 'canonical-results.json')
    if (canonical.get('extraction') or {}).get('stable_id') != identity['job_uid']:
        raise A260CapacityError('Kanonisk kilderesultat tilhører feil Work-jobb')
    selected = (canonical.get('a7_evidence_sources') or {}).get('arkade_noark') or {}
    arkade_rel = str(selected.get('file') or '')
    arkade_path = None
    declared = str(selected.get('sha256') or '')
    if arkade_rel:
        if (not arkade_rel.startswith('external_evidence/arkade5/') or
                not arkade_rel.endswith('/normalized/arkade5_results.json') or
                len(declared) != 64):
            raise A260CapacityError('Ukjent eller manglende Arkade-evidensidentitet')
        arkade_path = _secure_work_file(root, arkade_rel)
        if _sha(arkade_path) != declared:
            raise A260CapacityError('Arkade-evidens har endret SHA-256')
    # Compatibility for older synthetic/legacy workflows that did not create
    # a depot report. Preserve the historical no-approval behavior there.
    # Real A260 depot workflows use the full streaming export below.
    if not (root / 'noark5_reports/depot_validation').is_dir():
        from noark5_workflow.operations.canonical_evidence_v022_a7 import (
            _build_qa_basis_legacy_v022_a7,
        )
        return _build_qa_basis_legacy_v022_a7(root, job_id=job_id)
    depot_path, depot_rel = _find_depot(root, None)
    large_depot = depot_path.stat().st_size > MAX_DEPO
    if large_depot:
        from .qa_depot_stream_v023_a17 import project_depot_report
        depot, parsed_digest = project_depot_report(depot_path)
        if parsed_digest != _sha(depot_path):
            raise A260CapacityError('Depotrapporten endret seg under A260-lesing')
    else:
        depot = _json(depot_path, MAX_DEPO)
    if depot.get('report_type') != 'noark5_depot_validation':
        raise A260CapacityError('Ukjent depotvalideringsrapport')
    if not depot_path.parent.name.startswith(identity['job_id'] + '__'):
        raise A260CapacityError('Depotrapporten tilhører en annen jobb')
    imports = ((depot.get('external_validation') or {}).get('arkade5') or {}).get('imports') or []
    if arkade_rel and imports and not any(
            isinstance(item, dict) and item.get('normalized_file') == arkade_rel
            for item in imports):
        raise A260CapacityError('A220-valgt Arkade-evidens er ikke koblet til depotrapporten')
    depot_sha = _sha(depot_path)
    reviews = _reviews(root, identity, depot_sha)
    from .qa_delivery_v023_a11 import (
        DELIVERY_SOURCES, AGGREGATE_CATEGORIES,
        _binding as _delivery_binding, iter_verified_delivery,
    )
    delivery_binding = _delivery_binding(root, depot_rel, depot, identity['job_uid'])

    # Use all normal DWM/manual/RAF findings when its existing bounded snapshot
    # is available.  For huge Arkade inputs, rebuild the DWM-only components
    # without materializing tens of thousands of Arkade findings in RAM.
    snapshot = None
    # Avoid re-reading large source registers just to create an A260 preview.
    # The full DWM stream below remains mandatory and is verified to EOF.
    small_arkade = arkade_path is None or arkade_path.stat().st_size <= 4 * 1024 * 1024
    small_delivery = (delivery_binding is None or not delivery_binding.get('complete')
                      or delivery_binding['count'] <= 250)
    try:
        if small_arkade and small_delivery and not large_depot:
            snapshot = build_review_snapshot_v022_a3(work=root)
    except Exception as exc:
        message = str(exc)
        known = ('Too many Arkade findings', 'Flere Arkade-funn enn sikker rapportgrense',
                 'Too many review findings', 'Evidensfil er for stor:',
                 'Manglende, for stor eller utrygg rapportfil:',
                 'Ingen kanonisk Arkade-analyse')
        if not any(piece in message for piece in known):
            raise
    # A preview may never be mistaken for full A260 evidence.
    if snapshot is not None and snapshot.get('findings_complete') is False:
        snapshot = None
    if snapshot is not None:
        extras = (r for r in snapshot.get('findings') or ()
                  if (arkade_path is None or r.get('source') != 'Arkade 5')
                  and r.get('source') not in DELIVERY_SOURCES
                  and not (delivery_binding and delivery_binding.get('complete')
                           and r.get('source') == 'DWM depotvalidering'
                           and r.get('test_id') in AGGREGATE_CATEGORIES))
        depot_rel = str(snapshot.get('dwm_report_source') or depot_rel)
    else:
        extras = _manual_and_depot_findings(
            root, identity, depot_path, depot_rel, depot, arkade_rel,
            (canonical.get('a7_evidence_sources') or {}).get('arkade_pronom'))

    export_root = evidence_dir / 'a260_exports_v023_a6'
    if export_root.is_symlink():
        raise A260CapacityError('Utrygg eksportmappe')
    export_root.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.a260-stage-', dir=export_root))
    out = export_root / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:12])
    writer = None
    published = False
    try:
        writer = FindingWriter(stage / 'funn.jsonl', stage / 'funn.csv', reviewed_events=reviews)
        if arkade_path is not None:
            try:
                import ijson
            except ImportError as exc:
                raise A260CapacityError('Mangler ijson; kjør install.bat gui') from exc
            with arkade_path.open('rb') as inp:
                for row in iter_arkade_findings(ijson.parse(inp), source_ref=arkade_rel,
                                                source_sha=declared):
                    writer.add(row)
            if _sha(arkade_path) != declared:
                raise A260CapacityError('Arkade-kilden ble endret under A260')
        # Complete, separately source-bound DWM records, never the report
        # aggregates. Exhaust the stream so late SHA/count errors abort staging.
        for row in iter_verified_delivery(root, depot_rel, depot,
                                          job_uid=identity['job_uid']):
            writer.add(row)
        for item in extras:
            writer.add(item)
        summary = writer.summary()
        preview = list(writer.preview)
        writer.close()
        writer = None
        exports = {'jsonl': 'noark5_evidence/a260_exports_v023_a6/' + out.name + '/funn.jsonl',
                   'csv': 'noark5_evidence/a260_exports_v023_a6/' + out.name + '/funn.csv'}
        manifest = {'model_id': MODEL, 'job_uid': identity['job_uid'],
                    'source_arkade': arkade_rel or None, 'source_arkade_sha256': declared or None,
                    'depot_report': depot_rel, 'depot_report_sha256': depot_sha,
                    'evidence_audit_sha256': _sha(audit_path),
                    'summary': summary, 'files': {
                        'funn.jsonl': {'sha256': _sha(stage/'funn.jsonl'), 'bytes': (stage/'funn.jsonl').stat().st_size},
                        'funn.csv': {'sha256': _sha(stage/'funn.csv'), 'bytes': (stage/'funn.csv').stat().st_size}},
                    'source_families_separate': True, 'automatic_approval': False}
        if delivery_binding and delivery_binding.get('complete'):
            manifest['source_delivery'] = {
                'findings': delivery_binding['jsonl_relative'],
                'findings_sha256': delivery_binding['jsonl_sha256'],
                'csv': delivery_binding['csv_relative'],
                'csv_sha256': delivery_binding['csv_sha256'],
                'source_xml_sha256': delivery_binding['source_xml_sha256'],
                'noark_version': delivery_binding['version'],
                'finding_count': delivery_binding['count'],
            }
        (stage / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False,
                                                 indent=2) + '\n', encoding='utf-8')
        # Destination is a uniquely named new directory, never overwrite an old export.
        os.replace(stage, out)
        published = True
        doc = {'model_id': 'dwm.noark5.qa-basis.draft.a7.v1',
               'dependency_no': 260, 'job_uid': identity['job_uid'],
               'status': 'UTKAST', 'automatic_approval': False,
               'evidence_audit_sha256': _sha(audit_path),
               'depot_report_source': depot_rel, 'findings': summary,
               'exports': exports, 'export_manifest': exports['jsonl'].rsplit('/',1)[0] + '/manifest.json',
               'source_arkade_sha256': declared or None,
               'archive_creator_acceptance': None, 'depot_approval': None,
               'note': 'Fullstendig kildebundet funnregister. Teknisk status ikke endret; beslutning krever faglig behandling.'}
        # Publish pointers last; an export is never advertised before its files exist.
        _atomic_replace(evidence_dir / 'qa-basis-draft.json', json.dumps(doc, ensure_ascii=False,
                          indent=2) + '\n')
        _atomic_replace(evidence_dir / 'qa-basis-draft.html',
                        _html(summary, preview, identity['job_id'],
                              'a260_exports_v023_a6/' + out.name))
        return {'path': str(evidence_dir/'qa-basis-draft.json'),
                'html': str(evidence_dir/'qa-basis-draft.html'),
                'summary': summary, 'exports': exports, 'automatic_approval': False}
    finally:
        if writer is not None:
            writer.close()
        if not published:
            shutil.rmtree(stage, ignore_errors=True)


def _atomic_replace(path: Path, data: str) -> None:
    if path.is_symlink():
        raise A260CapacityError('Utrygg A260-utdatafil')
    fd, temp = tempfile.mkstemp(prefix='.a260-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
