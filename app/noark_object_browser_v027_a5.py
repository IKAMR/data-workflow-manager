"""Read-only, source-bound Noark 5 object index for Analyse (v0.2.7-a5).

Only an explicit user request reads the selected job's arkivstruktur.xml. A
complete SQLite projection is stored in Work, not in Source. Missing and
ambiguous object identities are never filled in from aggregate statistics.
The original depot report and the A4 annotation ledger remain authoritative.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable
import json
import os
import re
import sqlite3
import tempfile
from uuid import uuid4

MODEL = 'dwm.noark5.object-index.v027-a5'
INDEX_DIR = 'noark5_evidence/noark5_objects_v027_a5'
MAX_JOB_BYTES = 2_000_000
MAX_META_BYTES = 128_000
MAX_DEPTH = 128
MAX_ROWS = 20_000_000
MAX_PAGE = 250
MAX_CACHED = 100
XSI_TYPE = '{http://www.w3.org/2001/XMLSchema-instance}type'
OBJECT_TAGS = {
    'arkiv': 'arkiv', 'arkivdel': 'arkivdel',
    'mappe': 'mappe', 'saksmappe': 'mappe',
    'registrering': 'registrering', 'journalpost': 'registrering',
    'basisregistrering': 'registrering',
}
FIELDS = {
    'systemID', 'tittel', 'arkivstatus', 'arkivdelstatus', 'saksstatus',
    'journalstatus', 'mappeID', 'registreringsID', 'saksaar',
    'sakssekvensnummer', 'journalaar', 'journalsekvensnummer',
    'journalpostnummer', 'journalposttype', 'registreringstype',
    'opprettetDato', 'avsluttetDato', 'saksdato', 'journaldato',
    'registreringsdato', 'dokumentetsDato',
}


class ObjectIndexError(ValueError):
    """The projection is unavailable, incomplete or no longer source-bound."""


def _sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _root(snapshot: Any) -> tuple[Path, Path, str]:
    """Bind Analyse to one exact persisted Work job and its depot report.

    Older Qt job snapshots can omit job_uid even when job.json has it. Only
    recover that missing value from a matching, Work-owned report manifest;
    never reinterpret a non-empty but contradictory job_uid.
    """
    work = Path(snapshot.work)
    if work.is_symlink() or not work.is_dir():
        raise ObjectIndexError('Ugyldig eller frakoblet Work')
    work = work.resolve(strict=True)
    definition = work / 'job.json'
    if (definition.is_symlink() or not definition.is_file()
            or definition.stat().st_size > MAX_JOB_BYTES):
        raise ObjectIndexError('Work mangler sikker jobbdefinisjon')
    try:
        data = json.loads(definition.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError, UnicodeError) as exc:
        raise ObjectIndexError('Uleselig Work-jobbdefinisjon') from exc
    if not isinstance(data, dict) or data.get('file_type') != 'dwm-work-job':
        raise ObjectIndexError('Work/job.json er ikke en støttet DWM-jobbdefinisjon')
    saved_uid = str(data.get('job_uid') or '').strip()
    if not saved_uid:
        raise ObjectIndexError('Work/job.json mangler varig jobbidentitet (job_uid)')
    supplied_uid = str(getattr(snapshot, 'job_uid', '') or '').strip()
    if supplied_uid and supplied_uid != saved_uid:
        raise ObjectIndexError(
            'Valgt Analyse-jobb og Work er knyttet til forskjellige jobbidentiteter '
            '(job_uid). Kontroller Work-mappen i jobblisten; ikke endre job.json manuelt.')
    report = Path(snapshot.report_path)
    if (report.is_symlink() or not report.is_file()
            or not report.resolve(strict=True).is_relative_to(work)):
        raise ObjectIndexError('Analyse mangler original depotrapport i valgt Work')
    # A populated uid is independently asserted against job.json above; a2's
    # find_report() also verifies the report manifest when one is available.
    if not supplied_uid:
        selected_id = str(getattr(snapshot, 'job_id', '') or '').strip()
        job_info = data.get('job') or {}
        if not isinstance(job_info, dict):
            raise ObjectIndexError('Work/job.json mangler jobbinformasjon')
        aliases = {str(job_info.get('job_id') or '')}
        recorded_aliases = data.get('job_list_aliases') or []
        if isinstance(recorded_aliases, list):
            aliases.update(a for a in recorded_aliases if isinstance(a, str))
        if not selected_id or selected_id not in aliases:
            raise ObjectIndexError(
                'Analyse mangler job_uid, og JOB-ID stemmer ikke med valgt Work. '
                'Kontroller jobblistens Work-kobling.')
        manifest = report.parent / 'artifact_manifest.json'
        if (manifest.is_symlink() or not manifest.is_file()
                or manifest.stat().st_size > MAX_META_BYTES):
            raise ObjectIndexError(
                'Analyse mangler job_uid, og depotrapporten har ikke et verifiserbart '
                'jobbmanifest. Kan ikke knytte rapport til Work uten sikker kilde.')
        try:
            report_identity = json.loads(manifest.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError, UnicodeError) as exc:
            raise ObjectIndexError('Kan ikke lese depotrapportens jobbmanifest') from exc
        if (not isinstance(report_identity, dict)
                or str(report_identity.get('job_uid') or '') != saved_uid
                or str(report_identity.get('job_id') or '') != selected_id):
            raise ObjectIndexError(
                'Rapportens jobbmanifest samsvarer ikke med valgt Analyse-jobb og Work. '
                'Velg riktig jobb eller tilhørende Work-område.')
    return work, report, saved_uid


def _source(snapshot: Any) -> Path:
    # Reuse the established *exact* Source selection from Guided KS; never
    # scan sibling jobs, historical drives or arbitrary user-picked XML files.
    from app.ks_xml_evidence_v023_a19 import resolve_source_xml
    path = resolve_source_xml(snapshot.work, 'arkivstruktur.xml')
    if path is None or path.is_symlink() or not path.is_file():
        raise ObjectIndexError('arkivstruktur.xml finnes ikke i jobbens registrerte Source')
    return path.resolve(strict=True)


def _expected_source_sha(snapshot: Any) -> str:
    validation = (snapshot.report or {}).get('delivery_validation') or {}
    if (not isinstance(validation, dict) or validation.get('complete') is not True):
        return ''
    digest = str(validation.get('source_sha256') or '').lower()
    if not re.fullmatch(r'[a-f0-9]{64}', digest):
        return ''
    return digest


def _folder(work: Path) -> Path:
    base = work / 'noark5_evidence'
    for node in (base, base / 'noark5_objects_v027_a5'):
        if node.is_symlink() or (node.exists() and not node.is_dir()):
            raise ObjectIndexError('Utrygg objektindeksmappe i Work')
        node.mkdir(exist_ok=True)
    return base / 'noark5_objects_v027_a5'


def _local(tag: Any) -> str:
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _signature(path: Path) -> tuple[int, int, int, int]:
    s = path.stat()
    return (s.st_size, s.st_mtime_ns, s.st_dev, s.st_ino)


def _verify_manifest(snapshot: Any, meta: dict, *, db_digest: bool = False) -> Path:
    work, report, uid = _root(snapshot)
    if (not isinstance(meta, dict) or meta.get('model_id') != MODEL
            or meta.get('complete') is not True or meta.get('job_uid') != uid
            or meta.get('report_sha256') != _sha(report)):
        raise ObjectIndexError('Objektindeksen tilhører en annen rapportrevisjon')
    rel = meta.get('index_relative_path')
    if (not isinstance(rel, str) or not re.fullmatch(
            r'noark5_evidence/noark5_objects_v027_a5/[0-9a-f]{32}\.sqlite', rel)):
        raise ObjectIndexError('Ugyldig indeksreferanse')
    db = work / rel
    manifest_file = db.with_suffix('.json')
    folder = db.parent
    if ((work / 'noark5_evidence').is_symlink() or folder.is_symlink()
            or not db.resolve(strict=False).is_relative_to(work)
            or not manifest_file.resolve(strict=False).is_relative_to(work)
            or db.is_symlink() or manifest_file.is_symlink()
            or not db.is_file() or not manifest_file.is_file()
            or manifest_file.stat().st_size > MAX_META_BYTES):
        raise ObjectIndexError('Indeks eller manifest mangler / er utrygt')
    try:
        actual = json.loads(manifest_file.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ObjectIndexError('Uleselig indeksmanifest') from exc
    if actual != meta:
        raise ObjectIndexError('Indeksmanifestet ble endret etter innlasting')
    stat = db.stat()
    if (stat.st_size != meta.get('index_size')
            or stat.st_mtime_ns != meta.get('index_mtime_ns')):
        raise ObjectIndexError('Objektindeksfilen er endret etter indeksering')
    if db_digest and _sha(db) != meta.get('index_sha256'):
        raise ObjectIndexError('Objektindeksen har endret SHA-256')
    # Source may be disconnected. The complete, report-bound Work index is
    # still browseable, but it must never claim *current* source verification.
    return db


def current_source_status(snapshot: Any, meta: dict) -> str:
    """Source status for display; never silently upgrade historical evidence."""
    _verify_manifest(snapshot, meta)
    try:
        source = _source(snapshot)
        if str(source) != meta.get('source_path') or list(_signature(source)) != meta.get('source_signature'):
            return 'Kilde er endret eller flyttet etter indeksering'
    except (OSError, ValueError):
        return 'Original Source er frakoblet; viser bare lagret Work-indeks'
    return ('Kilde verifisert mot Work-evidens ved indeksering'
            if meta.get('source_binding') == 'work_sha256_verified'
            else 'Gjeldende Source lest; historisk SHA-256 er ikke dokumentert')


def find_cached_index(snapshot: Any) -> dict | None:
    """Use a COMPLETE and unchanged cache; no XML or arbitrary disk traversal."""
    try:
        work, report, uid = _root(snapshot)
        folder = work / INDEX_DIR
        if folder.is_symlink() or not folder.is_dir():
            return None
        report_sha = _sha(report)
        try:
            source = _source(snapshot)
            source_path, sig = str(source), list(_signature(source))
        except (OSError, ValueError):
            source_path = sig = None
        candidates = sorted(folder.glob('*.json'), reverse=True)[:MAX_CACHED]
        for path in candidates:
            if (path.is_symlink() or path.stat().st_size > MAX_META_BYTES
                    or not re.fullmatch(r'[0-9a-f]{32}\.json', path.name)):
                continue
            try:
                doc = json.loads(path.read_text(encoding='utf-8'))
                if (doc.get('job_uid') != uid or doc.get('report_sha256') != report_sha
                        or (source_path and (doc.get('source_path') != source_path
                                             or doc.get('source_signature') != sig))):
                    continue
                _verify_manifest(snapshot, doc, db_digest=True)
                return doc
            except (OSError, ValueError, TypeError):
                continue
    except (OSError, ValueError):
        pass
    return None


class _HashingReader:
    def __init__(self, file):
        self.file = file
        self.sha = sha256()
        self.bytes = 0

    def read(self, size: int = -1) -> bytes:
        data = self.file.read(size)
        if data:
            self.sha.update(data)
            self.bytes += len(data)
        return data


def build_object_index(snapshot: Any, *,
                       cancelled: Callable[[], bool] | None = None,
                       progress: Callable[[int], None] | None = None,
                       reuse: bool = True) -> dict:
    """Read all of one explicit Source XML and atomically publish derived Work data.

    Memory remains proportional to XML depth, not the number of objects. On
    cancellation, parse error or changed Source, no index manifest is published.
    """
    from lxml import etree

    work, report, uid = _root(snapshot)
    if cancelled and cancelled():
        raise ObjectIndexError('Indeksering avbrutt før start')
    if reuse:
        existing = find_cached_index(snapshot)
        if existing is not None:
            return existing
    source = _source(snapshot)
    expected = _expected_source_sha(snapshot)
    folder = _folder(work)
    report_sha = _sha(report)
    original = _signature(source)
    fd, temporary = tempfile.mkstemp(prefix='.a5-', suffix='.sqlite', dir=folder)
    os.close(fd)
    stage = Path(temporary)
    connection = None
    published_db = None
    counts: Counter[str] = Counter()
    ignored = Counter()
    frames: list[dict] = []
    active: list[dict] = []
    ordinal = 0
    event_total = 0
    root_tag = ''
    try:
        connection = sqlite3.connect(stage)
        connection.execute('PRAGMA journal_mode=DELETE')
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('CREATE TABLE objects ('
                           'id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL, '
                           'part_id INTEGER NOT NULL, kind TEXT NOT NULL, xml_tag TEXT NOT NULL, '
                           'xsi_type TEXT NOT NULL, native_id TEXT NOT NULL, title TEXT NOT NULL, '
                           'status TEXT NOT NULL, line INTEGER NOT NULL, '
                           'fields TEXT NOT NULL, search_blob TEXT NOT NULL)')
        connection.execute('CREATE INDEX objects_by_parent ON objects(parent_id, id)')
        connection.execute('CREATE INDEX objects_by_part ON objects(part_id, id)')
        connection.execute('CREATE INDEX objects_by_native ON objects(native_id)')
        with source.open('rb') as inp:
            reader = _HashingReader(inp)
            try:
                stream = etree.iterparse(reader, events=('start', 'end'),
                                         resolve_entities=False, load_dtd=False,
                                         no_network=True, huge_tree=False)
                for event, element in stream:
                    event_total += 1
                    if event_total % 8192 == 0 and cancelled and cancelled():
                        raise ObjectIndexError('Indeksering avbrutt, ingen delvis indeks publisert')
                    name = _local(element.tag)
                    if event == 'start':
                        if not frames:
                            root_tag = name
                            # In Noark 5 3.1/4.0/5.0, arkivstruktur.xml is the
                            # FILE NAME; its XSD root ELEMENT is <arkiv>.
                            if root_tag != 'arkiv':
                                raise ObjectIndexError(
                                    'Ugyldig rotelement i arkivstruktur.xml: forventer '
                                    '<arkiv>, fant <' + root_tag + '>')
                        if len(frames) >= MAX_DEPTH:
                            raise ObjectIndexError('XML-hierarkiet overskrider sikker dybde')
                        parent = active[-1] if active else None
                        kind = OBJECT_TAGS.get(name)
                        # Archive hierarchy is anchored to observed parents;
                        # the ignored intermediate klasse/system nodes keep
                        # their actual archive-part owner on the active stack.
                        admissible = (
                            # An archive can contain underarkiv, not only arkivdel.
                            kind == 'arkiv' and (parent is None or parent['kind'] == 'arkiv') or
                            kind == 'arkivdel' and parent is not None and parent['kind'] == 'arkiv' or
                            kind == 'mappe' and parent is not None and parent['kind'] in ('arkivdel', 'mappe') or
                            kind == 'registrering' and parent is not None and parent['kind'] in ('mappe', 'arkivdel'))
                        if kind and not admissible:
                            ignored[name] += 1
                        frame = {'tag': name, 'kind': kind if admissible else None}
                        if admissible:
                            ordinal += 1
                            if ordinal > MAX_ROWS:
                                raise ObjectIndexError('Objektindeksen overskrider sikker radgrense')
                            typ = str(element.attrib.get(XSI_TYPE) or '')
                            if len(typ) > 250:
                                raise ObjectIndexError('Uventet lang xsi:type i Source')
                            frame.update(id=ordinal,
                                         parent_id=parent['id'] if parent else 0,
                                         part_id=(ordinal if kind == 'arkivdel' else
                                                  parent['part_id'] if parent else 0),
                                         xsi_type=typ, fields={},
                                         line=int(element.sourceline or 0))
                            active.append(frame)
                        frames.append(frame)
                    else:
                        if not frames or frames[-1]['tag'] != name:
                            raise ObjectIndexError('Uventet XML-avslutning')
                        frame = frames[-1]
                        if (name in FIELDS and len(frames) >= 2
                                and frames[-2].get('kind') and name not in frames[-2]['fields']):
                            raw = (element.text or '').strip()
                            if len(raw) > 1000:
                                raw = raw[:1000] + ' [forkortet]'
                            frames[-2]['fields'][name] = raw
                        if frame.get('kind'):
                            fields = frame['fields']
                            title = fields.get('tittel', '')
                            native = fields.get('systemID', '')
                            status = (fields.get('saksstatus') or fields.get('journalstatus')
                                      or fields.get('arkivdelstatus') or fields.get('arkivstatus') or '')
                            search = ' '.join((native, title, frame['tag'], frame['xsi_type'],
                                               *fields.values())).casefold()
                            connection.execute('INSERT INTO objects VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                                               (frame['id'], frame['parent_id'], frame['part_id'],
                                                frame['kind'], frame['tag'], frame['xsi_type'], native,
                                                title, status, frame['line'],
                                                json.dumps(fields, ensure_ascii=False), search))
                            counts[frame['kind']] += 1
                            active.pop()
                            completed = sum(counts.values())
                            if completed % 10000 == 0:
                                connection.commit()
                            if completed % 1000 == 0 and progress:
                                progress(completed)
                        frames.pop()
                        element.clear()
                        parent_element = element.getparent()
                        if parent_element is not None:
                            while element.getprevious() is not None:
                                del parent_element[0]
                del stream
            except etree.XMLSyntaxError as exc:
                raise ObjectIndexError('Uleselig eller ufullstendig Source XML: ' + str(exc)) from exc
            # Capture exact Source bytes, including trailing whitespace.
            for piece in iter(lambda: reader.read(1024 * 1024), b''):
                if cancelled and cancelled():
                    raise ObjectIndexError('Indeksering avbrutt etter XML-lesing')
            source_sha = reader.sha.hexdigest()
            if reader.bytes != original[0] or frames or active:
                raise ObjectIndexError('Ufullstendig Source XML; indeksen publiseres ikke')
        if _signature(source) != original:
            raise ObjectIndexError('Source XML endret seg under indeksering')
        if expected and source_sha != expected:
            raise ObjectIndexError('Source SHA-256 samsvarer ikke med lagret Work-evidens')
        if cancelled and cancelled():
            raise ObjectIndexError('Indeksering avbrutt før publisering')
        if _sha(report) != report_sha:
            raise ObjectIndexError('Depotrapporten endret seg under indeksering')
        connection.commit()
        connection.close()
        connection = None
        db_digest = _sha(stage)
        key = uuid4().hex
        dest = folder / (key + '.sqlite')
        manifest = dest.with_suffix('.json')
        metadata = {
            'model_id': MODEL, 'complete': True, 'job_uid': uid,
            'report_sha256': report_sha,
            'index_relative_path': INDEX_DIR + '/' + dest.name,
            'index_sha256': db_digest,
            'index_size': stage.stat().st_size,
            'index_mtime_ns': stage.stat().st_mtime_ns,
            'source_path': str(source), 'source_sha256': source_sha,
            'source_signature': list(original),
            'source_binding': ('work_sha256_verified' if expected else 'current_source_only'),
            'expected_source_sha256': expected or None,
            'row_count': sum(counts.values()),
            'counts_by_kind': dict(sorted(counts.items())),
            'ignored_unanchored_elements': dict(sorted(ignored.items())),
            'automatic_approval': False,
            'note': 'Fullstendig strukturindeks, ikke en normativ Noark 5-godkjenning.',
        }
        # Publish complete SQLite first, then its manifest. Never overwrite
        # a previous evidence version, test result or A4 review ledger.
        os.replace(stage, dest)
        published_db = dest
        fd, temp_manifest = tempfile.mkstemp(prefix='.a5-meta-', dir=folder)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as out:
                json.dump(metadata, out, ensure_ascii=False, indent=2)
                out.write('\n')
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp_manifest, manifest)
        finally:
            if os.path.exists(temp_manifest):
                os.unlink(temp_manifest)
        if progress:
            progress(metadata['row_count'])
        return metadata
    except (sqlite3.Error, OSError, UnicodeError) as exc:
        raise ObjectIndexError('Kan ikke bygge komplett objektindeks: ' + str(exc)) from exc
    finally:
        if connection is not None:
            connection.close()
        if stage.exists():
            stage.unlink()
        if published_db is not None and not published_db.with_suffix('.json').exists():
            published_db.unlink(missing_ok=True)


def _connection(snapshot: Any, meta: dict):
    from contextlib import closing
    db = _verify_manifest(snapshot, meta)
    conn = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
    conn.execute('PRAGMA query_only=ON')
    return closing(conn)


def _get(conn: sqlite3.Connection, object_id: int) -> dict | None:
    row = conn.execute('SELECT id, parent_id, part_id, kind, xml_tag, xsi_type, '
                       'native_id, title, status, line, fields FROM objects WHERE id=?',
                       (object_id,)).fetchone()
    if row is None:
        return None
    obj = dict(zip(('id','parent_id','part_id','kind','xml_tag','xsi_type',
                    'native_id','title','status','line','fields'), row))
    obj['fields'] = json.loads(obj['fields'])
    return obj


def object_details(snapshot: Any, meta: dict, object_id: int) -> dict:
    if type(object_id) is not int or object_id <= 0:
        raise ObjectIndexError('Velg et lagret Noark-objekt')
    try:
        with _connection(snapshot, meta) as conn:
            obj = _get(conn, object_id)
            if obj is None:
                raise ObjectIndexError('Valgt objekt finnes ikke i denne rapportindeksen')
            lineage = []
            n = obj['parent_id']
            while n:
                ancestor = _get(conn, n)
                if ancestor is None or len(lineage) >= MAX_DEPTH:
                    raise ObjectIndexError('Ufullstendig objekt-hierarki')
                lineage.append(ancestor)
                n = ancestor['parent_id']
            obj['ancestors'] = tuple(reversed(lineage))
            obj['children'] = conn.execute('SELECT count(*) FROM objects WHERE parent_id=?',
                                           (object_id,)).fetchone()[0]
            obj['id_is_unique'] = bool(obj['native_id'] and conn.execute(
                'SELECT count(*) FROM objects WHERE native_id=?',
                (obj['native_id'],)).fetchone()[0] == 1)
            return obj
    except sqlite3.Error as exc:
        raise ObjectIndexError('Kan ikke lese objektindeks') from exc


def object_page(snapshot: Any, meta: dict, *, parent_id: int = 0,
                page: int = 0, page_size: int = 100,
                search: str = '', kind: str = '') -> dict:
    """Read a bounded page of actual XML objects, never aggregate guesses."""
    if (type(parent_id) is not int or parent_id < 0
            or type(page) is not int or page < 0
            or type(page_size) is not int or not 1 <= page_size <= MAX_PAGE
            or kind not in ('', 'arkiv', 'arkivdel', 'mappe', 'registrering')
            or not isinstance(search, str) or len(search) > 240):
        raise ObjectIndexError('Ugyldig side eller søkefilter')
    try:
        with _connection(snapshot, meta) as conn:
            if parent_id and _get(conn, parent_id) is None:
                raise ObjectIndexError('Valgt overordnet objekt finnes ikke')
            filters = ['parent_id=?']
            args: list[Any] = [parent_id]
            if kind:
                filters.append('kind=?')
                args.append(kind)
            if search.strip():
                filters.append('instr(search_blob, ?) > 0')
                args.append(search.strip().casefold())
            clause = ' AND '.join(filters)
            total = conn.execute('SELECT count(*) FROM objects WHERE '+clause, args).fetchone()[0]
            ids = [r[0] for r in conn.execute('SELECT id FROM objects WHERE '+clause+
                                            ' ORDER BY id LIMIT ? OFFSET ?',
                                            (*args, page_size, page * page_size))]
            rows = [_get(conn, n) for n in ids]
            if ids:
                placeholders = ','.join('?' for _ in ids)
                children = dict(conn.execute('SELECT parent_id,count(*) FROM objects WHERE parent_id IN ('+
                                             placeholders+') GROUP BY parent_id', ids))
                for row in rows:
                    row['children'] = children.get(row['id'], 0)
            return {'rows': rows, 'total': total, 'page': page,
                    'pages': (total + page_size - 1) // page_size,
                    'complete': True, 'row_count_all': meta['row_count']}
    except sqlite3.Error as exc:
        raise ObjectIndexError('Kan ikke lese sidevis objektregister') from exc


def _object_target(meta: dict, obj: dict) -> str:
    # Exact observed ordinal is only stable within the SHA-verified source.
    return 'analysis-a5:' + json.dumps(
        [str(meta['source_sha256']), int(obj['id']), str(obj['kind'])],
        ensure_ascii=False, separators=(',', ':'))


def object_comments(snapshot: Any, meta: dict, object_id: int) -> tuple[dict, ...]:
    from noark5_workflow.analysis.depot_annotations import list_depot_annotations
    obj = object_details(snapshot, meta, object_id)
    return tuple(list_depot_annotations(
        snapshot.report_path, view_id='analysis', target_type='noark5_object',
        target_id=_object_target(meta, obj)))


def save_object_comment(snapshot: Any, meta: dict, object_id: int, *,
                        text: str, kind: str, user: Any) -> dict:
    """Append to the existing A4/depot_annotations.json, no second ledger."""
    from noark5_workflow.analysis.depot_annotations import record_depot_annotation
    if kind not in ('note', 'deviation', 'question', 'follow_up'):
        raise ObjectIndexError('Ukjent kommentartype')
    obj = object_details(snapshot, meta, object_id)
    _root(snapshot)  # report and job scope rechecked
    report = Path(snapshot.report_path)
    if report.with_name('depot_annotations.json').is_symlink():
        raise ObjectIndexError('Kommentarregisteret kan ikke være en symbolsk lenke')
    return record_depot_annotation(
        report, annotation_type=kind, text=text, user=user,
        view_id='analysis', target_type='noark5_object',
        target_id=_object_target(meta, obj),
        target_label=f"{obj['kind']} / {obj['native_id'] or 'uten systemID'} / XML-linje {obj['line']}")


def linked_delivery_findings(snapshot: Any, meta: dict, object_id: int) -> dict:
    """Only exact, unique systemID and verified same-source delivery evidence."""
    obj = object_details(snapshot, meta, object_id)
    if not (getattr(snapshot, 'findings_complete', False)
            and meta.get('source_binding') == 'work_sha256_verified'
            and obj['id_is_unique']):
        return {'complete': False, 'rows': (),
                'note': 'Funn kan ikke knyttes sikkert til objektet (kilde/ID/dekning).'}
    native = obj['native_id']
    part = next((x['native_id'] for x in (obj, *reversed(obj['ancestors']))
                 if x['kind'] == 'arkivdel'), '')
    rows = tuple(f for f in snapshot.findings
                 if str(f.get('object_id') or '') == native
                 and (not f.get('archive_part_id') or f.get('archive_part_id') == part))
    return {'complete': True, 'rows': rows,
            'note': 'Bare identitetsmatchende DWM-avleveringsfunn (ikke alle testmotorer).'}
