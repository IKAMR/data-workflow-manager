"""A12: SHA-bound, disk-paged KS review over *all* DWM/Arkade findings.

This is an index for presentation and professional comments, not a new test or
an approval. A8 Arkade records and A11 delivery JSONL are fully verified at
construction; their first-250 previews must NEVER become the complete set.
The original Work evidence and Source are never modified.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Callable, Iterable

from .qa_delivery_v023_a11 import (
    DELIVERY_SOURCES, _binding as delivery_binding, _safe_work_file,
    iter_verified_delivery,
)
from .qa_paged_v023_a8 import INDEX_MODEL as ARKADE_INDEX_MODEL

MODEL = 'dwm.noark5.ks-paged-review.a12.v1'
DIRECTORY = 'noark5_evidence/qa_review_index_v023_a12'
MAX_PAGE = 250
MAX_ROW_BYTES = 24 * 1024 * 1024
SEVERITY_ORDER = ('ERROR', 'WARNING', 'REVIEW', 'NOTE', 'INFORMATION')


class PagedReviewError(ValueError):
    """Reject partial, stale or foreign Work evidence rather than imply completeness."""


def _sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def finding_key(finding: dict) -> str:
    """Exact canonical fingerprint from qa_review_v021_a13, no new ledger."""
    fields = ('source', 'test_id', 'severity', 'message', 'context', 'file', 'source_ref', 'lines')
    data = {key: finding.get(key) for key in fields}
    return sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def _root(work: str | Path) -> Path:
    path = Path(work).resolve(strict=True)
    if not path.is_dir() or path.is_symlink():
        raise PagedReviewError('Work er ikke en sikker katalog')
    return path


def _file(work: Path, rel: str) -> Path:
    try:
        return _safe_work_file(work, rel)
    except (OSError, ValueError) as exc:
        raise PagedReviewError(str(exc)) from exc


def _identity(work: Path, snapshot: dict) -> tuple[str, str, str, Path]:
    if snapshot.get('model_id') != 'ikamr.dwm.noark5.qa-decision.a12.v1':
        raise PagedReviewError('Ukjent KS-rapportgrunnlag')
    uid = str((snapshot.get('work_identity') or {}).get('job_uid') or '')
    if not uid:
        raise PagedReviewError('KS mangler Work-jobbidentitet')
    job_path = _file(work, 'job.json')
    if job_path.stat().st_size > 2 * 1024 * 1024:
        raise PagedReviewError('Uventet stor Work-jobbdefinisjon')
    job = json.loads(job_path.read_text(encoding='utf-8-sig'))
    if (job.get('file_type') != 'dwm-work-job' or job.get('job_uid') != uid):
        raise PagedReviewError('KS og Work tilhører ulike jobber')
    manifests = [x for x in snapshot.get('evidence_manifest') or ()
                 if x.get('kind') == 'dwm_depot']
    if len(manifests) != 1:
        raise PagedReviewError('KS mangler entydig depotrapport')
    manifest = manifests[0]
    relative = manifest.get('path')
    report = _file(work, relative)
    digest = manifest.get('sha256')
    if _sha(report) != digest:
        raise PagedReviewError('Depotrapporten er endret siden KS-innlasting')
    return uid, relative, digest, report


def _index_folder(work: Path) -> Path:
    parent = work / 'noark5_evidence'
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise PagedReviewError('Utrygg Work-evidenskatalog')
    parent.mkdir(exist_ok=True)
    folder = parent / 'qa_review_index_v023_a12'
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        raise PagedReviewError('Utrygg Work-indekskatalog')
    folder.mkdir(exist_ok=True)
    return folder


def _arkade_meta(snapshot: dict) -> dict | None:
    outer = snapshot.get('a8_paged_index') or (snapshot.get('arkade') or {}).get('a8_paged_index')
    if not outer:
        if (snapshot.get('arkade') or {}).get('findings_complete') is False:
            raise PagedReviewError('Arkade-visningen er ufullstendig uten kildebundet A8-indeks')
        return None
    if (not isinstance(outer, dict) or outer.get('model_id') != ARKADE_INDEX_MODEL
            or outer.get('complete') is not True or not outer.get('job_uid')):
        raise PagedReviewError('Ukjent eller ufullstendig A8-indeks')
    return outer


def _arkade_rows(work: Path, meta: dict, uid: str):
    """Verify source and A8 SQLite once, then stream payloads via read-only SQL."""
    if meta['job_uid'] != uid:
        raise PagedReviewError('A8-indeksen tilhører feil Work-jobb')
    rel = str(meta.get('index_relative_path') or '')
    if not rel.startswith('noark5_evidence/qa_index_v023_a8/') or not rel.endswith('.sqlite'):
        raise PagedReviewError('Ugyldig A8-indekssti')
    db = _file(work, rel)
    if _sha(db) != meta.get('index_sha256'):
        raise PagedReviewError('A8-indeksens SHA-256 er endret')
    normalized = _file(work, meta.get('source_relative_path'))
    if _sha(normalized) != meta.get('source_sha256'):
        raise PagedReviewError('Normalisert Arkade-kilde er endret')
    original_ref = meta.get('preserved_relative_path') or ''
    if original_ref and _sha(_file(work, original_ref)) != meta.get('original_source_sha256'):
        raise PagedReviewError('Bevart Arkade-original er endret')
    conn = None
    try:
        conn = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
        expected = meta.get('finding_count')
        if type(expected) is not int or expected < 0:
            raise PagedReviewError('A8 mangler dokumentert funntotal')
        actual = conn.execute('SELECT count(*) FROM findings').fetchone()[0]
        if expected != actual:
            raise PagedReviewError('A8-indeksens funntotal stemmer ikke')
        for (raw,) in conn.execute('SELECT payload FROM findings ORDER BY ordinal'):
            row = json.loads(raw)
            if row.get('source') != 'Arkade 5' or row.get('source_ref') != meta.get('source_relative_path'):
                raise PagedReviewError('A8-indeksens funn har ukjent kilde')
            if row.get('finding_key') != finding_key(row):
                raise PagedReviewError('A8-funnet har motstridende vurderingsnøkkel')
            yield row
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        raise PagedReviewError('Uleselig A8-indeks') from exc
    finally:
        if conn is not None:
            conn.close()


def _manual_state(work: Path, uid: str, depot_sha: str) -> dict:
    """Read the manual ledger only when it exists in the selected Work.

    Historic A12/A13 unit fixtures deliberately provide just their earlier
    review API, and a Work without manual observations must not depend on
    importing the unrelated manual-workflow adapter. The real manual ledger
    is always revalidated if the event directory actually exists.
    """
    folder = work / 'noark5_evidence/qa_manual_findings_v022_a3'
    if folder.is_symlink() or folder.parent.is_symlink():
        raise PagedReviewError('Utrygg Work-katalog for manuell evidens')
    if not folder.exists():
        empty = sha256(b'').hexdigest()
        return {'count': 0, 'sha256': empty,
                'current_count': 0, 'current_ids_sha256': empty}
    from .qa_workflow_v022_a3 import manual_ledger_state
    return manual_ledger_state(work, job_uid=uid, depot_sha256=depot_sha)


def _fingerprint(snapshot: dict, uid: str, depot_sha: str, arkade: dict | None,
                 manual_state: dict | None = None) -> str:
    # Row keys include manual observations and historical sources that can
    # change independently of the depot-report revision.
    fields = {'job_uid': uid, 'depot_sha256': depot_sha,
              'keys': [finding_key(x) for x in snapshot.get('findings') or ()],
              'manual_ledger': manual_state,
              'full_count': snapshot.get('full_finding_count'),
              'arkade': {k: arkade.get(k) for k in
                         ('source_relative_path', 'source_sha256', 'index_sha256',
                          'original_source_sha256', 'finding_count')} if arkade else None,
              'delivery': {k: (snapshot.get('delivery_qa') or {}).get(k) for k in
                           ('source', 'finding_count', 'source_sha256', 'status')}}
    return sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def _cached(work: Path, db: Path, manifest: Path, fingerprint: str, uid: str,
            depot_sha: str) -> dict | None:
    if (not db.is_file() or db.is_symlink() or not manifest.is_file()
            or manifest.is_symlink() or manifest.stat().st_size > 64 * 1024):
        return None
    try:
        info = json.loads(manifest.read_text(encoding='utf-8'))
        if (info.get('model_id') != MODEL or info.get('complete') is not True
                or info.get('snapshot_fingerprint') != fingerprint
                or info.get('job_uid') != uid or info.get('depot_sha256') != depot_sha
                or _sha(db) != info.get('index_sha256')):
            return None
        with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
            n = conn.execute('SELECT count(*) FROM findings').fetchone()[0]
        return info if n == info.get('finding_count') else None
    except (OSError, ValueError, sqlite3.Error):
        return None


def build_paged_index(work: str | Path, snapshot: dict, *,
                      progress: Callable[[int], None] | None = None,
                      cancelled: Callable[[], bool] | None = None) -> dict:
    """Build/reuse complete bounded-memory KS index for the actual selected Work.

    Never commits a partial index on cancel/error. Report- and source-bound
    caching avoids re-reading a 100k-row archive on every review save.
    """
    root = _root(work)
    uid, depot_rel, depot_sha, depot_path = _identity(root, snapshot)
    arkade = _arkade_meta(snapshot)
    delivery = snapshot.get('delivery_qa') or {}
    use_delivery = bool(str(delivery.get('status') or '').startswith('completed_'))
    if use_delivery:
        depot = json.loads(depot_path.read_text(encoding='utf-8-sig'))
        binding = delivery_binding(root, depot_rel, depot, uid)
        if not binding or not binding.get('complete'):
            raise PagedReviewError('DWM-rapporten mangler fullstendige individuelle funn')
        if binding['count'] != delivery.get('finding_count'):
            raise PagedReviewError('DWM-funntotal stemmer ikke med KS-grunnlaget')
    else:
        depot = None
        if delivery.get('status') not in (None, '', 'not_assessed', 'not_available'):
            raise PagedReviewError('Ukjent eller ufullstendig DWM-funnstatus')
    if snapshot.get('findings_complete') is False and not (arkade or use_delivery):
        raise PagedReviewError('KS er ufullstendig uten sidevis kildegrunnlag')
    manual_state = _manual_state(root, uid, depot_sha)
    # A stale, partial snapshot cannot be upgraded to a complete index merely
    # because the depot/Arkade source files are unchanged. A user may have
    # recorded new manual findings after the snapshot was built.
    manual_ids = sorted(str(row['manual_event_id']) for row in
                        snapshot.get('findings') or () if row.get('manual_event_id'))
    manual_hash = sha256(''.join(eid + '\n' for eid in manual_ids).encode('utf-8')).hexdigest()
    if (len(manual_ids) != manual_state['current_count']
            or manual_hash != manual_state['current_ids_sha256']):
        raise PagedReviewError('Manuelle funn er endret siden KS-grunnlaget ble lest; last inn på nytt')
    fp = _fingerprint(snapshot, uid, depot_sha, arkade, manual_state)
    folder = _index_folder(root)
    db = folder / (fp[:32] + '.sqlite')
    manifest = folder / (fp[:32] + '.json')
    existing = _cached(root, db, manifest, fp, uid, depot_sha)
    if existing:
        # A cache is valid only while BOTH original source families still match
        # the exact verified revision. Source files are immutable for QA, but
        # users can move/edit external disks between visits.
        if arkade:
            if (_sha(_file(root, arkade['source_relative_path'])) != arkade['source_sha256']
                    or (arkade.get('preserved_relative_path') and
                        _sha(_file(root, arkade['preserved_relative_path'])) !=
                        arkade['original_source_sha256'])
                    or _sha(_file(root, arkade['index_relative_path'])) != arkade['index_sha256']):
                raise PagedReviewError('Arkade-kilde eller A8-indeks ble endret siden KS-indeksering')
        if use_delivery:
            if (_sha(binding['jsonl_path']) != binding['jsonl_sha256'] or
                    _sha(binding['csv_path']) != binding['csv_sha256']):
                raise PagedReviewError('DWM-avleveringskilde ble endret siden KS-indeksering')
        return existing
    if db.is_symlink() or manifest.is_symlink():
        raise PagedReviewError('Utrygt indeksmål')
    fd, tmpname = tempfile.mkstemp(prefix='.a12-', suffix='.sqlite', dir=folder)
    os.close(fd)
    connection = None
    count = 0
    severities: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    try:
        connection = sqlite3.connect(tmpname)
        connection.execute('PRAGMA journal_mode=DELETE')
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('CREATE TABLE findings ('
                           'ordinal INTEGER PRIMARY KEY, finding_key TEXT NOT NULL UNIQUE, '
                           'source TEXT NOT NULL, severity TEXT NOT NULL, priority INTEGER NOT NULL, '
                           'test_id TEXT NOT NULL, search_text TEXT NOT NULL, payload TEXT NOT NULL)')
        connection.execute('CREATE INDEX by_priority ON findings(priority, ordinal)')
        connection.execute('CREATE INDEX by_severity ON findings(severity, priority, ordinal)')
        connection.execute('CREATE INDEX by_source ON findings(source, priority, ordinal)')
        connection.execute('CREATE INDEX by_test ON findings(test_id, priority, ordinal)')
        def add(row):
            nonlocal count
            if cancelled is not None and cancelled():
                raise PagedReviewError('Indeksering avbrutt – ingen ufullstendige funn publisert')
            if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k]
                                                for k in ('source','test_id','severity','message','source_ref')):
                raise PagedReviewError('KS-funn mangler identitet eller kilde')
            key = finding_key(row)
            if row.get('finding_key') and row['finding_key'] != key:
                raise PagedReviewError('KS-funnets vurderingsnøkkel stemmer ikke med kilden')
            payload = dict(row)
            for old in ('review_status','review_comment','include_in_ks','include_in_depot','reviewed_by'):
                payload.pop(old, None)
            payload['finding_key'] = key
            raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
            if len(raw.encode('utf-8')) > MAX_ROW_BYTES:
                raise PagedReviewError('KS-funnpost overstiger sikker enkeltpostgrense')
            count += 1
            severity = str(row['severity']).upper()
            # casefold for Unicode search (Norwegian æ/ø/å included).
            search = ' '.join(str(row.get(k) or '') for k in
                              ('source','test_id','severity','message','context','file',
                               'object_id','archive_part_id')).casefold()
            connection.execute('INSERT INTO findings VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                               (count,key,row['source'],severity,
                                SEVERITY_ORDER.index(severity) if severity in SEVERITY_ORDER else 5,
                                row['test_id'],search,raw))
            severities[severity] += 1
            sources[row['source']] += 1
            if count % 5000 == 0:
                connection.commit()
                if progress:
                    progress(count)
        for row in snapshot.get('findings') or ():
            if arkade and row.get('source') == 'Arkade 5':
                continue  # Source index contains *all* Arkade occurrences.
            if use_delivery and row.get('source') in DELIVERY_SOURCES:
                continue  # Never add the DWM 250-preview a second time.
            add(row)
        if arkade:
            for row in _arkade_rows(root, arkade, uid):
                add(row)
        if use_delivery:
            for row in iter_verified_delivery(root, depot_rel, depot, job_uid=uid):
                add(row)
        required = snapshot.get('full_finding_count')
        if type(required) is int and count != required:
            raise PagedReviewError(f'Forventet {required} KS-funn, indeksert {count}; '
                                   'ingen ufullstendig indeks publiseres')
        if snapshot.get('findings_complete') is True and count != len(snapshot.get('findings') or ()):
            raise PagedReviewError('KS hevder komplett snapshot med avvikende antall funn')
        connection.commit()
        connection.close()
        connection = None
        tracked = []
        if arkade:
            tracked.extend(((arkade['source_relative_path'], arkade['source_sha256']),
                            (arkade['index_relative_path'], arkade['index_sha256'])))
            if arkade.get('preserved_relative_path'):
                tracked.append((arkade['preserved_relative_path'],
                                arkade['original_source_sha256']))
        if use_delivery:
            tracked.extend(((binding['jsonl_relative'], binding['jsonl_sha256']),
                            (binding['csv_relative'], binding['csv_sha256'])))
        source_files = []
        for ref, expected_sha in tracked:
            path = _file(root, ref)
            # Detect a race between complete scan, index write and publication.
            if _sha(path) != expected_sha:
                raise PagedReviewError('Originale evidensfiler ble endret under KS-indeksering')
            stat = path.stat()
            source_files.append({'path': ref, 'sha256': expected_sha,
                                 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns})
        if _manual_state(root, uid, depot_sha) != manual_state:
            raise PagedReviewError('Manuell evidens ble endret under KS-indeksering')
        doc = {'model_id': MODEL, 'complete': True, 'job_uid': uid,
               'manual_ledger': manual_state,
               'depot_report_relative': depot_rel, 'depot_sha256': depot_sha,
               'snapshot_fingerprint': fp,
               'source_files': source_files,
               'index_relative_path': DIRECTORY + '/' + db.name,
               'index_sha256': _sha(Path(tmpname)),
               'finding_count': count,
               'severity_counts': dict(sorted(severities.items())),
               'source_counts': dict(sorted(sources.items())),
               'arkade_index_sha256': arkade.get('index_sha256') if arkade else None,
               'arkade_source_sha256': arkade.get('source_sha256') if arkade else None,
               'arkade_original_sha256': arkade.get('original_source_sha256') if arkade else None,
               'delivery_source_sha256': delivery.get('source_sha256') if use_delivery else None,
               'automatic_approval': False}
        # Publish immutable complete DB first, then its manifest.
        os.replace(tmpname, db)
        tmpname = ''
        fdmeta, tempmeta = tempfile.mkstemp(prefix='.a12-meta-', dir=folder)
        try:
            with os.fdopen(fdmeta, 'w', encoding='utf-8', newline='\n') as fpout:
                fpout.write(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
                fpout.flush()
                os.fsync(fpout.fileno())
            os.replace(tempmeta, manifest)
        finally:
            if os.path.exists(tempmeta):
                os.unlink(tempmeta)
        return doc
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        if isinstance(exc, PagedReviewError):
            raise
        raise PagedReviewError('Kan ikke bygge komplett KS-indeks: ' + str(exc)) from exc
    finally:
        if connection is not None:
            connection.close()
        if tmpname and os.path.exists(tmpname):
            os.unlink(tmpname)


def _open_index(work: str | Path, metadata: dict, *, digest: bool = False):
    root = _root(work)
    if (not isinstance(metadata, dict) or metadata.get('model_id') != MODEL
            or metadata.get('complete') is not True):
        raise PagedReviewError('Ukjent eller ufullstendig KS-indeks')
    rel = metadata.get('index_relative_path')
    if (not isinstance(rel, str) or not rel.startswith(DIRECTORY + '/')
            or not rel.endswith('.sqlite')):
        raise PagedReviewError('Ugyldig KS-indeksreferanse')
    db = _file(root, rel)
    meta_file = _file(root, rel[:-7] + '.json')
    if meta_file.stat().st_size > 64 * 1024:
        raise PagedReviewError('Indeksmanifestet er uventet stort')
    current = json.loads(meta_file.read_text(encoding='utf-8'))
    if (current != metadata or current.get('model_id') != MODEL
            or current.get('complete') is not True):
        raise PagedReviewError('KS-indeksmanifestet er endret siden innlasting')
    job_file = _file(root, 'job.json')
    if job_file.stat().st_size > 2 * 1024 * 1024:
        raise PagedReviewError('Work-identitet overstiger sikker lesestørrelse')
    job = json.loads(job_file.read_text(encoding='utf-8-sig'))
    if (job.get('file_type') != 'dwm-work-job'
            or job.get('job_uid') != metadata.get('job_uid')):
        raise PagedReviewError('KS-indeksen tilhører en annen Work-jobb')
    report = _file(root, metadata.get('depot_report_relative'))
    if _sha(report) != metadata.get('depot_sha256'):
        raise PagedReviewError('Valgt depotrapport ble endret etter KS-indeksering')
    for item in metadata.get('source_files') or ():
        file = _file(root, item['path'])
        stat = file.stat()
        if stat.st_size != item.get('size') or stat.st_mtime_ns != item.get('mtime_ns'):
            raise PagedReviewError('Evidenskilden ble endret etter KS-indeksering')
        if digest and _sha(file) != item.get('sha256'):
            raise PagedReviewError('SHA-256-avvik i original KS-evidens')
    if digest and _sha(db) != metadata.get('index_sha256'):
        raise PagedReviewError('KS-indeksen er endret siden indeksering')
    if digest:
        # Manual findings are immutable Work evidence, independent of the
        # depot/Arkade source files above. Verify their *entire* event ledger
        # before a review save or full report export. Old index manifests must
        # be rebuilt, never silently treated as a complete A15 index.
        actual = _manual_state(root, metadata['job_uid'], metadata['depot_sha256'])
        if actual != metadata.get('manual_ledger'):
            raise PagedReviewError('Manuell evidens er endret siden KS-indeksering')
    return root, db


def load_review_events(work: str | Path, metadata: dict) -> dict[str, dict]:
    """Stream all immutable a13 events, selecting the latest for each indexed finding.

    No 2,000-event cap and no full-history list in memory. Every historic event
    is independently checksum-verified, including obsolete source revisions.
    The original per-finding chronology is respected even when scandir is
    unordered. This never interprets a professional remark as technical PASS.
    """
    root, db = _open_index(work, metadata, digest=True)
    import importlib
    review_api = importlib.import_module('.qa_review_v021_a13', __package__)
    reader = getattr(review_api, '_iter_events', None) or review_api._read_events
    events: dict[str, dict] = {}
    ranks: dict[str, tuple[int, str, int]] = {}
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
        conn.execute('PRAGMA query_only=ON')
        for sequence, ev in enumerate(reader(root), 1):
            if (ev.get('job_uid') != metadata['job_uid'] or
                    ev.get('depot_report_sha256') != metadata['depot_sha256']):
                continue
            key = str(ev.get('finding_key') or '')
            stamp = ev.get('recorded_ns')
            # All real events have a signed integer recorded_ns. Preserve
            # legacy test-double compatibility for unversioned mock events.
            rank = ((stamp, str(ev.get('event_id') or ''), 0)
                    if type(stamp) is int else (0, '', sequence))
            if key in ranks:
                if rank > ranks[key]:
                    events[key] = ev
                    ranks[key] = rank
            elif conn.execute('SELECT 1 FROM findings WHERE finding_key=?', (key,)).fetchone():
                events[key] = ev
                ranks[key] = rank
    return events


def review_page(work: str | Path, metadata: dict, *, page: int = 0,
                page_size: int = 100, severity: str = '', source: str = '',
                test_id: str = '', search: str = '', reviewed: str = '',
                reviews: dict[str, dict] | None = None) -> dict:
    """Bounded SQL page, including optional reviewed/pending filter and totals."""
    if (type(page) is not int or page < 0 or type(page_size) is not int
            or not 1 <= page_size <= MAX_PAGE or severity not in ('', *SEVERITY_ORDER)
            or reviewed not in ('', 'reviewed', 'pending') or
            any(not isinstance(v, str) for v in (source, test_id, search)) or len(search) > 400):
        raise PagedReviewError('Ugyldig KS-side eller filter')
    root, db = _open_index(work, metadata)
    conditions = []
    params: list = []
    if severity:
        conditions.append('f.severity = ?'); params.append(severity)
    if source:
        conditions.append('f.source = ?'); params.append(source)
    if test_id:
        conditions.append('f.test_id = ?'); params.append(test_id)
    if search.strip():
        conditions.append('instr(f.search_text, ?) > 0'); params.append(search.strip().casefold())
    rev = reviews or {}
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
        if reviewed:
            conn.execute('CREATE TEMP TABLE reviewed_keys (finding_key TEXT PRIMARY KEY)')
            conn.executemany('INSERT OR IGNORE INTO reviewed_keys VALUES (?)',
                             ((key,) for key in rev))
            condition = ('EXISTS' if reviewed == 'reviewed' else 'NOT EXISTS')
            conditions.append(condition + ' (SELECT 1 FROM reviewed_keys r WHERE r.finding_key = f.finding_key)')
        where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
        try:
            count = conn.execute('SELECT count(*) FROM findings f' + where, params).fetchone()[0]
            rows = conn.execute('SELECT f.payload FROM findings f' + where +
                                ' ORDER BY f.priority, f.ordinal LIMIT ? OFFSET ?',
                                (*params,page_size,page * page_size)).fetchall()
        except sqlite3.Error as exc:
            raise PagedReviewError('Kan ikke lese sidevis KS-indeks') from exc
    result = []
    for (data,) in rows:
        item = json.loads(data)
        event = rev.get(item['finding_key'])
        item['review_status'] = str(event.get('status') or '') if event else ''
        item['review_comment'] = str(event.get('comment') or '') if event else ''
        item['include_in_ks'] = bool(event.get('include_in_ks')) if event else True
        item['include_in_depot'] = bool(event.get('include_in_depot')) if event else True
        result.append(item)
    return {'page': page, 'page_size': page_size,
            'total': count, 'total_all': metadata['finding_count'],
            'pages': (count + page_size - 1) // page_size,
            'rows': result, 'complete': True}


def save_review_for_page(work: str | Path, snapshot: dict, metadata: dict,
                         finding: dict, *, status: str, comment: str, user,
                         include_in_ks: bool = True,
                         include_in_depot: bool = True) -> dict:
    """Exact index membership + original a13 append-only save (no new ledger).

    The narrowed snapshot is a validation context, not a replacement snapshot
    or export. This lets a13 check an off-preview row without accepting an
    arbitrary row supplied by a caller.
    """
    root, db = _open_index(work, metadata, digest=True)
    uid, depot_rel, digest, _report = _identity(root, snapshot)
    if (uid != metadata['job_uid'] or depot_rel != metadata['depot_report_relative']
            or digest != metadata['depot_sha256']):
        raise PagedReviewError('Siden er knyttet til feil KS-/depotrapport')
    key = finding_key(finding)
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
        found = conn.execute('SELECT payload FROM findings WHERE finding_key=?', (key,)).fetchone()
    if not found:
        raise PagedReviewError('Valgt funn tilhører ikke denne komplette KS-indeksen')
    original = json.loads(found[0])
    # Compare entire unreviewed evidence row; UI-specific presentation fields
    # must be ignored, everything else must match source-bound raw evidence.
    for field, value in original.items():
        if finding.get(field) != value:
            raise PagedReviewError('Valgt KS-funn er endret etter sidevis lesing')
    from .qa_review_v021_a13 import record_review
    narrow = dict(snapshot)
    narrow['findings'] = [original]
    return record_review(root, narrow, original, status=status, comment=comment,
                         user=user, include_in_ks=include_in_ks,
                         include_in_depot=include_in_depot)
