"""DWM v0.2.3-a8: source-bound, disk-backed Arkade findings for large KS.

Original Work evidence is read-only. This index is derived and explicitly NOT an
approval or a substitute for A260's complete CSV/JSONL export. An index is only
published after full JSON parsing, integrity checks and a committed SQLite DB.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import tempfile
from typing import Any

INDEX_DIR = 'noark5_evidence/qa_index_v023_a8'
INDEX_MODEL = 'dwm.noark5.qa-findings-index.v023-a8'
PREVIEW_ROWS = 250  # presentation only: the index always retains every finding
MAX_PAGE_SIZE = 1000  # UI resource bound, never an evidence/record-count limit
MAX_INDEX_META = 1024 * 1024


class QaIndexError(ValueError):
    """Fail closed: no partial index, invented evidence or implied acceptance."""


def _digest(path: Path) -> str:
    result = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def _file_in_work(work: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or '\\' in relative or
            '//' in relative or ':' in relative.split('/')[0]):
        raise QaIndexError('Forventer Work-relativ evidenssti med /')
    p = PurePosixPath(relative)
    if p.is_absolute() or any(x in ('.', '..', '') for x in p.parts):
        raise QaIndexError('Utrygg evidenssti')
    candidate = work
    for part in p.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise QaIndexError('Symbolsk lenke i evidenssti')
    if not candidate.resolve(strict=False).is_relative_to(work.resolve(strict=True)):
        raise QaIndexError('Evidens utenfor Work')
    if not candidate.is_file():
        raise QaIndexError('Evidensfil finnes ikke: ' + relative)
    return candidate


def _index_folder(work: Path) -> Path:
    root = work / 'noark5_evidence'
    if not root.is_dir() or root.is_symlink():
        raise QaIndexError('Work mangler sikker noark5_evidence-mappe')
    folder = root / 'qa_index_v023_a8'
    if folder.is_symlink():
        raise QaIndexError('Utrygg indeksmappe')
    folder.mkdir(exist_ok=True)
    return folder


def _read_manifest(path: Path) -> dict | None:
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_size > MAX_INDEX_META):
        return None
    try:
        item = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError, UnicodeError):
        return None
    return item if isinstance(item, dict) else None


def _base_index(work: Path, source_relative: str, source_sha: str) -> tuple[Path, Path]:
    name = sha256((source_relative + '\n' + source_sha).encode('utf-8')).hexdigest()[:24]
    folder = _index_folder(work)
    return folder / (name + '.sqlite'), folder / (name + '.json')


def _valid_cached(db: Path, meta_path: Path, source_sha: str,
                  original_sha: str, relative: str, job_uid: str) -> dict | None:
    meta = _read_manifest(meta_path)
    if not meta or not db.is_file() or db.is_symlink():
        return None
    if (meta.get('model_id') != INDEX_MODEL or
            meta.get('complete') is not True or
            meta.get('source_sha256') != source_sha or
            meta.get('original_source_sha256') != original_sha or
            meta.get('source_relative_path') != relative or
            meta.get('job_uid') != job_uid or
            meta.get('index_sha256') != _digest(db)):
        return None
    return meta


def _connect_new(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA synchronous=FULL')
    conn.execute('CREATE TABLE findings ('
                 'ordinal INTEGER PRIMARY KEY, finding_key TEXT NOT NULL, '
                 'severity TEXT NOT NULL, test_id TEXT NOT NULL, payload TEXT NOT NULL)')
    conn.execute('CREATE INDEX idx_findings_severity ON findings(severity, ordinal)')
    conn.execute('CREATE INDEX idx_findings_test ON findings(test_id, ordinal)')
    return conn


def build_arkade_index(work: str | Path, source_relative: str, *,
                       original_sha256: str, job_uid: str,
                       preview_rows: int = PREVIEW_ROWS,
                       preserved_relative: str = '') -> dict[str, Any]:
    """Index all Arkade errors/warnings in SQLite with bounded preview.

    Never silently omit a finding. Reject unknown/mutated source, malformed JSON,
    missing provenance and unsafe paths. The index is safe to reuse only when its
    SHA and Work/job/normalized source binding still match.
    """
    if not (0 <= preview_rows <= MAX_PAGE_SIZE):
        raise QaIndexError('Ugyldig størrelse på forhåndsvisning')
    if len(original_sha256) != 64 or any(c not in '0123456789abcdef' for c in original_sha256.lower()):
        raise QaIndexError('Arkade-kilden mangler SHA-256')
    if not job_uid:
        raise QaIndexError('Manglende Work-jobbidentitet')
    if not (source_relative.startswith('external_evidence/arkade5/') and
            source_relative.endswith('/normalized/arkade5_results.json')):
        raise QaIndexError('Ukjent Arkade-sti')
    root = Path(work).resolve(strict=True)
    source = _file_in_work(root, source_relative)
    if preserved_relative and _digest(_file_in_work(root, preserved_relative)) != original_sha256:
        raise QaIndexError('Bevart Arkade-original stemmer ikke med manifestets SHA-256')
    source_stat = source.stat()
    source_hash = _digest(source)
    db, meta_path = _base_index(root, source_relative, source_hash)
    cached = _valid_cached(db, meta_path, source_hash, original_sha256, source_relative, job_uid)
    if cached is not None and cached.get('preserved_relative_path', '') != preserved_relative:
        cached = None
    if cached is not None:
        result = dict(cached)
        result['preview'] = page_arkade_index(root, cached, page=0,
                                              page_size=max(preview_rows, 1))['rows'][:preview_rows]
        return result
    try:
        import ijson
    except ImportError as exc:
        raise QaIndexError('ijson er påkrevd for trygg strømlesing av Arkade') from exc
    from noark5_workflow.reporting.qa_a260_v023_a6 import iter_arkade_findings

    folder = _index_folder(root)
    fd, tmp = tempfile.mkstemp(prefix='.a8-', suffix='.sqlite', dir=folder)
    os.close(fd)
    conn = None
    complete = False
    observed: dict[str, Any] = {'original_sha': None, 'test_count': 0, 'summary': {}}
    count = 0
    severities: Counter[str] = Counter()
    try:
        conn = _connect_new(Path(tmp))
        with source.open('rb') as stream:
            def events():
                for prefix, event, value in ijson.parse(stream):
                    if prefix == 'source.sha256' and event == 'string':
                        observed['original_sha'] = value
                    elif prefix == 'tests.item' and event == 'start_map':
                        observed['test_count'] += 1
                    elif (prefix in ('summary.number_of_tests_run',
                                      'summary.number_of_errors',
                                      'summary.number_of_warnings',
                                      'summary.system_name', 'summary.archival_period') and
                          event in ('string', 'number', 'integer', 'null')):
                        observed['summary'][prefix.split('.', 1)[1]] = str(value) if value is not None else None
                    yield prefix, event, value
            for row in iter_arkade_findings(events(), source_ref=source_relative,
                                            source_sha=source_hash):
                count += 1
                severity = str(row['severity']).upper()
                test_id = str(row['test_id'])
                severities[severity] += 1
                conn.execute('INSERT INTO findings VALUES (?, ?, ?, ?, ?)',
                             (count, row['finding_key'], severity, test_id,
                              json.dumps(row, ensure_ascii=False, allow_nan=False)))
                if count % 5000 == 0:
                    conn.commit()
        if observed['original_sha'] != original_sha256:
            raise QaIndexError('Normalisert Arkade-fil og bevart originalkilde har ulik SHA-256')
        if (source.stat().st_size != source_stat.st_size or
                _digest(source) != source_hash):
            raise QaIndexError('Arkade-kilden ble endret under indeksering')
        unique_tests = conn.execute('SELECT count(DISTINCT test_id) FROM findings').fetchone()[0]
        conn.commit()
        conn.close()
        conn = None
        data = {
            'model_id': INDEX_MODEL, 'complete': True, 'job_uid': job_uid,
            'source_relative_path': source_relative,
            'source_sha256': source_hash,
            'original_source_sha256': original_sha256,
            'preserved_relative_path': preserved_relative,
            'index_relative_path': (Path(INDEX_DIR) / db.name).as_posix(),
            'index_sha256': _digest(Path(tmp)),
            'test_count': observed['test_count'], 'reported_summary': observed['summary'],
            'finding_count': count, 'severity_counts': dict(sorted(severities.items())),
            'distinct_test_ids_with_findings': unique_tests,
            'preview_limit': preview_rows, 'technical_validation_verified': False,
            'archive_creator_acceptance': None, 'depot_approval': None,
            'note': 'Alle kilderapporterte funn er indeksert; dette er ikke godkjenning.',
        }
        # The index is published before its manifest: incomplete work has no valid binding.
        if db.is_symlink() or meta_path.is_symlink():
            raise QaIndexError('Utrygg målfil for indeks')
        os.replace(tmp, db)
        tmp = ''
        fd_meta, name_meta = tempfile.mkstemp(prefix='.a8-meta-', dir=folder)
        try:
            with os.fdopen(fd_meta, 'w', encoding='utf-8', newline='\n') as out:
                out.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
                out.flush()
                os.fsync(out.fileno())
            os.replace(name_meta, meta_path)
        finally:
            if os.path.exists(name_meta):
                os.unlink(name_meta)
        complete = True
        data['preview'] = page_arkade_index(root, data, page=0,
                                            page_size=max(preview_rows, 1))['rows'][:preview_rows]
        return data
    except (OSError, ValueError, sqlite3.Error, ijson.JSONError) as exc:
        if isinstance(exc, QaIndexError):
            raise
        raise QaIndexError('Kunne ikke bygge fullstendig Arkade-indeks: ' + str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def page_arkade_index(work: str | Path, metadata: dict, *, page: int = 0,
                      page_size: int = 200, severity: str = '',
                      test_id: str = '') -> dict:
    """Read an arbitrary result page, without loading the full index in RAM."""
    if (type(page) is not int or page < 0 or type(page_size) is not int or
            not 1 <= page_size <= MAX_PAGE_SIZE):
        raise QaIndexError('Ugyldig indeks-side')
    if not isinstance(metadata, dict) or metadata.get('model_id') != INDEX_MODEL:
        raise QaIndexError('Ukjent indeksmodell')
    if not metadata.get('complete'):
        raise QaIndexError('Ufullstendig Arkade-indeks')
    root = Path(work).resolve(strict=True)
    rel = metadata.get('index_relative_path')
    if not isinstance(rel, str) or not rel.startswith(INDEX_DIR + '/') or not rel.endswith('.sqlite'):
        raise QaIndexError('Ugyldig indekssti')
    db = _file_in_work(root, rel)
    source_relative = metadata.get('source_relative_path')
    if not isinstance(source_relative, str) or _digest(_file_in_work(root, source_relative)) != metadata.get('source_sha256'):
        raise QaIndexError('Arkade-originalens normaliserte kildefil er endret siden indeksering')
    original_relative = metadata.get('preserved_relative_path') or ''
    if original_relative and _digest(_file_in_work(root, original_relative)) != metadata.get('original_source_sha256'):
        raise QaIndexError('Bevart Arkade-original er endret siden indeksering')
    if _digest(db) != metadata.get('index_sha256'):
        raise QaIndexError('SHA-256-avvik i avledet indeks')
    if severity and severity not in ('ERROR', 'WARNING'):
        raise QaIndexError('Ukjent alvorlighetsgrad')
    condition = []
    values = []
    if severity:
        condition.append('severity = ?')
        values.append(severity)
    if test_id:
        condition.append('test_id = ?')
        values.append(test_id)
    where = ' WHERE ' + ' AND '.join(condition) if condition else ''
    uri = db.as_uri() + '?mode=ro'
    conn = None
    try:
        conn = sqlite3.connect(uri, uri=True)
        total = conn.execute('SELECT count(*) FROM findings' + where, values).fetchone()[0]
        found = conn.execute('SELECT payload FROM findings' + where +
                             ' ORDER BY ordinal LIMIT ? OFFSET ?',
                             (*values, page_size, page * page_size)).fetchall()
    except sqlite3.Error as exc:
        raise QaIndexError('Kunne ikke lese indeksert evidens') from exc
    finally:
        if conn is not None:
            conn.close()
    return {'page': page, 'page_size': page_size, 'total': total,
            'rows': [json.loads(raw) for (raw,) in found], 'complete': True}


def streamed_json_marker(path: str | Path, field: str) -> str | None:
    """Read a small typed JSON envelope marker without decoding the full source.

    Parses to EOF so malformed/trailing source data cannot masquerade as valid.
    """
    try:
        import ijson
    except ImportError as exc:
        raise QaIndexError('Mangler ijson for stor PRONOM-evidens') from exc
    value = None
    try:
        with Path(path).open('rb') as stream:
            for prefix, event, item in ijson.parse(stream):
                if prefix == field and event == 'string':
                    value = item
    except (OSError, UnicodeError, ValueError, ijson.JSONError) as exc:
        raise QaIndexError('Ugyldig normalisert PRONOM-evidens') from exc
    return value
