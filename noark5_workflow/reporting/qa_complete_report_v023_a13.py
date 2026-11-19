"""A13: complete source-bound KS and depot report package from the A12 index.

All findings are streamed to independent recipient-specific HTML, JSONL and
CSV. Only professional comments explicitly selected for a recipient are shown
in that recipient's report. Neither technical outcomes nor Source are changed.
The whole package is atomically published after final source/review rechecks.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Callable, Iterable

from .qa_paged_review_v023_a12 import (
    MODEL as PAGED_MODEL, PagedReviewError, _identity, _open_index,
    finding_key, load_review_events,
)

MODEL = 'dwm.noark5.ks-depot-complete-report.a13.v1'
MAX_PAGE_ROWS = 1000
DEFAULT_PAGE_ROWS = 500
SECTION_IDS = frozenset(('summary', 'findings', 'parts', 'tests', 'sources'))
RECOMMENDATIONS = frozenset(('pending', 'clarify', 'accept', 'conditional', 'followup', 'reject'))
RECOMMENDATION_NAMES = {
    'pending': 'Ingen faglig innstilling registrert',
    'clarify': 'Krever videre avklaring',
    'accept': 'Foreslås godkjent (ikke vedtak)',
    'conditional': 'Foreslås godkjent med merknader (ikke vedtak)',
    'followup': 'Krever oppfølging eller korrigert uttrekk',
    'reject': 'Foreslås ikke godkjent (ikke vedtak)',
}
CSV_FIELDS = ('finding_uid', 'finding_key', 'source', 'test_id', 'severity',
              'message', 'context', 'file', 'lines', 'source_ref', 'metadata_id',
              'xpath', 'object_id', 'archive_part_id', 'technical_status',
              'professional_status', 'review_comment', 'reviewed_by',
              'reviewed_at', 'review_selected_for_report')
STYLE = '''<style>
body{font:14px/1.55 'Segoe UI',Arial,sans-serif;max-width:1350px;margin:24px auto;padding:0 22px;color:#1a2c3b}
h1{font-size:27px}h2{margin-top:27px;font-size:19px}a{color:#15608f}
.notice{border-left:4px solid #ae7924;background:#fff4d7;padding:12px 16px}
table{width:100%;border-collapse:collapse;margin:12px 0 18px;table-layout:fixed}
th,td{border:1px solid #d7dfe6;text-align:left;padding:7px;vertical-align:top;overflow-wrap:anywhere}
th{background:#eef2f6}.small{font-size:12px;color:#536273}
nav{display:flex;gap:18px;flex-wrap:wrap;margin:18px 0}.muted{color:#536273}
@media print{body{max-width:none;margin:12mm;font-size:11pt}tr{break-inside:avoid}}
</style>'''


class CompleteReportError(ValueError):
    """Incomplete, changed or foreign sources must never produce an approved report."""


def _hash_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _h(value) -> str:
    return escape(str(value if value is not None else ''), quote=True)


def _csv_cell(value) -> str:
    if isinstance(value, (list, tuple, dict)):
        text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    else:
        text = '' if value is None else str(value)
    # Prevent formula execution when opened in spreadsheet applications.
    trimmed = text.lstrip()
    if (trimmed.startswith(('=', '+', '-', '@'))
            or text.startswith(('\t', '\n', '\r'))):
        return "'" + text
    return text


def _event_revision(reviews: dict[str, dict]) -> str:
    """Snapshot the existing append-only review events, never write a second ledger."""
    h = sha256()
    for key, event in sorted(reviews.items()):
        h.update(key.encode('ascii'))
        h.update(json.dumps(event, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':')).encode('utf-8'))
        h.update(b'\n')
    return h.hexdigest()


def _check_cancel(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise CompleteReportError('Rapporteksport avbrutt – ingen ufullstendig rapport publisert')


def _check_binding(work: str | Path, snapshot: dict, index: dict) -> tuple[Path, Path]:
    if (not isinstance(index, dict) or index.get('model_id') != PAGED_MODEL
            or index.get('complete') is not True):
        raise CompleteReportError('Komplett A12-indeks mangler')
    root, db = _open_index(work, index, digest=True)
    uid, depot_rel, depot_sha, _ = _identity(root, snapshot)
    if (uid != index.get('job_uid') or depot_rel != index.get('depot_report_relative')
            or depot_sha != index.get('depot_sha256')):
        raise CompleteReportError('Rapportindeks og valgt Work-jobb har ulik identitet')
    return root, db


def _safe_destination(work: Path, destination: str | Path) -> Path:
    from .qa_decision_v021_a13 import _safe_destination as protect
    target = Path(destination).resolve(strict=False)
    job_file = work / 'job.json'
    if job_file.is_symlink() or job_file.stat().st_size > 2 * 1024 * 1024:
        raise CompleteReportError('Utrygg Work-jobbdefinisjon')
    job = json.loads(job_file.read_text(encoding='utf-8-sig'))
    protect(target, work, job, ())
    return target


def _review_fields(original: dict, event: dict | None, scope: str) -> dict:
    """Show technical evidence in both, but private review text in selected report only."""
    row = dict(original)
    for stale in ('review_status', 'review_comment', 'professional_status',
                  'reviewed_by', 'reviewed_at', 'include_in_ks', 'include_in_depot',
                  'review_selected_for_report'):
        row.pop(stale, None)
    selected = bool(event and event.get('include_in_' + scope) is True)
    if not event:
        status = 'Ikke vurdert'
    elif not selected:
        status = 'Faglig vurdering finnes, men er ikke valgt til denne rapporten'
    else:
        status = str(event.get('status') or '')
    row.update(technical_status=str(original.get('severity') or ''),
               professional_status=status,
               review_comment=str(event.get('comment') or '') if selected else '',
               reviewed_by=str((event.get('author') or {}).get('display_name') or '') if selected else '',
               reviewed_at=str(event.get('created_utc') or '') if selected else '',
               review_selected_for_report=selected)
    return row


def _html_start(title: str) -> str:
    return ('<!doctype html><html lang="no"><head><meta charset="utf-8"><title>'
            + _h(title) + '</title>' + STYLE + '</head><body>')


def _nav(scope: str, n: int, pages: int) -> str:
    nav = ['<nav><a href="../' + scope + '-rapport-utkast.html">Rapportoversikt</a>']
    if n > 1:
        nav.append('<a href="side-' + f'{n-1:06d}' + '.html">Forrige side</a>')
    if n < pages:
        nav.append('<a href="side-' + f'{n+1:06d}' + '.html">Neste side</a>')
    return ' · '.join(nav) + '</nav>'


class _ScopeWriter:
    """One independent, recipient-filtered output; O(page_size) HTML memory."""
    def __init__(self, root: Path, scope: str, total: int, page_rows: int):
        self.scope, self.total, self.page_rows = scope, total, page_rows
        self.root = root
        self.pages = max(1, (total + page_rows - 1) // page_rows)
        self.folder = root / (scope + '-detaljer')
        self.folder.mkdir()
        self.json_fp = (root / (scope + '-funn.jsonl')).open('x', encoding='utf-8', newline='\n')
        self.csv_fp = (root / (scope + '-funn.csv')).open('x', encoding='utf-8-sig', newline='')
        self.csv_writer = csv.DictWriter(self.csv_fp, CSV_FIELDS, delimiter=';',
                                         lineterminator='\r\n', extrasaction='ignore')
        self.csv_writer.writeheader()
        self.page_fp = None
        self.page_number = 0
        self.count = 0
        self.selected_reviews = 0

    def _start_page(self, number: int) -> None:
        self._close_page()
        self.page_number = number
        path = self.folder / f'side-{number:06d}.html'
        self.page_fp = path.open('x', encoding='utf-8', newline='\n')
        self.page_fp.write(_html_start(self.scope.upper() + ' – funn side ' + str(number)))
        self.page_fp.write('<h1>Komplett ' + self.scope.upper() + '-funnregister – side '
                           + str(number) + ' av ' + str(self.pages) + '</h1>'
                           '<p class="notice">UTKAST – ingen formell depotgodkjenning. '
                           'Teknisk status er bevart uendret.</p>'
                           + _nav(self.scope, number, self.pages) +
                           '<table><thead><tr><th>Nr.</th><th>Kontroll og kilde</th>'
                           '<th>Nivå</th><th>Funn og XML-spor</th><th>Faglig vurdering valgt til rapporten</th>'
                           '</tr></thead><tbody>')

    def _close_page(self) -> None:
        if self.page_fp is not None:
            if self.count == 0:
                self.page_fp.write('<tr><td colspan="5">Ingen registrerte funn</td></tr>')
            self.page_fp.write('</tbody></table>' + _nav(self.scope, self.page_number, self.pages)
                               + '</body></html>\n')
            self.page_fp.close()
            self.page_fp = None

    def add(self, original: dict, event: dict | None) -> None:
        ordinal = self.count + 1
        page = (ordinal - 1) // self.page_rows + 1
        if page != self.page_number:
            self._start_page(page)
        row = _review_fields(original, event, self.scope)
        self.json_fp.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        self.csv_writer.writerow({k: _csv_cell(row.get(k)) for k in CSV_FIELDS})
        self.selected_reviews += int(row['review_selected_for_report'])
        xml_trace = ('<b>XML:</b> ' + _h(row.get('file')) + ' · linje ' + _h(row.get('lines'))
                     + '<p><b>XPath:</b> ' + _h(row.get('xpath'))
                     + '</p><p><b>Objekt:</b> ' + _h(row.get('object_id'))
                     + ' · <b>Arkivdel:</b> ' + _h(row.get('archive_part_id'))
                     + '</p><p class="small"><b>Work:</b> ' + _h(row.get('source_ref'))
                     + ' · SHA/UID: ' + _h(row.get('finding_uid') or row.get('finding_key')) + '</p>')
        comment = '<b>' + _h(row['professional_status']) + '</b>'
        if row['review_comment']:
            comment += '<p>' + _h(row['review_comment']) + '</p><p class="small">' + _h(row['reviewed_by']) + ' · ' + _h(row['reviewed_at']) + '</p>'
        self.page_fp.write('<tr><td>' + str(ordinal) + '</td><td><b>'
                           + _h(row.get('test_id')) + '</b><p>' + _h(row.get('source'))
                           + '</p></td><td>' + _h(row.get('severity')) + '</td><td>'
                           + _h(row.get('message')) + '<p>' + _h(row.get('context'))
                           + '</p>' + xml_trace + '</td><td>' + comment + '</td></tr>\n')
        self.count += 1

    def finish(self) -> None:
        if self.page_fp is None:
            self._start_page(1)
        self._close_page()
        self.json_fp.close()
        self.csv_fp.close()
        if self.count != self.total:
            raise CompleteReportError('Antall eksporterte funn stemmer ikke med komplett A12-indeks')

    def abort(self) -> None:
        for fp in (self.page_fp, self.json_fp, self.csv_fp):
            if fp is not None and not fp.closed:
                fp.close()


def _summary_table(rows: Iterable[tuple[str, object]]) -> str:
    return ('<table><tbody>' + ''.join('<tr><th>' + _h(a) + '</th><td>' + _h(b) + '</td></tr>'
                                      for a, b in rows) + '</tbody></table>')


def _section_for_parts(snapshot: dict) -> str:
    parts = snapshot.get('archive_parts') or []
    if not parts:
        return '<p>Ingen arkivdelsopplysninger tilgjengelige i rapportgrunnlaget.</p>'
    rows = ['<table><tr><th>systemID</th><th>Arkivdel</th><th>Status</th><th>Start</th><th>Slutt</th></tr>']
    for part in parts:
        if not isinstance(part, dict):
            continue
        rows.append('<tr><td>' + _h(part.get('system_id') or part.get('id'))
                    + '</td><td>' + _h(part.get('title')) + '</td><td>' + _h(part.get('status'))
                    + '</td><td>' + _h(part.get('period_start') or part.get('archive_period_start_date'))
                    + '</td><td>' + _h(part.get('period_end') or part.get('archive_period_end_date'))
                    + '</td></tr>')
    return ''.join(rows) + '</table>'


def _overview_page(scope: str, snapshot: dict, index: dict, *, stats: dict,
                   reviews_in_scope: int, total_reviews: int,
                   sections: frozenset[str], recommendation: str,
                   note: str, page_rows: int, preview_only: bool = False) -> str:
    total = index['finding_count']
    pages = max(1, (total + page_rows - 1) // page_rows)
    ident = snapshot.get('work_identity') or {}
    title = 'KS-rapport til arkivskaper' if scope == 'ks' else 'Depotets validerings- og ferdigstillingsrapport'
    html = [_html_start(title + ' – UTKAST'), '<h1>' + _h(title) + ' – UTKAST</h1>',
            '<p><b>Jobb:</b> ' + _h(ident.get('job_id')) + ' · ' + _h(ident.get('job_name')) + '</p>',
            '<p class="notice"><strong>IKKE GODKJENT.</strong> Dette er et kildesporbart rapportutkast. '
            'Ingen automatisk arkivskaperaksept eller formelt depotvedtak. '
            'Faglige vurderinger endrer ikke teknisk teststatus.</p>']
    if 'summary' in sections:
        html += ['<h2>Komplett funnstatus</h2>', _summary_table((
            ('Alle funn (ingen avkorting)', total),
            ('Faglig vurdert totalt', total_reviews),
            ('Faglige vurderinger valgt til denne rapporten', reviews_in_scope),
            ('Gjenstående uten faglig vurdering', total - total_reviews),
            ('Teknisk FEIL', stats['severity'].get('ERROR', 0)),
            ('Teknisk WARNING', stats['severity'].get('WARNING', 0)),
            ('REVIEW', stats['severity'].get('REVIEW', 0)),
            ('Innstilling (ikke vedtak)', RECOMMENDATION_NAMES[recommendation]),
            ('Begrunnelse for innstilling', note or 'Ikke registrert')))]
    if 'summary' in sections:
        html += ['<h2>Funn fordelt på kildefamilie</h2>',
                 '<table><thead><tr><th>Kilde</th><th>Funn</th></tr></thead><tbody>'
                 + ''.join('<tr><td>' + _h(source) + '</td><td>' + str(count)
                           + '</td></tr>' for source, count in
                           sorted((stats.get('source') or index.get('source_counts') or {}).items()))
                 + '</tbody></table>',
                 '<p class="small">Arkade 5 er ekstern, kilderapportert evidens. '
                 'DWM-kontroller, historiske sammenligninger og faglige vurderinger '
                 'har ulike roller og skal ikke likestilles med formell godkjenning.</p>']
    if preview_only:
        html += ['<h2>Forhåndsvisning av komplett opptelling</h2>',
                 '<p>Dette er bare en verifisert oppsummering. ' 
                 'Funnregisteret og alle valgte faglige kommentarer blir tilgjengelige ' 
                 'i HTML/JSONL/CSV når rapportpakken eksporteres. ' 
                 'Ingen enkeltfunn vises eller forkortes som en full rapport her.</p>']
    elif 'findings' in sections:
        html += ['<h2>Alle funn og faglige vurderinger</h2>',
                 '<p><b>Ingen funn er utelatt fra det tekniske registeret.</b> '
                 'Bare kommentarer valgt til denne rapporttypen vises.</p>',
                 '<p><a href="' + scope + '-detaljer/side-000001.html">'
                 'Åpne sidevis, fullstendig HTML-register (' + str(pages) + ' sider)</a></p>',
                 '<p><a href="' + scope + '-funn.csv">Alle funn i CSV</a> · '
                 '<a href="' + scope + '-funn.jsonl">Alle funn i JSONL</a></p>',
                 '<details><summary>Vis lenker til alle HTML-sider</summary><p>'
                 + ' · '.join('<a href="' + scope + '-detaljer/side-' + f'{n:06d}' + '.html">'
                            + str(n) + '</a>' for n in range(1, pages+1)) + '</p></details>']
    elif not preview_only:
        html += ['<h2>Fullstendig funnregister</h2>',
                 '<p>Presentasjonsseksjonen «Funn» er skjult, men alle funn er likevel eksportert.</p>',
                 '<p><a href="' + scope + '-funn.csv">CSV – alle funn</a> · '
                 '<a href="' + scope + '-funn.jsonl">JSONL – alle funn</a> · '
                 '<a href="' + scope + '-detaljer/side-000001.html">HTML – alle funn</a></p>']
    if 'parts' in sections:
        html += ['<h2>Arkivdeler og perioder (lagret kildegrunnlag)</h2>', _section_for_parts(snapshot)]
    if 'tests' in sections:
        technical = snapshot.get('dwm_technical') or {}
        html += ['<h2>Teknisk valideringsstatus</h2>',
                 '<p>Teknisk status er rapportert uendret fra den valgte DWM-depotrapporten.</p>',
                 _summary_table((('Status', technical.get('status') or 'Ikke dokumentert'),
                                 ('Kilde', index['depot_report_relative']),
                                 ('SHA-256', index['depot_sha256'])))]
    if 'sources' in sections:
        html += ['<h2>Kildebelegg og integritet</h2>',
                 _summary_table((('A12-indeks', index['index_relative_path']),
                                 ('Indeks-SHA-256', index['index_sha256']),
                                 ('Depotrapport-SHA-256', index['depot_sha256']),
                                 ('Vurderingshistorikk', 'Eksisterende, integritetskontrollert append-only-register'))),
                 '<p><a href="evidensmanifest.json">Fullt evidensmanifest med SHA-256</a></p>']
    html += ['<p class="small">Rapportpakken inneholder alle tekniske funn. '
             'Ingen formell beslutning eller AIP er produsert av denne funksjonen.</p>',
             '</body></html>\n']
    return ''.join(html)


def preview_complete_summary(work: str | Path, snapshot: dict, index: dict, *,
                             sections: Iterable[str] = SECTION_IDS,
                             recommendation: str = 'pending',
                             recommendation_note: str = '') -> str:
    """Bounded preview of VERIFIED full-register totals; never pretend to preview all rows."""
    root, _ = _check_binding(work, snapshot, index)
    reviews = load_review_events(root, index)
    options = frozenset(sections) & SECTION_IDS
    if not options or recommendation not in RECOMMENDATIONS:
        raise CompleteReportError('Ugyldig rapportutvalg')
    stats = {'severity': dict(index.get('severity_counts') or {})}
    return _overview_page('ks', snapshot, index, stats=stats,
                          reviews_in_scope=sum(bool(e.get('include_in_ks')) for e in reviews.values()),
                          total_reviews=len(reviews), sections=options,
                          recommendation=recommendation,
                          note=recommendation_note, page_rows=DEFAULT_PAGE_ROWS,
                          preview_only=True)


def export_complete_reports(work: str | Path, snapshot: dict, index: dict,
                            destination: str | Path, *,
                            sections: Iterable[str] = SECTION_IDS,
                            recommendation: str = 'pending',
                            recommendation_note: str = '',
                            page_rows: int = DEFAULT_PAGE_ROWS,
                            cancelled: Callable[[], bool] | None = None,
                            progress: Callable[[int], None] | None = None) -> dict:
    """Atomic complete KS/depot reports, source-bound to one Work job/revision.

    Every row is exported to both recipient-specific registers and HTML pages.
    The original review ledger remains authoritative. Before publication, both
    original source hashes and the current review revision are rechecked.
    """
    if (type(page_rows) is not int or not 1 <= page_rows <= MAX_PAGE_ROWS):
        raise CompleteReportError('Ugyldig HTML-sidestørrelse')
    options = frozenset(sections) & SECTION_IDS
    if not options or recommendation not in RECOMMENDATIONS:
        raise CompleteReportError('Ugyldig rapportutvalg eller faglig innstilling')
    if not isinstance(recommendation_note, str) or len(recommendation_note) > 5000:
        raise CompleteReportError('Faglig begrunnelse er for lang')
    _check_cancel(cancelled)
    root, db = _check_binding(work, snapshot, index)
    target = _safe_destination(root, destination)
    reviews = load_review_events(root, index)
    before_revision = _event_revision(reviews)
    total = index['finding_count']
    if type(total) is not int or total < 0:
        raise CompleteReportError('A12 mangler verifisert funntotal')
    # Only create a private, disposable staging area AFTER all destination
    # protections have passed. There is no direct writing into the target.
    stage = Path(tempfile.mkdtemp(prefix='.dwm-a13-', dir=target.parent))
    writers = []
    committed = False
    try:
        ks = _ScopeWriter(stage, 'ks', total, page_rows)
        writers.append(ks)
        depot = _ScopeWriter(stage, 'depot', total, page_rows)
        writers.append(depot)
        counts = Counter()
        by_source = Counter()
        n = 0
        with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
            conn.execute('PRAGMA query_only=ON')
            for (payload,) in conn.execute('SELECT payload FROM findings ORDER BY priority, ordinal'):
                _check_cancel(cancelled)
                original = json.loads(payload)
                if (not isinstance(original, dict) or original.get('finding_key') != finding_key(original)
                        or not original.get('source') or not original.get('test_id')
                        or not original.get('message') or not original.get('severity')):
                    raise CompleteReportError('Indeksfunn har ugyldig kilde- eller vurderingsidentitet')
                event = reviews.get(original['finding_key'])
                ks.add(original, event)
                depot.add(original, event)
                counts[str(original['severity']).upper()] += 1
                by_source[str(original['source'])] += 1
                n += 1
                if n % 1000 == 0 and progress:
                    progress(n)
        if n != total:
            raise CompleteReportError(f'A12 oppgir {total} funn, men komplett eksport leste {n}')
        for writer in writers:
            writer.finish()
        _check_cancel(cancelled)
        # Recheck BOTH original evidence and append-only professional reviews.
        _check_binding(root, snapshot, index)
        after_reviews = load_review_events(root, index)
        if _event_revision(after_reviews) != before_revision:
            raise CompleteReportError('Faglige vurderinger endret seg under rapporteksport')
        if progress:
            progress(n)
        stats = {'severity': dict(sorted(counts.items())), 'source': dict(sorted(by_source.items()))}
        for scope, writer in (('ks', ks), ('depot', depot)):
            overview = _overview_page(scope, snapshot, index, stats=stats,
                                      reviews_in_scope=writer.selected_reviews,
                                      total_reviews=len(reviews), sections=options,
                                      recommendation=recommendation,
                                      note=recommendation_note, page_rows=page_rows)
            (stage / (scope + '-rapport-utkast.html')).write_text(overview, encoding='utf-8')
        generated = datetime.now(timezone.utc).isoformat(timespec='seconds')
        overview_json = {'model_id': MODEL, 'complete': True,
                         'report_status': 'UTKAST_IKKE_GODKJENT', 'automatic_approval': False,
                         'job_uid': index['job_uid'], 'depot_report_sha256': index['depot_sha256'],
                         'finding_count': n, 'reviewed_count': len(reviews),
                         'unreviewed_count': n-len(reviews),
                         'reviews_in_ks': ks.selected_reviews,
                         'reviews_in_depot': depot.selected_reviews,
                         'severity_counts': stats['severity'], 'source_counts': stats['source'],
                         'sections': sorted(options), 'recommendation_not_decision': recommendation,
                         'recommendation_note': recommendation_note,
                         'technical_status_unchanged': (snapshot.get('dwm_technical') or {}).get('status'),
                         'archive_parts': snapshot.get('archive_parts') or [],
                         'created_utc': generated}
        (stage / 'rapportgrunnlag.json').write_text(
            json.dumps(overview_json, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (stage / 'index.html').write_text(
            _html_start('KS og depot – komplett rapportpakke UTKAST')
            + '<h1>Samlet KS-/depotrapport – UTKAST</h1>'
            + '<p class="notice"><b>IKKE GODKJENT.</b> ' + str(n)
            + ' kildebundne funn, alle med i komplette registre. '
            'Menneskelige vurderinger endrer ikke teknisk status.</p>'
            + '<nav><a href="ks-rapport-utkast.html">KS-rapport til arkivskaper</a> · '
            '<a href="depot-rapport-utkast.html">Depotets rapportutkast</a> · '
            '<a href="rapportgrunnlag.json">Oppsummering JSON</a> · '
            '<a href="evidensmanifest.json">SHA-256-evidensmanifest</a></nav>'
            '<p>Kommentarer er inkludert bare når de er valgt for det aktuelle rapportutkastet.</p>'
            '</body></html>\n', encoding='utf-8')
        # Count and fingerprint every file, including each complete HTML page.
        published = {}
        for f in sorted(stage.rglob('*')):
            if f.is_file():
                relative = f.relative_to(stage).as_posix()
                published[relative] = {'sha256': _hash_file(f), 'bytes': f.stat().st_size}
        manifest = {'model_id': MODEL, 'complete': True, 'automatic_approval': False,
                    'report_status': 'UTKAST_IKKE_GODKJENT',
                    'work_job_uid': index['job_uid'], 'depot_report_relative': index['depot_report_relative'],
                    'depot_report_sha256': index['depot_sha256'],
                    'a12_index_relative': index['index_relative_path'],
                    'a12_index_sha256': index['index_sha256'],
                    'a12_source_files': index.get('source_files') or [],
                    'review_revision_sha256': before_revision,
                    'reviewed_finding_count': len(reviews),
                    'finding_count': n, 'html_pages_per_report': ks.pages,
                    'published_files': published, 'generated_utc': generated,
                    'limitations': ['Utkast; ingen formell godkjenning',
                                    'Faglige vurderinger endrer ikke teknisk teststatus',
                                    'Alle historiske vurderingshendelser i Work verifiseres ved eksport; tidsbruk avhenger av filsystem og antall hendelser']}
        (stage / 'evidensmanifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        _check_cancel(cancelled)
        # A late tamper/cancel must never leave an apparently complete target.
        _check_binding(root, snapshot, index)
        if _event_revision(load_review_events(root, index)) != before_revision:
            raise CompleteReportError('Vurderingsregisteret ble endret før publisering')
        if target.exists() or target.is_symlink():
            raise FileExistsError('Rapportmappen finnes allerede: ' + str(target))
        stage.rename(target)
        committed = True
        return {'directory': target, 'index': target / 'index.html',
                'ks_html': target / 'ks-rapport-utkast.html',
                'depot_html': target / 'depot-rapport-utkast.html',
                'manifest': target / 'evidensmanifest.json',
                'finding_count': n, 'reviewed_count': len(reviews),
                'reviews_in_ks': ks.selected_reviews,
                'reviews_in_depot': depot.selected_reviews,
                'status': 'UTKAST_IKKE_GODKJENT'}
    except (OSError, ValueError, TypeError, sqlite3.Error, UnicodeError) as exc:
        if isinstance(exc, CompleteReportError):
            raise
        raise CompleteReportError('Komplett rapporteksport feilet: ' + str(exc)) from exc
    finally:
        for writer in writers:
            writer.abort()
        if not committed:
            shutil.rmtree(stage, ignore_errors=True)
