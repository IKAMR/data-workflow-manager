"""A7: bounded PUID overview, keyset file drill-down, and durable copy receipts.

Derived exclusively from A6's identity-checked, read-only SQLite file index.
Technical identification, archival-format policy, and professional decisions
remain separate.  New copy history is stored in Work, not Source or the A6 index.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterable
import json
import os
import re
import sqlite3

from app.noark5_document_workbench_v027_a6 import (
    DocumentWorkbenchError, PSEUDO, _checked_db, _json, _linked, _run,
    _sha, _work, copy_selected_files,
)

HISTORY_MODEL = 'dwm.noark5.document-copy-history.v027-a7.v1'
HISTORY_FILE = 'noark5_evidence/document_copy_history_v027_a7.sqlite'
MAX_VIEW_GROUPS = 100_000
MAX_FILE_PAGE = 200
MAX_EXPORT_HISTORY = 250
SHA_PATTERN = re.compile(r'[a-f0-9]{64}\Z')


def mime_category(puid: str, format_name: str) -> tuple[str, str]:
    """Broad *display hint*, NOT a reported MIME identification.

    Avoid claiming a MIME type from filename alone.  Siegfried's retained
    format name informs a coarse bucket, with unknown kept explicitly unknown.
    """
    value = str(format_name or '').casefold()
    if puid in PSEUDO:
        return 'Ukjent', 'ukjent'
    if 'pdf' in value or 'portable document format' in value:
        return 'PDF', 'application/pdf'
    if any(x in value for x in ('jpeg', 'jpg', 'png', 'tiff', 'gif', 'bitmap',
                                'image', 'jpeg 2000', 'webp', 'heic')):
        return 'Bilde', 'image/*'
    if any(x in value for x in ('xml', 'schema definition', 'xsd', 'sgml')):
        return 'XML', 'application/xml'
    if 'json' in value:
        return 'Data', 'application/json'
    if any(x in value for x in ('csv', 'plain text', 'unicode text',
                                'text file', 'rich text', 'html', 'markdown')):
        return 'Tekst', 'text/*'
    if any(x in value for x in ('word', 'excel', 'powerpoint', 'power point',
                                'open document', 'opendocument', 'office',
                                'spreadsheet', 'presentation', 'rtf')):
        return 'Kontor', 'application/*'
    if any(x in value for x in ('wav', 'waveform', 'flac', 'mpeg audio',
                                'mp3', 'ogg audio', 'aiff', 'audio')):
        return 'Lyd', 'audio/*'
    if any(x in value for x in ('mpeg video', 'mp4', 'quicktime', 'matroska',
                                'avi ', 'video')):
        return 'Video', 'video/*'
    if any(x in value for x in ('zip', 'gzip', '7-zip', 'archive file', 'tar ',
                                'rar ', 'compressed')):
        return 'Arkivfil', 'application/*'
    if any(x in value for x in ('database', 'sqlite', 'siard', 'sql ', 'dbase')):
        return 'Database', 'application/*'
    if any(x in value for x in ('e-mail', 'email', 'mailbox', 'outlook msg')):
        return 'E-post', 'message/*'
    return 'Annet / ukjent', 'ukjent'


def _open_ro(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=10)
    conn.execute('PRAGMA query_only=ON')
    return conn


def _history_path(snapshot: Any) -> Path:
    work, _report, _uid, _report_sha = _work(snapshot)
    parent = work / 'noark5_evidence'
    result = work / HISTORY_FILE
    if _linked(parent) or _linked(result) or (parent.exists() and not parent.is_dir()):
        raise DocumentWorkbenchError('Utrygg Work-katalog for kopihistorikk')
    return result


def _history_db(snapshot: Any, *, create: bool) -> Path | None:
    path = _history_path(snapshot)
    if not path.exists() and not create:
        return None
    if path.exists() and (not path.is_file() or _linked(path)):
        raise DocumentWorkbenchError('Ugyldig kopihistorikk i Work')
    if create:
        path.parent.mkdir(exist_ok=True)
        with closing(sqlite3.connect(path, timeout=15)) as conn:
            conn.execute('PRAGMA journal_mode=DELETE')
            conn.execute('PRAGMA synchronous=FULL')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS exports (
                    id TEXT PRIMARY KEY, model TEXT NOT NULL, job_uid TEXT NOT NULL,
                    run_sha TEXT NOT NULL, report_sha TEXT NOT NULL,
                    recorded_utc TEXT NOT NULL, output_path TEXT NOT NULL,
                    manifest_sha TEXT NOT NULL, layout TEXT NOT NULL,
                    part_id TEXT NOT NULL, file_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS copied_files (
                    export_id TEXT NOT NULL, job_uid TEXT NOT NULL,
                    run_sha TEXT NOT NULL, source_rel TEXT NOT NULL,
                    puid TEXT NOT NULL, part_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                    output_relative TEXT NOT NULL,
                    PRIMARY KEY (export_id, source_rel)
                );
                CREATE INDEX IF NOT EXISTS copied_by_source
                    ON copied_files(job_uid,run_sha,source_rel);
                CREATE INDEX IF NOT EXISTS copied_by_part
                    ON copied_files(job_uid,run_sha,part_id,puid);
                CREATE TABLE IF NOT EXISTS export_groups (
                    export_id TEXT NOT NULL, puid TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    PRIMARY KEY (export_id,puid)
                );
                CREATE INDEX IF NOT EXISTS export_groups_by_puid
                    ON export_groups(puid,export_id);
            ''')
    return path


def _export_id(result_dir: Path, manifest_sha: str) -> str:
    # Importing the same complete manifest twice is idempotent.
    return sha256((str(result_dir) + '\n' + manifest_sha).encode('utf-8')).hexdigest()


def record_copy_receipt(snapshot: Any, meta: dict, copy_result: dict, *,
                        progress: Callable[[int], None] | None = None) -> dict:
    """One transaction: register a completed A6 copy and every actual file.

    The output's A6 manifest is SHA-attested and never edited. At most one
    manifest record is in memory at once; even 1M copies are registerable.
    """
    _checked_db(snapshot, meta, digest=True)
    run = _run(snapshot)
    output = Path(str(copy_result.get('path') or ''))
    if (not output.is_absolute() or _linked(output) or not output.is_dir()
            or output.resolve(strict=True).is_relative_to(run['work'])
            or output.resolve(strict=True).is_relative_to(run['source'])):
        raise DocumentWorkbenchError('Kopieringsresultatet har utrygt målområde')
    summary_file = output / 'sammendrag.json'
    manifest = output / 'kopimanifest.jsonl'
    if _linked(summary_file) or _linked(manifest) or not manifest.is_file():
        raise DocumentWorkbenchError('Mangler komplett kopimanifest')
    summary = _json(summary_file)
    if (summary.get('model_id') != 'dwm.noark5.document-copy.v027-a6'
            or summary.get('work_job_uid') != run['uid']
            or summary.get('report_sha256') != run['report_sha']
            or summary.get('source_run_id') != meta['run_id']
            or summary.get('file_manifest') != 'kopimanifest.jsonl'
            or summary.get('files_copied') != copy_result.get('files_copied')):
        raise DocumentWorkbenchError('Kopieringsresultatet tilhører ikke valgt jobb og kjøring')
    manifest_sha = _sha(manifest)
    if not SHA_PATTERN.fullmatch(manifest_sha) or manifest_sha != summary.get('file_manifest_sha256'):
        raise DocumentWorkbenchError('Kopimanifestet har endret SHA-256')
    export_id = _export_id(output.resolve(strict=True), manifest_sha)
    history_path = _history_db(snapshot, create=True)
    assert history_path is not None
    counts: Counter[str] = Counter()
    observed = 0
    with closing(sqlite3.connect(history_path, timeout=15)) as conn:
        conn.execute('PRAGMA foreign_keys=ON')
        # Existing receipts always refer to exactly the same completed export.
        old = conn.execute('SELECT manifest_sha, output_path FROM exports WHERE id=?',
                           (export_id,)).fetchone()
        if old:
            if old != (manifest_sha, str(output.resolve(strict=True))):
                raise DocumentWorkbenchError('Kopihistorikken har motstridende eksportidentitet')
            return {'export_id': export_id, 'already_recorded': True}
        conn.execute('BEGIN IMMEDIATE')
        try:
            conn.execute('INSERT INTO exports VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                export_id, HISTORY_MODEL, run['uid'], meta['run_raw_sha256'],
                run['report_sha'], datetime.now(timezone.utc).isoformat(timespec='seconds'),
                str(output.resolve(strict=True)), manifest_sha,
                str(summary.get('layout') or ''), str(summary.get('archive_part_id') or ''),
                summary['files_copied'],
            ))
            with manifest.open('r', encoding='utf-8') as stream:
                for line in stream:
                    if len(line) > 10000:
                        raise DocumentWorkbenchError('Ugyldig lang oppføring i kopimanifest')
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise DocumentWorkbenchError('Ugyldig oppføring i kopimanifest')
                    rel = row.get('source_relative')
                    puid = row.get('puid')
                    digest = row.get('sha256')
                    outfile = row.get('output_relative')
                    part = row.get('archive_part_id')
                    if (not isinstance(rel, str) or not rel or '\x00' in rel
                            or not isinstance(puid, str) or puid not in meta.get('by_puid', {})
                            or not isinstance(part, str) or len(part) > 500
                            or not isinstance(digest, str) or not SHA_PATTERN.fullmatch(digest)
                            or not isinstance(outfile, str) or not outfile or '\x00' in outfile
                            or outfile.startswith('/') or '\\' in outfile
                            or '..' in outfile.split('/') or '.' in outfile.split('/')):
                        raise DocumentWorkbenchError('Ugyldig dokumentidentitet i kopimanifest')
                    conn.execute('INSERT INTO copied_files VALUES (?,?,?,?,?,?,?,?)', (
                        export_id, run['uid'], meta['run_raw_sha256'], rel, puid,
                        part, digest, outfile,
                    ))
                    counts[puid] += 1
                    observed += 1
                    if progress and (observed % 10000 == 0 or observed == summary['files_copied']):
                        progress(observed)
            if observed != summary['files_copied']:
                raise DocumentWorkbenchError('Kopimanifest mangler filoppføringer')
            for puid, n in counts.items():
                conn.execute('INSERT INTO export_groups VALUES (?,?,?)',
                             (export_id, puid, n))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'export_id': export_id, 'already_recorded': False,
            'files_recorded': observed, 'by_puid': dict(counts)}


def copy_with_history(snapshot: Any, meta: dict, *, selected_puids: Iterable[str],
                      destination: Path | str, structure: str = 'puid',
                      part_id: str = '', cancelled: Callable[[], bool] | None = None,
                      progress: Callable[[int, int], None] | None = None) -> dict:
    """Preserve successful copied data even if registering the receipt fails.

    Explicit history_warning ensures an output that exists is NEVER described
    as an unsuccessful/no-copy operation solely due to Work ledger failure.
    """
    result = copy_selected_files(snapshot, meta, selected_puids=selected_puids,
                                 destination=destination, structure=structure,
                                 part_id=part_id, cancelled=cancelled, progress=progress)
    try:
        receipt = record_copy_receipt(
            snapshot, meta, result,
            progress=(lambda n: progress(n, -result['files_copied']))
            if progress else None)
        return {**result, 'history_state': 'recorded', 'receipt': receipt}
    except (OSError, ValueError, sqlite3.Error, TypeError) as exc:
        return {**result, 'history_state': 'not_recorded', 'history_warning': str(exc)}


def copy_totals(snapshot: Any, meta: dict, *, part_id: str = '') -> dict[str, dict]:
    """O(PUID groups), not O(copied files), even for million-file exports."""
    _checked_db(snapshot, meta)
    path = _history_db(snapshot, create=False)
    if path is None:
        return {}
    try:
        with closing(_open_ro(path)) as conn:
            if part_id:
                sql = '''SELECT c.puid,count(*),count(DISTINCT c.export_id),
                                max(e.recorded_utc)
                         FROM copied_files c JOIN exports e ON e.id=c.export_id
                         WHERE c.job_uid=? AND c.run_sha=? AND c.part_id=?
                         GROUP BY c.puid'''
                args = (meta['job_uid'], meta['run_raw_sha256'], part_id)
            else:
                sql = '''SELECT g.puid, sum(g.file_count), count(*), max(e.recorded_utc)
                         FROM export_groups AS g
                         JOIN exports AS e ON e.id=g.export_id
                         WHERE e.job_uid=? AND e.run_sha=?
                         GROUP BY g.puid'''
                args = (meta['job_uid'], meta['run_raw_sha256'])
            return {puid: {'copies': int(n), 'exports': int(batches), 'last': date}
                    for puid, n, batches, date in conn.execute(sql, args)}
    except sqlite3.Error as exc:
        raise DocumentWorkbenchError('Kopihistorikken kan ikke leses: ' + str(exc)) from exc


def export_history(snapshot: Any, meta: dict, *, limit: int = 100) -> tuple[dict, ...]:
    if type(limit) is not int or not 1 <= limit <= MAX_EXPORT_HISTORY:
        raise DocumentWorkbenchError('Ugyldig grense for kopihistorikk')
    _checked_db(snapshot, meta)
    path = _history_db(snapshot, create=False)
    if path is None:
        return ()
    try:
        with closing(_open_ro(path)) as conn:
            return tuple({'export_id': eid, 'date': date, 'output': output,
                          'files': count, 'layout': layout, 'part_id': part,
                          'puid_count': puid_count}
                         for eid, date, output, count, layout, part, puid_count in conn.execute(
                '''SELECT e.id,e.recorded_utc,e.output_path,e.file_count,e.layout,e.part_id,
                          (SELECT count(*) FROM export_groups g WHERE g.export_id=e.id)
                   FROM exports e WHERE e.job_uid=? AND e.run_sha=?
                   ORDER BY e.recorded_utc DESC, e.id DESC LIMIT ?''',
                (meta['job_uid'], meta['run_raw_sha256'], limit)))
    except sqlite3.Error as exc:
        raise DocumentWorkbenchError('Kopihistorikken kan ikke leses: ' + str(exc)) from exc


def copied_page_counts(snapshot: Any, meta: dict, rel_paths: Iterable[str]) -> dict[str, int]:
    """Only the visible 1-200 file rows need a copy-status query."""
    rel = tuple(dict.fromkeys(rel_paths))
    if not rel or len(rel) > MAX_FILE_PAGE:
        return {}
    path = _history_db(snapshot, create=False)
    if path is None:
        return {}
    sql = ('SELECT source_rel,count(*) FROM copied_files '
           'WHERE job_uid=? AND run_sha=? AND source_rel IN ('
           + ','.join('?' for _ in rel) + ') GROUP BY source_rel')
    try:
        with closing(_open_ro(path)) as conn:
            return {name: int(n) for name, n in conn.execute(
                sql, (meta['job_uid'], meta['run_raw_sha256'], *rel))}
    except sqlite3.Error as exc:
        raise DocumentWorkbenchError('Kan ikke lese filenes kopihistorikk') from exc


def puid_overview(snapshot: Any, meta: dict, *, part_id: str = '') -> tuple[dict, ...]:
    """SQL aggregate grouped by PUID; never transfer 1M file rows to Python."""
    db = _checked_db(snapshot, meta)
    if part_id and (meta.get('xml_mapping') or {}).get('state') != 'work_sha256_verified':
        raise DocumentWorkbenchError('Arkivdelfilter krever verifisert XML-kobling')
    try:
        with closing(_open_ro(db)) as conn:
            if part_id:
                # The (part_id,puid,id) index scopes this query correctly.
                sql = '''SELECT puid, min(fmt), min(version), count(*), sum(size)
                         FROM files WHERE part_id=? GROUP BY puid
                         ORDER BY count(*) DESC,puid'''
                vals = list(conn.execute(sql, (part_id,)))
            else:
                # Counts already computed while A6 built its indexed inventory.
                # One indexed format lookup per PUID, not 1M row materialization.
                vals = []
                for puid, count in meta.get('by_puid', {}).items():
                    item = conn.execute('SELECT fmt,version FROM files WHERE puid=? LIMIT 1',
                                        (puid,)).fetchone()
                    if item is None:
                        raise DocumentWorkbenchError('PUID-oversikten stemmer ikke med indeksen')
                    vals.append((puid, item[0], item[1], count, None))
                vals.sort(key=lambda x: (-x[3], x[0]))
            if len(vals) > MAX_VIEW_GROUPS:
                raise DocumentWorkbenchError('For mange ulike PUID-grupper til visning')
        copies = copy_totals(snapshot, meta, part_id=part_id)
        rows = []
        for puid, name, version, n, bytes_ in vals:
            group, mime = mime_category(puid, name)
            observed = copies.get(puid) or {}
            rows.append({'puid': puid, 'format': name, 'version': version,
                         'files': int(n), 'bytes': bytes_, 'group': group, 'mime': mime,
                         'copy_events': observed.get('copies', 0),
                         'copy_exports': observed.get('exports', 0),
                         'last_copy': observed.get('last', '')})
        return tuple(rows)
    except sqlite3.Error as exc:
        raise DocumentWorkbenchError('Kan ikke lese PUID-oversikt') from exc


def file_page_seek(snapshot: Any, meta: dict, *, puid: str, part_id: str = '',
                   search: str = '', after_id: int = 0, limit: int = 100) -> dict:
    """Index-backed keyset page; deep navigation avoids OFFSET over 1M records."""
    if (type(after_id) is not int or after_id < 0 or type(limit) is not int
            or not 1 <= limit <= MAX_FILE_PAGE or not isinstance(search, str)
            or len(search) > 240 or puid not in meta.get('by_puid', {})):
        raise DocumentWorkbenchError('Ugyldig filsidefilter')
    if part_id and (meta.get('xml_mapping') or {}).get('state') != 'work_sha256_verified':
        raise DocumentWorkbenchError('Arkivdelfilter krever kildeverifisert XML')
    db = _checked_db(snapshot, meta)
    args: list[Any] = [puid, after_id]
    where = 'puid=? AND id>?'
    if part_id:
        where += ' AND part_id=?'
        args.append(part_id)
    if search.strip():
        where += ' AND instr(search,?)>0'
        args.append(search.strip().casefold())
    try:
        with closing(_open_ro(db)) as conn:
            cursor = conn.execute('SELECT id,rel,puid,fmt,version,ident_state,size,mtime_ns,'
                                  'part_id,doc_id,description_id,xml_line FROM files WHERE '
                                  + where + ' ORDER BY id LIMIT ?', (*args, limit + 1))
            fetched = cursor.fetchall()
        has_next = len(fetched) > limit
        names = ('id', 'rel', 'puid', 'fmt', 'version', 'ident_state', 'size',
                 'mtime_ns', 'part_id', 'doc_id', 'description_id', 'xml_line')
        rows = [dict(zip(names, item)) for item in fetched[:limit]]
        copied = copied_page_counts(snapshot, meta, (r['rel'] for r in rows))
        for row in rows:
            row['copies_recorded'] = copied.get(row['rel'], 0)
        return {'rows': rows, 'has_next': has_next,
                'next_cursor': rows[-1]['id'] if rows else after_id,
                'complete': True}
    except sqlite3.Error as exc:
        raise DocumentWorkbenchError('Kan ikke lese dokumentfilsiden') from exc
